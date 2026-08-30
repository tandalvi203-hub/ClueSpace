/**
 * ClueSpace Application Master Controller
 * Mounts ClueSpace Console, initializes data services and 4 screens.
 */

import { initNavigation, onScreenChange } from './navigation.js';
import { renderMissionControl } from './screen1_mission_control.js';
import { renderIncidentExplorer } from './screen2_incident_explorer.js';
import { renderInvestigationWorkspace } from './screen3_investigation_workspace.js';

export async function mountClueSpace(rootElement, onExitCallback) {
  rootElement.innerHTML = `
    <!-- Starfield Canvas -->
    <canvas id="cluespace-starfield" class="cluespace-starfield"></canvas>

    <!-- Clean Floating Left Vertical Navigation -->
    <aside class="cluespace-sidebar-nav" id="cluespace-sidebar-nav">
      <ul class="nav-timeline-list">
        
        <!-- 01: MISSION CONTROL -->
        <li class="nav-timeline-item active" data-screen="screen-mission-control" title="01 — MISSION CONTROL">
          <div class="nav-circle-wrapper">
            <div class="nav-circumference-light"></div>
            <div class="nav-circle-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="8" />
                <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
              </svg>
            </div>
          </div>
          <div class="nav-item-meta">
            <span class="nav-item-num">01</span>
            <span class="nav-item-title">MISSION CONTROL</span>
          </div>
        </li>

        <!-- 02: INCIDENT EXPLORER -->
        <li class="nav-timeline-item" data-screen="screen-incident-explorer" title="02 — INCIDENT EXPLORER">
          <div class="nav-circle-wrapper">
            <div class="nav-circumference-light"></div>
            <div class="nav-circle-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
          </div>
          <div class="nav-item-meta">
            <span class="nav-item-num">02</span>
            <span class="nav-item-title">INCIDENT EXPLORER</span>
          </div>
        </li>

        <!-- 03: INVESTIGATION WORKSPACE -->
        <li class="nav-timeline-item" data-screen="screen-investigation-workspace" title="03 — INVESTIGATION WORKSPACE">
          <div class="nav-circle-wrapper">
            <div class="nav-circumference-light"></div>
            <div class="nav-circle-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
              </svg>
            </div>
          </div>
          <div class="nav-item-meta">
            <span class="nav-item-num">03</span>
            <span class="nav-item-title">INVESTIGATION WORKSPACE</span>
          </div>
        </li>

      </ul>
    </aside>

    <!-- Main Content Area -->
    <main class="cluespace-main-content">
      <section id="screen-mission-control" class="cluespace-screen-view active-screen"></section>
      <section id="screen-incident-explorer" class="cluespace-screen-view"></section>
      <section id="screen-investigation-workspace" class="cluespace-screen-view"></section>
    </main>
  `;

  // Attach Exit Button
  const exitBtn = rootElement.querySelector('#btn-exit-cluespace');
  if (exitBtn && onExitCallback) {
    exitBtn.addEventListener('click', onExitCallback);
  }

  // Render Screens
  const screen1Container = rootElement.querySelector('#screen-mission-control');
  const screen2Container = rootElement.querySelector('#screen-incident-explorer');
  const screen3Container = rootElement.querySelector('#screen-investigation-workspace');

  await Promise.all([
    renderMissionControl(screen1Container),
    renderIncidentExplorer(screen2Container),
    renderInvestigationWorkspace(screen3Container)
  ]);

  // Initialize Navigation
  initNavigation();

  // Background Starfield
  initClueSpaceStarfield(rootElement.querySelector('#cluespace-starfield'));
}

function initClueSpaceStarfield(canvas) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let width = 0;
  let height = 0;
  let dpr = window.devicePixelRatio || 1;
  let animId = null;

  const STAR_COUNT = 85;
  const stars = [];

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
  }

  function initStars() {
    stars.length = 0;
    for (let i = 0; i < STAR_COUNT; i++) {
      stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        radius: 0.35 + Math.random() * 0.75, // Faint micro-points (0.35px - 1.1px)
        baseAlpha: 0.08 + Math.random() * 0.22, // Low contrast (0.08 - 0.30)
        twinkleSpeed: 0.0003 + Math.random() * 0.0007,
        phase: Math.random() * Math.PI * 2,
        vx: (Math.random() - 0.5) * 0.03, // Barely perceptible horizontal drift
        vy: -0.04 - Math.random() * 0.08, // Very slow upward drift
        color: Math.random() > 0.35 ? '210, 230, 255' : '185, 215, 255'
      });
    }
  }

  resize();
  initStars();

  window.addEventListener('resize', () => {
    resize();
    initStars();
  });

  let lastTime = performance.now();

  function animate(now) {
    const dt = Math.min((now - lastTime) / 1000, 0.1);
    lastTime = now;

    // Fill with deep-space background: #01040a center vignette to pure #000000
    const grad = ctx.createRadialGradient(
      width * 0.5, height * 0.5, 0,
      width * 0.5, height * 0.5, Math.max(width, height) * 0.85
    );
    grad.addColorStop(0, '#01040a');
    grad.addColorStop(0.6, '#000206');
    grad.addColorStop(1, '#000000');

    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    // Draw faint micro-stars with seamless wrapping
    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];

      s.x += s.vx * (dt * 60);
      s.y += s.vy * (dt * 60);

      // Seamless toroidal wrapping
      if (s.y < 0) s.y = height;
      if (s.y > height) s.y = 0;
      if (s.x < 0) s.x = width;
      if (s.x > width) s.x = 0;

      s.phase += s.twinkleSpeed * (dt * 1000);
      const twinkle = Math.sin(s.phase) * 0.2;
      let alpha = Math.max(0.04, Math.min(0.32, s.baseAlpha + twinkle));

      // Edge fading to ensure perfectly seamless wrap-around without pop
      const edgeFade = 25;
      let edgeFactor = 1;
      if (s.y < edgeFade) edgeFactor = Math.min(edgeFactor, s.y / edgeFade);
      if (s.y > height - edgeFade) edgeFactor = Math.min(edgeFactor, (height - s.y) / edgeFade);
      if (s.x < edgeFade) edgeFactor = Math.min(edgeFactor, s.x / edgeFade);
      if (s.x > width - edgeFade) edgeFactor = Math.min(edgeFactor, (width - s.x) / edgeFade);
      alpha *= edgeFactor;

      ctx.beginPath();
      ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${s.color}, ${alpha.toFixed(3)})`;
      ctx.fill();
    }

    animId = requestAnimationFrame(animate);
  }

  animId = requestAnimationFrame(animate);
}
