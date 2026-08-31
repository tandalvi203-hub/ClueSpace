/* ==========================================================================
   Space Mission: Incident Investigator — Core Controller & Telemetry Engine
   Optimized Architecture: Isolated Intro, Lazy Loaded Heavy Modules & 3D Visualizations
   ========================================================================== */

// Intro Screen Elements
const introScreen = document.getElementById('intro-screen');
const introVideo = document.getElementById('intro-video');
const btnSkipIntro = document.getElementById('btn-skip-intro');

// DOM Elements
const heroVideo = document.getElementById('hero-video');
const btnSoundToggle = document.getElementById('btn-sound-toggle');
const btnVideoPlay = document.getElementById('btn-video-play');
const btnCinemaToggle = document.getElementById('btn-cinema-toggle');
const hudHeader = document.getElementById('hud-header');
const scrollContainer = document.getElementById('scroll-container');
const cinemaExitHint = document.getElementById('cinema-exit-hint');
const starCanvas = document.getElementById('starfield-canvas');
const waveformCanvas = document.getElementById('waveform-canvas');

// Intro State & Navigation
let isIntroActive = true;
let isVideoPaused = false;
let isCinemaMode = false;

// Lazy Loading Singletons & Promises
let spatializerPromise = null;
let spacetimePromise = null;
let workflowInitDone = false;
let cluespacePromise = null;
let isClueSpaceMounted = false;
let isClueSpaceActive = false;

/**
 * Lazy initializer for Anomaly Spatializer (Screen 2)
 */
async function ensureAnomalySpatializer() {
  if (!spatializerPromise) {
    spatializerPromise = (async () => {
      const { initAnomalySpatializer } = await import('./src/cluespace/anomalySpatializer.js');
      await initAnomalySpatializer();
      initSpaceCanvas('spatializer-space-canvas');
    })();
  }
  return spatializerPromise;
}

/**
 * Lazy initializer for Telemetry Spacetime (Screen 3 / 4D Evidence Space)
 */
async function ensureTelemetrySpacetime() {
  if (!spacetimePromise) {
    spacetimePromise = (async () => {
      const { initTelemetrySpacetime } = await import('./src/cluespace/4dEvidenceSpace.js');
      await initTelemetrySpacetime();
    })();
  }
  return spacetimePromise;
}

/**
 * Lazy initializer for Workflow System Section
 */
function ensureWorkflowSection() {
  if (!workflowInitDone) {
    workflowInitDone = true;
    initSpaceCanvas('workflow-space-canvas');
    import('./src/cluespace/systemWorkflow.js').then(({ initSystemWorkflow }) => {
      initSystemWorkflow(() => openClueSpace());
    }).catch(err => console.error('Error initializing System Workflow:', err));
  }
}

/**
 * Lazy initializer for ClueSpace Console Application
 */
async function ensureClueSpaceApp() {
  if (!cluespacePromise) {
    cluespacePromise = (async () => {
      const { mountClueSpace } = await import('./src/cluespace/cluespace_app.js');
      await mountClueSpace(cluespaceAppEl, () => exitClueSpace('hero-section'));
      isClueSpaceMounted = true;
    })();
  }
  return cluespacePromise;
}

// ---------------------------------------------------------------------------
// Intro Playback & Smooth Transition to Main Screen
// ---------------------------------------------------------------------------
function playHeroVideo() {
  if (heroVideo && !isVideoPaused) {
    heroVideo.muted = true;
    heroVideo.playsInline = true;
    heroVideo.loop = true;
    if (heroVideo.ended) {
      heroVideo.currentTime = 0;
    }
    const p = heroVideo.play();
    if (p !== undefined) {
      p.catch(err => {
        console.warn('Hero video play deferred:', err);
      });
    }
  }
}

