/**
 * ClueSpace System Journey — Scroll-Driven Sequential Storytelling Controller
 */

let isInitialized = false;
let scrollListenerActive = false;
let animationFrameId = null;

/**
 * Initializes the scroll-driven System Journey experience
 */
export function initSystemWorkflow(onOpenConsoleCallback) {
  const container = document.getElementById('workflow-section');
  if (!container) return;

  if (isInitialized) {
    updateSystemScrollState();
    return;
  }
  isInitialized = true;

  // Initialize micro-canvas graphics
  initDetectCanvas();
  initConnectCanvas();
  initReconstructCanvas();

  // Bind CTA button
  const ctaBtn = document.getElementById('system-final-cta');
  if (ctaBtn) {
    ctaBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof onOpenConsoleCallback === 'function') {
        onOpenConsoleCallback();
      }
    });
  }

  // Setup Scroll-Driven Controller
  setupScrollController();
}

/**
 * Calculates step positions and activates the in-focus step row
 */
function updateSystemScrollState() {
  const container = document.getElementById('workflow-section');
  const track = document.getElementById('system-journey-track');
  const progressBar = document.getElementById('system-central-line-progress');
  const rows = document.querySelectorAll('.system-step-row');

  if (!container || !track || rows.length === 0) return;

  const viewportHeight = window.innerHeight;
  const viewportCenter = window.scrollY + viewportHeight * 0.5;

  // 1. Calculate Progress Line Height
  const trackRect = track.getBoundingClientRect();
  const trackTop = trackRect.top + window.scrollY;
  const trackHeight = trackRect.height;

  if (trackHeight > 0) {
    const rawProgress = (viewportCenter - trackTop) / trackHeight;
    const clampedProgress = Math.max(0, Math.min(1, rawProgress));
    if (progressBar) {
      progressBar.style.height = `${(clampedProgress * 100).toFixed(1)}%`;
    }
  }

  // 2. Determine Active Step based on proximity to viewport center
  let activeIndex = -1;
  let minDistance = Infinity;

  rows.forEach((row, idx) => {
    const rowRect = row.getBoundingClientRect();
    const rowCenter = rowRect.top + window.scrollY + rowRect.height * 0.5;
    const dist = Math.abs(viewportCenter - rowCenter);

    // Give a focused window
    if (dist < minDistance && dist < viewportHeight * 0.55) {
      minDistance = dist;
      activeIndex = idx;
    }
  });

  // Default to first step if near top of track
  if (activeIndex === -1 && trackRect.top < viewportHeight * 0.5 && trackRect.bottom > 0) {
    activeIndex = 0;
  }

  // 3. Update DOM classes for active/passed/upcoming state
  rows.forEach((row, idx) => {
    if (idx === activeIndex) {
      row.classList.add('is-active');
      row.classList.remove('is-passed', 'is-upcoming');
    } else if (idx < activeIndex) {
      row.classList.remove('is-active', 'is-upcoming');
      row.classList.add('is-passed');
    } else {
      row.classList.remove('is-active', 'is-passed');
      row.classList.add('is-upcoming');
    }
  });
}

/**
 * Sets up optimized requestAnimationFrame scroll listener
 */
function setupScrollController() {
  if (scrollListenerActive) return;
  scrollListenerActive = true;

  let ticking = false;
  const onScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        updateSystemScrollState();
        ticking = false;
      });
      ticking = true;
    }
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });

  // Initial call to set state
  setTimeout(updateSystemScrollState, 50);
}

/**
 * Micro Visual 01: Telemetry Waveform with Anomaly Peak
 */
