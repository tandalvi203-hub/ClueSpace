const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

// CRC32 table
const crcTable = [];
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) {
    if (c & 1) c = 0xedb88320 ^ (c >>> 1);
    else c = c >>> 1;
  }
  crcTable[n] = c;
}

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function readPNG(buffer) {
  let offset = 8; // skip signature
  let width, height, bitDepth, colorType, compression, filter, interlace;
  const idatChunks = [];

  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    offset += 12 + length;

    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
      compression = data[10];
      filter = data[11];
      interlace = data[12];
    } else if (type === 'IDAT') {
      idatChunks.push(data);
    } else if (type === 'IEND') {
      break;
    }
  }

  const compressedData = Buffer.concat(idatChunks);
  const decompressed = zlib.inflateSync(compressedData);

  const bytesPerPixel = colorType === 6 ? 4 : colorType === 2 ? 3 : 4;
  const rowStride = width * bytesPerPixel;
  const rawPixels = Buffer.alloc(width * height * 4); // RGBA

  let srcOffset = 0;
  const prevRow = Buffer.alloc(rowStride);
  const currRow = Buffer.alloc(rowStride);

  for (let y = 0; y < height; y++) {
    const filterType = decompressed[srcOffset++];
    for (let i = 0; i < rowStride; i++) {
      currRow[i] = decompressed[srcOffset++];
    }

    // Unfilter
    if (filterType === 1) { // Sub
      for (let i = bytesPerPixel; i < rowStride; i++) {
        currRow[i] = (currRow[i] + currRow[i - bytesPerPixel]) & 0xff;
      }
    } else if (filterType === 2) { // Up
      for (let i = 0; i < rowStride; i++) {
        currRow[i] = (currRow[i] + prevRow[i]) & 0xff;
      }
    } else if (filterType === 3) { // Average
      for (let i = 0; i < rowStride; i++) {
        const left = i >= bytesPerPixel ? currRow[i - bytesPerPixel] : 0;
        const up = prevRow[i];
        currRow[i] = (currRow[i] + Math.floor((left + up) / 2)) & 0xff;
      }
    } else if (filterType === 4) { // Paeth
      for (let i = 0; i < rowStride; i++) {
        const a = i >= bytesPerPixel ? currRow[i - bytesPerPixel] : 0;
        const b = prevRow[i];
        const c = i >= bytesPerPixel ? prevRow[i - bytesPerPixel] : 0;
        const p = a + b - c;
        const pa = Math.abs(p - a);
        const pb = Math.abs(p - b);
        const pc = Math.abs(p - c);
        let pr;
        if (pa <= pb && pa <= pc) pr = a;
        else if (pb <= pc) pr = b;
        else pr = c;
        currRow[i] = (currRow[i] + pr) & 0xff;
      }
    }

    currRow.copy(prevRow);

    // Copy to rawPixels (RGBA)
    for (let x = 0; x < width; x++) {
      const destIdx = (y * width + x) * 4;
      if (colorType === 2) { // RGB
        rawPixels[destIdx] = currRow[x * 3];
        rawPixels[destIdx + 1] = currRow[x * 3 + 1];
        rawPixels[destIdx + 2] = currRow[x * 3 + 2];
        rawPixels[destIdx + 3] = 255;
      } else if (colorType === 6) { // RGBA
        rawPixels[destIdx] = currRow[x * 4];
        rawPixels[destIdx + 1] = currRow[x * 4 + 1];
        rawPixels[destIdx + 2] = currRow[x * 4 + 2];
        rawPixels[destIdx + 3] = currRow[x * 4 + 3];
      }
    }
  }

  return { width, height, pixels: rawPixels };
}