function finishIntro() {
  if (!isIntroActive) return;
  isIntroActive = false;

  if (introVideo) {
    try {
      introVideo.pause();
    } catch (e) {}
  }

  if (introScreen) {
    introScreen.classList.add('intro-dismissed');
    setTimeout(() => {
      introScreen.style.display = 'none';
      if (introVideo) {
        introVideo.src = '';
        introVideo.load();
      }
    }, 380);
  }

  // Handle direct hash or initial scroll position on refresh/load
  const rawHash = window.location.hash ? window.location.hash.replace('#', '') : '';
  if (rawHash === 'spatializer-section' || rawHash === 'spatializer') {
    scrollToSection('spatializer-section');
  } else if (rawHash === 'spacetime-section' || rawHash === 'spacetime') {
    scrollToSection('spacetime-section');
  } else if (rawHash === 'workflow-section' || rawHash === 'workflow') {
    scrollToSection('workflow-section');
  } else if (rawHash === 'cluespace' || rawHash === 'cluespace-app') {
    openClueSpace();
  } else {
    // Default Main Screen (Hero Section / Mission Logs)
    setActiveNav('hero-section');
    playHeroVideo();
    startStarCanvas();
    startMissionClock();

    // Check if the page is already scrolled to another section on refresh
    updateActiveNavOnScroll();
  }
}

if (heroVideo) {
  heroVideo.muted = true;
  heroVideo.playsInline = true;
  heroVideo.loop = true;
  heroVideo.addEventListener('canplay', () => {
    if (!isIntroActive) playHeroVideo();
  });
  heroVideo.addEventListener('loadeddata', () => {
    if (!isIntroActive) playHeroVideo();
  });
}

if (introVideo) {
  introVideo.muted = true;
  introVideo.playsInline = true;
  introVideo.addEventListener('ended', finishIntro);
  introVideo.addEventListener('error', finishIntro);

  // Auto-start intro video immediately
  const playPromise = introVideo.play();
  if (playPromise !== undefined) {
    playPromise.catch(() => {
      console.log('Intro video autoplay deferred by browser policy');
    });
  }
}

if (btnSkipIntro) {
  btnSkipIntro.addEventListener('click', (e) => {
    e.stopPropagation();
    finishIntro();
  });
}

if (introScreen) {
  introScreen.addEventListener('click', finishIntro);
}

// Fallback user interaction to ensure video starts
const ensureHeroPlayOnInteraction = () => {
  if (isIntroActive) {
    finishIntro();
  } else {
    playHeroVideo();
  }
};
window.addEventListener('click', ensureHeroPlayOnInteraction);
window.addEventListener('keydown', ensureHeroPlayOnInteraction);
window.addEventListener('touchstart', ensureHeroPlayOnInteraction);

// Listen for hash changes
window.addEventListener('hashchange', () => {
  const hash = window.location.hash ? window.location.hash.replace('#', '') : '';
  if (hash && document.getElementById(hash)) {
    scrollToSection(hash);
  }
});

// ---------------------------------------------------------------------------
// Navigation & Panels
// ---------------------------------------------------------------------------
const navButtons = document.querySelectorAll('.nav-btn');
const viewPanels = document.querySelectorAll('.view-panel');
const panelCloseBtns = document.querySelectorAll('.panel-close-btn');

// Sections
const heroSection = document.getElementById('hero-section');
const spatializerSection = document.getElementById('spatializer-section');
const spacetimeSection = document.getElementById('spacetime-section');
const workflowSection = document.getElementById('workflow-section');
const scrollDownHint = document.getElementById('scroll-down-hint');

// Telemetry Elements
const metClock = document.getElementById('met-clock');
const valVelocity = document.getElementById('val-velocity');
const dynPitch = document.getElementById('dyn-pitch');
const dynYaw = document.getElementById('dyn-yaw');
const dynRoll = document.getElementById('dyn-roll');
const dynAlt = document.getElementById('dyn-alt');
const dynThrustVal = document.getElementById('dyn-thrust-val');
const sliderTimestamp = document.getElementById('slider-timestamp');
const timelineSlider = document.getElementById('timeline-slider');

// Audio Synth Context
let audioCtx = null;
let isAudioActive = false;
let ambientDroneNode = null;
let ambientGainNode = null;

// 1. Navigation: Immediate Screen Initialization & Accurate Active State
function setActiveNav(sectionId) {
  navButtons.forEach(btn => {
    if (btn.dataset.scroll === sectionId) {
      btn.classList.add('active');
    } else if (btn.dataset.scroll || btn.id === 'btn-open-cluespace') {
      btn.classList.remove('active');
    }
  });
}