function initDetectCanvas() {
  const canvas = document.getElementById('vis-detect-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 240;
  const height = canvas.clientHeight || 72;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);

  const points = [];
  const count = 48;
  const peakIndex = 32;

  for (let i = 0; i < count; i++) {
    const t = i / (count - 1);
    let val = Math.sin(t * Math.PI * 4) * 0.15 + (Math.random() - 0.5) * 0.1;
    if (Math.abs(i - peakIndex) < 5) {
      const peakDist = 1 - Math.abs(i - peakIndex) / 5;
      val -= peakDist * 0.7; // Anomaly drop/spike
    }
    points.push({ x: t * width, y: height * 0.5 + val * height * 0.45 });
  }

  // Draw background grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, height * 0.5);
  ctx.lineTo(width, height * 0.5);
  ctx.stroke();

  // Draw waveform line
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  points.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.stroke();

  // Draw peak anomaly marker
  const peakPt = points[peakIndex];
  if (peakPt) {
    // Vertical anomaly line
    ctx.strokeStyle = 'rgba(244, 63, 94, 0.6)';
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(peakPt.x, 0);
    ctx.lineTo(peakPt.x, height);
    ctx.stroke();
    ctx.setLineDash([]);

    // Red beacon dot
    ctx.fillStyle = '#f43f5e';
    ctx.shadowColor = '#f43f5e';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(peakPt.x, peakPt.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }
}

/**
 * Micro Visual 02: Connected Spacetime Anomaly Constellation Network
 */
function initConnectCanvas() {
  const canvas = document.getElementById('vis-connect-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 240;
  const height = canvas.clientHeight || 80;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);

  const nodes = [
    { x: width * 0.15, y: height * 0.35, r: 3, label: 'CADC0888', isRoot: true },
    { x: width * 0.40, y: height * 0.65, r: 2.5, label: 'CADC0872' },
    { x: width * 0.60, y: height * 0.30, r: 2.5, label: 'CADC0873' },
    { x: width * 0.85, y: height * 0.55, r: 2.5, label: 'CADC0894' },
    { x: width * 0.50, y: height * 0.45, r: 2.0, label: 'CADC0874' }
  ];

  const links = [
    [0, 1], [0, 2], [1, 3], [1, 4], [2, 4]
  ];

  // Draw links
  links.forEach(([i, j]) => {
    const a = nodes[i];
    const b = nodes[j];
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  });

  // Draw nodes
  nodes.forEach(n => {
    if (n.isRoot) {
      ctx.fillStyle = '#f43f5e';
      ctx.shadowColor = '#f43f5e';
      ctx.shadowBlur = 6;
    } else {
      ctx.fillStyle = '#38bdf8';
      ctx.shadowColor = '#38bdf8';
      ctx.shadowBlur = 4;
    }
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  });
}

/**
 * Micro Visual 03: Minimal Vector Wireframe Spacecraft Silhouette
 */
function initReconstructCanvas() {
  const canvas = document.getElementById('vis-sat-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 180;
  const height = canvas.clientHeight || 86;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);

  const cx = width * 0.5;
  const cy = height * 0.5;

  ctx.strokeStyle = 'rgba(56, 189, 248, 0.7)';
  ctx.lineWidth = 1.2;

  // Spacecraft Central Body (Isometric Faceted Prism)
  ctx.beginPath();
  ctx.moveTo(cx - 16, cy - 12);
  ctx.lineTo(cx + 16, cy - 8);
  ctx.lineTo(cx + 16, cy + 12);
  ctx.lineTo(cx - 16, cy + 8);
  ctx.closePath();
  ctx.stroke();

  // Starboard Solar Wing
  ctx.strokeStyle = 'rgba(168, 85, 247, 0.7)';
  ctx.beginPath();
  ctx.moveTo(cx + 16, cy);
  ctx.lineTo(cx + 52, cy - 10);
  ctx.lineTo(cx + 52, cy + 6);
  ctx.lineTo(cx + 16, cy + 16);
  ctx.closePath();
  ctx.stroke();

  // Port Solar Wing
  ctx.beginPath();
  ctx.moveTo(cx - 16, cy);
  ctx.lineTo(cx - 52, cy + 10);
  ctx.lineTo(cx - 52, cy - 6);
  ctx.lineTo(cx - 16, cy - 16);
  ctx.closePath();
  ctx.stroke();

  // Orbital Ring Arc
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
  ctx.setLineDash([2, 4]);
  ctx.beginPath();
  ctx.ellipse(cx, cy, 64, 24, -Math.PI / 12, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
}