function writePNG(width, height, rgbaPixels) {
  const rowBytes = width * 4;
  const filtered = Buffer.alloc(height * (rowBytes + 1));
  let destOffset = 0;

  for (let y = 0; y < height; y++) {
    filtered[destOffset++] = 0; // Filter: None
    rgbaPixels.copy(filtered, destOffset, y * rowBytes, (y + 1) * rowBytes);
    destOffset += rowBytes;
  }

  const idatData = zlib.deflateSync(filtered, { level: 9 });

  const chunks = [];
  // PNG Signature
  chunks.push(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));

  // IHDR
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // 8 bit
  ihdr[9] = 6; // RGBA
  ihdr[10] = 0; // deflate
  ihdr[11] = 0; // standard filter
  ihdr[12] = 0; // no interlace

  const ihdrChunk = Buffer.alloc(12 + 13);
  ihdrChunk.writeUInt32BE(13, 0);
  ihdrChunk.write('IHDR', 4);
  ihdr.copy(ihdrChunk, 8);
  ihdrChunk.writeUInt32BE(crc32(ihdrChunk.subarray(4, 21)), 21);
  chunks.push(ihdrChunk);

  // IDAT
  const idatChunk = Buffer.alloc(12 + idatData.length);
  idatChunk.writeUInt32BE(idatData.length, 0);
  idatChunk.write('IDAT', 4);
  idatData.copy(idatChunk, 8);
  idatChunk.writeUInt32BE(crc32(idatChunk.subarray(4, 8 + idatData.length)), 8 + idatData.length);
  chunks.push(idatChunk);

  // IEND
  const iendChunk = Buffer.alloc(12);
  iendChunk.writeUInt32BE(0, 0);
  iendChunk.write('IEND', 4);
  iendChunk.writeUInt32BE(crc32(iendChunk.subarray(4, 8)), 8);
  chunks.push(iendChunk);

  return Buffer.concat(chunks);
}

// Read original logo
const inputPath = path.resolve(__dirname, '../public/assets/images/cluespace-logo.png');
const inputBuf = fs.readFileSync(inputPath);
const { width, height, pixels } = readPNG(inputBuf);
console.log(`Original: ${width}x${height}`);

// Process pixels to remove black background and create smooth alpha
// For black background removal:
// Dark pixels (black) get alpha = 0.
// Glowing pixels get alpha proportional to their maximum RGB value,
// and color values are un-premultiplied so the logo colors remain crisp and vibrant on any dark/starfield background!
const outPixels = Buffer.alloc(width * height * 4);

for (let i = 0; i < pixels.length; i += 4) {
  const r = pixels[i];
  const g = pixels[i + 1];
  const b = pixels[i + 2];

  const maxVal = Math.max(r, g, b);

  if (maxVal <= 6) {
    // Pure black background
    outPixels[i] = 0;
    outPixels[i + 1] = 0;
    outPixels[i + 2] = 0;
    outPixels[i + 3] = 0;
  } else {
    // Calculate smooth alpha with nice curve
    // Linear to slight boost for glow
    let alpha = maxVal / 255;
    // Apply soft threshold at bottom
    if (maxVal < 25) {
      alpha = ((maxVal - 6) / 19) * (25 / 255);
    }
    // Boost glow midtones slightly so it stays visually prominent and sharp
    let finalAlpha = Math.min(1.0, Math.pow(alpha, 0.85) * 1.1);
    let alphaByte = Math.min(255, Math.max(1, Math.round(finalAlpha * 255)));

    // Un-premultiply RGB colors so they don't darken when rendered with alpha
    const unmult = finalAlpha > 0 ? (1.0 / finalAlpha) : 1;
    outPixels[i] = Math.min(255, Math.round(r * unmult));
    outPixels[i + 1] = Math.min(255, Math.round(g * unmult));
    outPixels[i + 2] = Math.min(255, Math.round(b * unmult));
    outPixels[i + 3] = alphaByte;
  }
}

const outPNG = writePNG(width, height, outPixels);
const outputPath = path.resolve(__dirname, '../public/assets/images/cluespace-logo-transparent.png');
fs.writeFileSync(outputPath, outPNG);
console.log(`Saved transparent logo (${outPNG.length} bytes) to ${outputPath}`);