function scrollToSection(sectionId) {
  setActiveNav(sectionId);

  // Always initialize the target screen immediately upon navigation click
  if (sectionId === 'spatializer-section') {
    ensureAnomalySpatializer();
  } else if (sectionId === 'spacetime-section') {
    ensureTelemetrySpacetime();
  } else if (sectionId === 'workflow-section') {
    ensureWorkflowSection();
  } else if (sectionId === 'hero-section') {
    playHeroVideo();
    startStarCanvas();
    startMissionClock();
  }

  const target = document.getElementById(sectionId);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth' });
    closeAllModals();
    playBeep(680, 0.08, 'sine');
  }
}

function openModal(panelId) {
  closeAllModals();
  const panel = document.getElementById(panelId);
  if (panel) {
    panel.classList.add('active-panel');
    playBeep(720, 0.09, 'sine');
    if (panelId === 'telemetry-view') {
      startWaveform();
    }
  }
}

function closeAllModals() {
  viewPanels.forEach(panel => {
    panel.classList.remove('active-panel');
  });
  stopWaveform();
}

// Brand Badge Logo navigation
const brandBadge = document.getElementById('brand-badge');
const hudNavRight = document.getElementById('hud-nav-right');

if (brandBadge) {
  brandBadge.addEventListener('click', () => {
    if (isClueSpaceActive) {
      exitClueSpace('hero-section');
    } else {
      scrollToSection('hero-section');
    }
  });
}

navButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.id === 'btn-open-cluespace') {
      if (!isClueSpaceActive) {
        openClueSpace();
      }
    } else if (btn.dataset.scroll) {
      if (isClueSpaceActive) {
        exitClueSpace(btn.dataset.scroll);
      } else {
        scrollToSection(btn.dataset.scroll);
      }
    } else if (btn.dataset.target) {
      openModal(btn.dataset.target);
    }
  });
});

panelCloseBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    closeAllModals();
    playBeep(480, 0.06, 'sine');
  });
});

if (scrollDownHint) {
  scrollDownHint.addEventListener('click', (e) => {
    e.preventDefault();
    scrollToSection('spatializer-section');
  });
}

// 2. Precise Scroll-Spy for Active Nav Link based on Viewport Center
const sections = [heroSection, spatializerSection, spacetimeSection, workflowSection].filter(Boolean);

function updateActiveNavOnScroll() {
  if (isClueSpaceActive) return;

  const scrollY = window.scrollY || window.pageYOffset || 0;
  const viewportCenter = scrollY + window.innerHeight / 2;

  let activeSec = heroSection;
  let minDistance = Infinity;

  for (const sec of sections) {
    const rect = sec.getBoundingClientRect();
    if (rect.top <= window.innerHeight * 0.5 && rect.bottom >= window.innerHeight * 0.5) {
      activeSec = sec;
      break;
    }
    const secCenter = rect.top + scrollY + rect.height / 2;
    const distance = Math.abs(viewportCenter - secCenter);
    if (distance < minDistance) {
      minDistance = distance;
      activeSec = sec;
    }
  }

  if (activeSec && activeSec.id) {
    setActiveNav(activeSec.id);

    // Automatically ensure the active screen is initialized without requiring nav clicks
    if (!isIntroActive) {
      if (activeSec.id === 'spatializer-section') {
        ensureAnomalySpatializer();
      } else if (activeSec.id === 'spacetime-section') {
        ensureTelemetrySpacetime();
      } else if (activeSec.id === 'workflow-section') {
        ensureWorkflowSection();
      } else if (activeSec.id === 'hero-section') {
        if (heroVideo && !isVideoPaused && heroVideo.paused) {
          heroVideo.play().catch(() => {});
        }
        startStarCanvas();
        startMissionClock();
      }
    }
  }
}

let scrollTicking = false;
window.addEventListener('scroll', () => {
  if (!scrollTicking) {
    window.requestAnimationFrame(() => {
      updateActiveNavOnScroll();
      scrollTicking = false;
    });
    scrollTicking = true;
  }
}, { passive: true });

// Optional Preloading Observer for Heavy 3D Modules when approaching Viewport
const preloadObserver = new IntersectionObserver((entries) => {
  if (isIntroActive || isClueSpaceActive) return;
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const id = entry.target.id;
      if (id === 'spatializer-section') {
        ensureAnomalySpatializer();
      } else if (id === 'spacetime-section') {
        ensureTelemetrySpacetime();
      } else if (id === 'workflow-section') {
        ensureWorkflowSection();
      }
    }
  });
}, { root: null, rootMargin: '250px', threshold: 0.05 });

