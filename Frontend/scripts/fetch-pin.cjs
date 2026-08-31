const https = require('https');

async function resolveUrl(url) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
  });
  console.log('Final URL:', res.url);
  const text = await res.text();
  
  // Search for video-list or media URLs in Pinterest payload
  const videoMatches = text.match(/https:\/\/[^"'\s]+\.mp4[^"'\s]*/g) || [];
  const gifMatches = text.match(/https:\/\/[^"'\s]+\.gif[^"'\s]*/g) || [];
  const webpMatches = text.match(/https:\/\/[^"'\s]+\.webp[^"'\s]*/g) || [];
  const imgMatches = text.match(/https:\/\/i\.pinimg\.com\/originals\/[^"'\s]+/g) || [];

  console.log('MP4:', [...new Set(videoMatches)]);
  console.log('GIF:', [...new Set(gifMatches)]);
  console.log('WEBP:', [...new Set(webpMatches)]);
  console.log('Original Img:', [...new Set(imgMatches)]);
}

resolveUrl('https://pin.it/5FvfMqgbO').catch(console.error);