sections.forEach(sec => preloadObserver.observe(sec));

// 3. Hero Video Play / Pause
function toggleVideoPlay() {
  isVideoPaused = !isVideoPaused;
  if (heroVideo) {
    if (isVideoPaused) {
      heroVideo.pause();
    } else {
      heroVideo.play().catch(() => {});
    }
  }

  if (isVideoPaused) {
    btnVideoPlay.innerHTML = `
      <svg class="icon" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      <span class="ctrl-tooltip">PLAY VIDEO</span>
    `;
  } else {
    btnVideoPlay.innerHTML = `
      <svg class="icon" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
        <rect x="6" y="4" width="4" height="16" rx="1"/>
        <rect x="14" y="4" width="4" height="16" rx="1"/>
      </svg>
      <span class="ctrl-tooltip">PAUSE VIDEO</span>
    `;
  }
  playBeep(440, 0.06, 'triangle');
}

if (btnVideoPlay) {
  btnVideoPlay.addEventListener('click', toggleVideoPlay);
}

// 4. Cinema Mode (Clean Video View)
function toggleCinemaMode() {
  isCinemaMode = !isCinemaMode;
  if (isCinemaMode) {
    if (hudHeader) hudHeader.classList.add('cinema-hidden');
    if (scrollContainer) scrollContainer.style.opacity = '0';
    if (cinemaExitHint) cinemaExitHint.classList.add('visible');
    closeAllModals();
    playBeep(520, 0.1, 'sine');
  } else {
    if (hudHeader) hudHeader.classList.remove('cinema-hidden');
    if (scrollContainer) scrollContainer.style.opacity = '1';
    if (cinemaExitHint) cinemaExitHint.classList.remove('visible');
    playBeep(780, 0.08, 'sine');
  }
}

if (btnCinemaToggle) {
  btnCinemaToggle.addEventListener('click', toggleCinemaMode);
}
if (cinemaExitHint) {
  cinemaExitHint.addEventListener('click', () => {
    if (isCinemaMode) toggleCinemaMode();
  });
}

// 5. Web Audio Sci-Fi Sound FX & Atmospheric Drone
function initAudio() {
  if (!audioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
}

function startAmbientDrone() {
  initAudio();
  if (ambientDroneNode) return;

  const osc1 = audioCtx.createOscillator();
  const osc2 = audioCtx.createOscillator();
  ambientGainNode = audioCtx.createGain();
  const filter = audioCtx.createBiquadFilter();

  osc1.type = 'sawtooth';
  osc1.frequency.setValueAtTime(55, audioCtx.currentTime); // Low A

  osc2.type = 'sine';
  osc2.frequency.setValueAtTime(110, audioCtx.currentTime);

  filter.type = 'lowpass';
  filter.frequency.setValueAtTime(220, audioCtx.currentTime);

  ambientGainNode.gain.setValueAtTime(0.001, audioCtx.currentTime);
  ambientGainNode.gain.exponentialRampToValueAtTime(0.12, audioCtx.currentTime + 2);

  osc1.connect(filter);
  osc2.connect(filter);
  filter.connect(ambientGainNode);
  ambientGainNode.connect(audioCtx.destination);

  osc1.start();
  osc2.start();

  ambientDroneNode = { osc1, osc2, filter };
}

function stopAmbientDrone() {
  if (ambientGainNode && audioCtx) {
    ambientGainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.5);
    setTimeout(() => {
      if (ambientDroneNode) {
        ambientDroneNode.osc1.stop();
        ambientDroneNode.osc2.stop();
        ambientDroneNode = null;
      }
    }, 500);
  }
}

function playBeep(freq = 600, duration = 0.08, type = 'sine') {
  if (!isAudioActive) return;
  initAudio();
  try {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);

    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch (e) {}
}

if (btnSoundToggle) {
  btnSoundToggle.addEventListener('click', () => {
    isAudioActive = !isAudioActive;
    if (isAudioActive) {
      startAmbientDrone();
      btnSoundToggle.classList.add('text-cyan');
      btnSoundToggle.querySelector('.ctrl-tooltip').textContent = 'AUDIO FX: ACTIVE';
    } else {
      stopAmbientDrone();
      btnSoundToggle.classList.remove('text-cyan');
      btnSoundToggle.querySelector('.ctrl-tooltip').textContent = 'AUDIO FX: OFF';
    }
  });
}

// 6. Mission Elapsed Time (MET) & Live Telemetry Simulator (Started after Intro)
const startTime = Date.now() - (4 * 3600000 + 18 * 60000 + 22000);
let isClockRunning = false;

function updateMissionClock() {
  if (!isClockRunning) return;
  const elapsed = Date.now() - startTime;
  const hours = Math.floor(elapsed / 3600000).toString().padStart(2, '0');
  const minutes = Math.floor((elapsed % 3600000) / 60000).toString().padStart(2, '0');
  const seconds = Math.floor((elapsed % 60000) / 1000).toString().padStart(2, '0');
  const centis = Math.floor((elapsed % 1000) / 10).toString().padStart(2, '0');

  if (metClock) {
    metClock.textContent = `T+ ${hours}:${minutes}:${seconds}.${centis}`;
  }

  // Micro fluctuations in velocity
  if (valVelocity && Math.random() > 0.7) {
    const baseVel = 27480 + (Math.sin(Date.now() / 1500) * 12).toFixed(1);
    valVelocity.textContent = `${Number(baseVel).toLocaleString()} KM/H`;
  }

  // Micro fluctuations in telemetry panel
  if (dynPitch && Math.random() > 0.8) {
    const pitch = (12.4 + (Math.sin(Date.now() / 800) * 0.4)).toFixed(1);
    dynPitch.textContent = `${pitch > 0 ? '+' : ''}${pitch}°`;
  }
  if (dynYaw && Math.random() > 0.8) {
    const yaw = (-3.1 + (Math.cos(Date.now() / 900) * 0.3)).toFixed(1);
    dynYaw.textContent = `${yaw > 0 ? '+' : ''}${yaw}°`;
  }

  requestAnimationFrame(updateMissionClock);
}

function startMissionClock() {
  if (!isClockRunning) {
    isClockRunning = true;
    updateMissionClock();
  }
}

// 7. Interactive Timeline Scrubber in Reconstruction Panel
if (timelineSlider && sliderTimestamp) {
  timelineSlider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    const m = Math.floor(val / 60).toString().padStart(2, '0');
    const s = (val % 60).toString().padStart(2, '0');
    sliderTimestamp.textContent = `T+ 00:${m}:${s} (ORBIT RECON)`;
  });
}

// 8. Dynamic Sensor Waveform Visualizer (Runs only when modal is open)
let isWaveformRunning = false;
let waveformAnimId = null;

function startWaveform() {
  if (!waveformCanvas || isWaveformRunning) return;
  isWaveformRunning = true;
  const wCtx = waveformCanvas.getContext('2d');
  let waveOffset = 0;

  function drawWaveform() {
    if (!isWaveformRunning) return;
    waveformCanvas.width = waveformCanvas.parentElement.clientWidth || 300;
    waveformCanvas.height = 100;

    wCtx.fillStyle = 'rgba(0, 5, 15, 0.8)';
    wCtx.fillRect(0, 0, waveformCanvas.width, waveformCanvas.height);

    wCtx.strokeStyle = 'rgba(0, 242, 254, 0.85)';
    wCtx.lineWidth = 1.5;
    wCtx.shadowBlur = 8;
    wCtx.shadowColor = '#00f2fe';

    wCtx.beginPath();
    const centerY = waveformCanvas.height / 2;
    const points = 80;
    const step = waveformCanvas.width / points;

    for (let i = 0; i <= points; i++) {
      const x = i * step;
      const noise = (Math.sin(i * 0.3 + waveOffset) + Math.cos(i * 0.8 - waveOffset * 1.5)) * 12;
      const spike = (i > 38 && i < 46) ? Math.sin((i - 38) * 0.4) * 32 : 0;
      const y = centerY + noise + spike;

      if (i === 0) wCtx.moveTo(x, y);
      else wCtx.lineTo(x, y);
    }
    wCtx.stroke();

    waveOffset += 0.04;
    waveformAnimId = requestAnimationFrame(drawWaveform);
  }

  drawWaveform();
}

function stopWaveform() {
  isWaveformRunning = false;
  if (waveformAnimId) {
    cancelAnimationFrame(waveformAnimId);
    waveformAnimId = null;
  }
}

// 9. Dynamic Starfield Warp Canvas (Synced with Main Landing Page after Intro)
let isStarfieldRunning = false;

function startStarCanvas() {
  if (!starCanvas || isStarfieldRunning) return;
  isStarfieldRunning = true;

  const sCtx = starCanvas.getContext('2d');
  let stars = [];
  const STAR_COUNT = 80;

  function resizeStarCanvas() {
    starCanvas.width = window.innerWidth;
    starCanvas.height = window.innerHeight;
    stars = Array.from({ length: STAR_COUNT }, () => ({
      x: Math.random() * starCanvas.width,
      y: Math.random() * starCanvas.height,
      size: Math.random() * 1.6 + 0.4,
      speed: Math.random() * 0.6 + 0.2,
      opacity: Math.random() * 0.8 + 0.2
    }));
  }

  function drawStars() {
    if (!isStarfieldRunning) return;
    sCtx.clearRect(0, 0, starCanvas.width, starCanvas.height);

    stars.forEach(star => {
      star.y += star.speed;
      if (star.y > starCanvas.height) {
        star.y = 0;
        star.x = Math.random() * starCanvas.width;
      }

      sCtx.fillStyle = `rgba(255, 255, 255, ${star.opacity})`;
      sCtx.shadowBlur = 4;
      sCtx.shadowColor = '#00f2fe';
      sCtx.beginPath();
      sCtx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
      sCtx.fill();
    });

    requestAnimationFrame(drawStars);
  }

  window.addEventListener('resize', resizeStarCanvas);
  resizeStarCanvas();
  drawStars();
}

// 10. Keyboard Shortcuts (ESC to close panels/cinema)
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (isCinemaMode) {
      toggleCinemaMode();
    } else {
      closeAllModals();
    }
  }
});

// 11. ClueSpace Console Integration
const cluespaceAppEl = document.getElementById('cluespace-app');
const btnOpenCluespace = document.getElementById('btn-open-cluespace');
const btnCluespaceJump = document.getElementById('btn-cluespace-jump');

async function openClueSpace() {
  isClueSpaceActive = true;
  if (scrollContainer) scrollContainer.style.display = 'none';
  if (hudHeader) {
    hudHeader.style.display = 'flex';
    hudHeader.classList.add('in-cluespace');
  }
  if (cluespaceAppEl) {
    cluespaceAppEl.style.display = 'flex';
    await ensureClueSpaceApp();
  }

  // Set active nav button
  navButtons.forEach(btn => {
    if (btn.id === 'btn-open-cluespace') {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Render Main Screen return button in top right of shared header
  if (hudNavRight) {
    hudNavRight.innerHTML = `
      <button class="cluespace-exit-btn" id="btn-header-exit" title="Return to Main Screen">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        <span>MAIN SCREEN</span>
      </button>
    `;
    const exitBtn = hudNavRight.querySelector('#btn-header-exit');
    if (exitBtn) {
      exitBtn.addEventListener('click', () => exitClueSpace('hero-section'));
    }
  }
}

function exitClueSpace(targetSection = 'hero-section') {
  isClueSpaceActive = false;
  if (cluespaceAppEl) cluespaceAppEl.style.display = 'none';
  if (scrollContainer) scrollContainer.style.display = 'block';
  if (hudHeader) {
    hudHeader.style.display = 'flex';
    hudHeader.classList.remove('in-cluespace');
  }
  if (hudNavRight) {
    hudNavRight.innerHTML = '';
  }

  if (targetSection) {
    scrollToSection(targetSection);
  }
}

if (btnOpenCluespace) {
  btnOpenCluespace.addEventListener('click', () => openClueSpace());
}

if (btnCluespaceJump) {
  btnCluespaceJump.addEventListener('click', () => openClueSpace());
}

// 12. Deep Space Void Starfield Canvas Initializer (Initialized on demand)
function initSpaceCanvas(canvasId) {
  const canvas = document.getElementById(canvasId);
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
    const parent = canvas.parentElement;
    width = parent ? parent.clientWidth : window.innerWidth;
    height = parent ? parent.clientHeight : window.innerHeight;
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

    ctx.clearRect(0, 0, width, height);

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



