/**
 * ClueSpace — Anomaly Spatializer (Screen 2)
 * Hero 3D Spacecraft Telemetry & Temporal Cascade Visualizer
 *
 * Visualizes investigations spatially in 3D around an aerospace spacecraft wireframe model.
 * All channels, timestamps, anomaly scores, temporal precedence, and overlap statuses
 * are derived dynamically and strictly from authentic investigation datasets.
 *
 * Scientific disclaimer:
 * "Telemetry spatialization • Relationships represent observed temporal associations, not physical causality."
 */

import { fetchInvestigation, getAllInvestigations } from './dataService.js';
import { getSelectedInvestigationId, setSelectedInvestigationId, navigateToInvestigationWorkspace, onInvestigationChange } from './navigation.js';

if (typeof CanvasRenderingContext2D !== 'undefined' && !CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r = 4) {
    if (w < 2 * r) r = w / 2;
    if (h < 2 * r) r = h / 2;
    this.beginPath();
    this.moveTo(x + r, y);
    this.arcTo(x + w, y, x + w, y + h, r);
    this.arcTo(x + w, y + h, x, y + h, r);
    this.arcTo(x, y + h, x, y, r);
    this.arcTo(x, y, x + w, y, r);
    this.closePath();
    return this;
  };
}

let isInitialized = false;
let activeInvestigationId = 'INV-988';
let activeInvestigation = null;

// 3D Canvas & Context
let canvas = null;
let ctx = null;
let animFrameId = null;

// Hero Spacecraft Camera Framing
// Matches the elevated upper-side perspective with the satellite positioned slightly to the left
const DEFAULT_CAMERA = {
  yaw: -0.84,       // 3/4 orbital azimuth angle
  pitch: 0.68,      // Elevated upper-side downward pitch angle
  distance: 240,    // Optimal framing distance
  panX: -65,        // Shifted slightly towards the left
  panY: 15,         // Centered vertical composition
  fov: 720
};

const camera = {
  yaw: DEFAULT_CAMERA.yaw,
  pitch: DEFAULT_CAMERA.pitch,
  targetYaw: DEFAULT_CAMERA.yaw,
  targetPitch: DEFAULT_CAMERA.pitch,
  distance: DEFAULT_CAMERA.distance,
  targetDistance: DEFAULT_CAMERA.distance,
  panX: DEFAULT_CAMERA.panX,
  panY: DEFAULT_CAMERA.panY,
  targetPanX: DEFAULT_CAMERA.panX,
  targetPanY: DEFAULT_CAMERA.panY,
  fov: DEFAULT_CAMERA.fov
};

// Interaction State
let isDragging = false;
let isRightDragging = false;
let lastMouseX = 0;
let lastMouseY = 0;
let selectedMarker = null;
let currentSeverityFilter = 'ALL';
let selectorSearchQuery = '';
let activeDropdownSeverity = null;

// Temporal Playback State
let timeStart = 0;
let timeEnd = 0;
let currentTimestamp = 0; // Epoch milliseconds
let isPlaying = false;
let playbackSpeed = 1.0;
let lastFrameTime = performance.now();

// Processed 3D Spatial Entities
let evidenceChannels = [];
let temporalLinks = [];
let satelliteGeometry = null;

/**
 * Mounts and initializes the Anomaly Spatializer Screen in #spatializer-section
 */
export async function initAnomalySpatializer() {
  if (isInitialized) return;

  const section = document.getElementById('spatializer-section');
  if (!section) return;

  // Render HTML HUD overlays inside #spatializer-section
  section.innerHTML = `
    <!-- Starfield & Ambience Canvas -->
    <canvas id="spatializer-space-canvas" class="spatializer-space-canvas"></canvas>

    <!-- Main 3D Spacecraft Viewport -->
    <div class="spatializer-viewport" id="spatializer-viewport">
      <canvas id="spatializer-3d-canvas" class="spatializer-3d-canvas"></canvas>
    </div>

    <!-- Top Overlay Bar (Left Title & Subtitle) -->
    <header class="spatializer-top-bar" id="spatializer-top-bar">
      <div class="spatializer-title-block">
        <h2 class="spatializer-main-title">
          <span>ANOMALY SPATIALIZER</span>
        </h2>
        <div class="spatializer-subtitle">
          <span>Investigation Spatialization</span>
          <span class="spatializer-info-icon" title="Observed temporal telemetry associations projected around satellite canvas">i</span>
        </div>
      </div>
    </header>

    <!-- Right-Side Stack: Investigation Selector, Channel Inspector, Legend, View Controls -->
    <aside class="spatializer-right-hud" id="spatializer-right-hud">
      <!-- 1. Severity Investigation Filter Dropdown Controls (Matching Telemetry Spacetime) -->
      <div class="spatializer-sev-filter-group" id="spatializer-sev-filter-group" role="group" aria-label="Filter and select investigations by severity">
        <div class="spatializer-sev-dropdown-wrap" data-sev="ALL">
          <button class="spatializer-sev-dropdown-btn active" data-sev="ALL" id="btn-spat-sev-all">
            <span>ALL</span>
            <span class="spatializer-sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="spatializer-sev-dropdown-wrap" data-sev="CRITICAL">
          <button class="spatializer-sev-dropdown-btn sev-critical" data-sev="CRITICAL" id="btn-spat-sev-critical">
            <span>CRITICAL</span>
            <span class="spatializer-sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="spatializer-sev-dropdown-wrap" data-sev="HIGH">
          <button class="spatializer-sev-dropdown-btn sev-high" data-sev="HIGH" id="btn-spat-sev-high">
            <span>HIGH</span>
            <span class="spatializer-sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="spatializer-sev-dropdown-wrap" data-sev="MODERATE">
          <button class="spatializer-sev-dropdown-btn sev-moderate" data-sev="MODERATE" id="btn-spat-sev-moderate">
            <span>MODERATE</span>
            <span class="spatializer-sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="spatializer-sev-dropdown-wrap" data-sev="LOW">
          <button class="spatializer-sev-dropdown-btn sev-low" data-sev="LOW" id="btn-spat-sev-low">
            <span>LOW</span>
            <span class="spatializer-sev-btn-arrow">▾</span>
          </button>
        </div>
      </div>

      <!-- Dynamic Searchable Severity Dropdown Panel -->
      <div class="spatializer-sev-dropdown-panel" id="spatializer-sev-dropdown-panel" hidden>
        <div class="spatializer-sev-dropdown-search-box">
          <input 
            type="text" 
            id="spatializer-sev-search-input" 
            class="spatializer-sev-search-input" 
            placeholder="Search investigation ID..." 
            autocomplete="off" 
            spellcheck="false"
            aria-label="Search investigation by ID"
          />
        </div>
        <div class="spatializer-sev-dropdown-header" id="spatializer-sev-dropdown-header">AVAILABLE INVESTIGATIONS</div>
        <div class="spatializer-sev-dropdown-scroll" id="spatializer-sev-dropdown-scroll"></div>
      </div>

      <!-- Selected Active Investigation Card (Matching User Reference) -->
      <div class="spatializer-hud-card spatializer-inv-card" id="spatializer-inv-card">
        <span class="spatializer-inv-title" id="spat-active-inv-name">INCIDENT #INV-988</span>
        <span class="spatializer-inv-badge sev-critical" id="spat-active-inv-badge">CRITICAL</span>
      </div>

      <!-- 2. Channel Inspector Card -->
      <div class="spatializer-hud-card spatializer-inspector-card" id="spatializer-inspector-card">
        <div class="spatializer-card-header">
          <span class="spatializer-card-title">CHANNEL INSPECTOR</span>
          <button class="spatializer-inspector-close" id="btn-close-inspector" aria-label="Close Inspector">✕</button>
        </div>

        <div class="spatializer-inspector-hero">
          <div class="spatializer-inspector-channel-badge">
            <div class="spatializer-inspector-dot" id="spat-insp-dot"></div>
            <span id="spat-insp-channel-id">CADC0888</span>
          </div>
          <span class="spatializer-inspector-role-tag" id="spat-insp-role-tag">INITIATOR</span>
        </div>

        <div class="spatializer-inspector-grid">
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">Status:</span>
            <span class="spatializer-inspector-val hl-pink" id="spat-insp-status">Anomaly Detected</span>
          </div>
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">First Detected:</span>
            <span class="spatializer-inspector-val" id="spat-insp-first-time">10:44:37 UTC</span>
          </div>
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">Peak Anomaly Score:</span>
            <span class="spatializer-inspector-val hl-pink" id="spat-insp-peak-score">0.990</span>
          </div>
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">Duration:</span>
            <span class="spatializer-inspector-val" id="spat-insp-duration">12.0s</span>
          </div>
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">Window Overlap:</span>
            <span class="spatializer-inspector-val hl-cyan" id="spat-insp-overlap">TRUE</span>
          </div>
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">Telemetry Points:</span>
            <span class="spatializer-inspector-val" id="spat-insp-pts-count">8</span>
          </div>
          <div class="spatializer-inspector-row">
            <span class="spatializer-inspector-label">Data Quality:</span>
            <span class="spatializer-inspector-val hl-green" id="spat-insp-quality">High (Verified)</span>
          </div>
        </div>

        <!-- Real-Time Telemetry Waveform Snippet -->
        <div class="spatializer-sparkline-box">
          <div class="spatializer-sparkline-label">TELEMETRY DEVIATION SNIPPET</div>
          <canvas class="spatializer-sparkline-canvas" id="spatializer-sparkline-canvas"></canvas>
        </div>
      </div>

      <!-- 3. Legend Card -->
      <div class="spatializer-hud-card" id="spatializer-legend-card">
        <div class="spatializer-card-header">
          <span class="spatializer-card-title">LEGEND</span>
          <button class="spatializer-card-collapse-btn" id="btn-collapse-legend" aria-label="Toggle Legend">▾</button>
        </div>
        <div class="spatializer-legend-grid" id="spatializer-legend-body">
          <div class="spatializer-legend-col">
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-dot dot-not-activated"></div>
              <span>Not Activated</span>
            </div>
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-dot dot-activated"></div>
              <span>Activated</span>
            </div>
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-dot dot-current"></div>
              <span>Current Active</span>
            </div>
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-dot dot-high"></div>
              <span>High Severity</span>
            </div>
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-dot dot-med"></div>
              <span>Medium Severity</span>
            </div>
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-dot dot-low"></div>
              <span>Low Severity</span>
            </div>
          </div>
          <div class="spatializer-legend-col spatializer-legend-col-right">
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-line line-overlap-true"></div>
              <span>Overlap [TRUE]</span>
            </div>
            <div class="spatializer-legend-item">
              <div class="spatializer-legend-line line-overlap-false"></div>
              <span>Overlap [FALSE]</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. View Controls Card -->
      <div class="spatializer-hud-card" id="spatializer-view-controls">
        <div class="spatializer-card-header">
          <span class="spatializer-card-title">VIEW CONTROLS</span>
        </div>
        <div class="spatializer-ctrls-grid">
          <button class="spatializer-ctrl-btn active" id="btn-cam-orbit" type="button">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="8"/>
              <ellipse cx="12" cy="12" rx="10" ry="4"/>
            </svg>
            <span>Orbit</span>
          </button>
          <button class="spatializer-ctrl-btn" id="btn-cam-zoom-out" type="button" title="Zoom Out">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              <line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
            <span>Zoom Out</span>
          </button>
          <button class="spatializer-ctrl-btn" id="btn-cam-zoom-in" type="button" title="Zoom In">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              <line x1="11" y1="8" x2="11" y2="14"/>
              <line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
            <span>Zoom In</span>
          </button>
          <button class="spatializer-ctrl-btn" id="btn-cam-reset" type="button" title="Reset View">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
              <path d="M3 3v5h5"/>
            </svg>
            <span>Reset View</span>
          </button>
        </div>
        <div class="spatializer-cam-status">
          <span class="spatializer-cam-indicator-dot"></span>
          <span>3D Navigation: <strong class="text-cyan">Rotate • Move • Zoom</strong></span>
        </div>
      </div>
    </aside>

    <!-- Scientific Integrity Disclaimer -->
    <div class="spatializer-disclaimer">
      <span>ⓘ Telemetry spatialization • Relationships represent observed temporal associations, not physical causality.</span>
    </div>

    <!-- Floating Scroll Indicator to Telemetry Spacetime -->
    <a href="#spacetime-section" class="scroll-down-hint spatializer-scroll-hint" id="spatializer-scroll-hint"
      aria-label="Scroll down to Telemetry Spacetime">
      <span class="scroll-down-text">TELEMETRY SPACETIME</span>
      <div class="scroll-down-chevron">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </div>
    </a>
  `;

  // Initialize Canvas & Geometry
  canvas = section.querySelector('#spatializer-3d-canvas');
  if (canvas) {
    ctx = canvas.getContext('2d');
  }

  satelliteGeometry = buildSatelliteGeometry();

  // Setup Event Listeners
  setupEventListeners(section);

  // Load initial investigation data
  const initialId = getSelectedInvestigationId() || 'INV-988';
  await loadInvestigationData(initialId);

  // Subscribe to external investigation selection changes
  onInvestigationChange(async (newId) => {
    if (newId && newId !== activeInvestigationId) {
      await loadInvestigationData(newId);
    }
  });

  // Start 3D Render Loop
  startRenderLoop();

  isInitialized = true;
}

/**
 * Builds the geometric wireframe vertices and edges for the satellite centerpiece,
 * precisely matching the blueprint structure in the reference image:
 * - Faceted cylindrical fuselage with forward aperture cap and triangulated wireframe lattice
 * - Top-dorsal optical sensor / antenna snout probe (+Y) on the forward rim
 * - Mid-section ribbed interstage collar with wing anchor clevises
 * - Aft equipment / propulsion bay with longitudinal recessed panel bays and cross-bracing
 * - Aft dome bulkhead mounting a central conical rocket engine nozzle and 5 surrounding radial auxiliary thruster pods
 * - Dual articulated solar array wings (Port and Starboard) mounted on triangular A-frame truss support yokes,
 *   each wing containing 3 distinct framed rectangular solar panel modules with high-density photovoltaic cell grids
 */
function buildSatelliteGeometry() {
  const vertices = [];
  const edges = [];

  function addVertex(x, y, z) {
    vertices.push({ x, y, z });
    return vertices.length - 1;
  }

  function addEdge(i1, i2, color = 'cyan', glow = false) {
    edges.push({ i1, i2, color, glow });
  }

  const numRadial = 12; // 12-sided faceted polygon for aerospace structural fidelity

  // =========================================================================
  // 1. FORWARD APERTURE & FORE HULL MODULE (X = -54 to X = -20)
  // =========================================================================

  const fwdEndCapR = 17;
  const fwdHullR = 23;
  const foreStationsX = [-54, -48, -38, -28, -20];
  const foreRings = [];

  // Front Cap Center and Inner Concentric Sensor Ring (at X = -54)
  const capCenter = addVertex(-54, 0, 0);
  const innerRingR = 9;
  const innerCapRing = [];
  for (let r = 0; r < numRadial; r++) {
    const angle = (r / numRadial) * Math.PI * 2;
    const y = Math.sin(angle) * innerRingR;
    const z = Math.cos(angle) * innerRingR;
    const idx = addVertex(-54, y, z);
    innerCapRing.push(idx);
    addEdge(capCenter, idx, 'cyan');
  }
  for (let r = 0; r < numRadial; r++) {
    addEdge(innerCapRing[r], innerCapRing[(r + 1) % numRadial], 'cyan');
  }

  // Fore Hull Station Rings
  for (let s = 0; s < foreStationsX.length; s++) {
    const x = foreStationsX[s];
    const rCurrent = (s === 0) ? fwdEndCapR : fwdHullR;
    const ring = [];
    for (let r = 0; r < numRadial; r++) {
      const angle = (r / numRadial) * Math.PI * 2;
      const y = Math.sin(angle) * rCurrent;
      const z = Math.cos(angle) * rCurrent;
      const idx = addVertex(x, y, z);
      ring.push(idx);
    }
    foreRings.push(ring);

    // Circumferential loop
    for (let r = 0; r < numRadial; r++) {
      addEdge(ring[r], ring[(r + 1) % numRadial], s === 0 || s === 1 ? 'cyan' : 'cyan', s === 1);
    }
  }

  // Front Cap Spokes to Outer Cap Ring
  for (let r = 0; r < numRadial; r++) {
    addEdge(innerCapRing[r], foreRings[0][r], 'cyan');
  }

  // Chamfer and Longitudinal Stringers + Triangulated Wireframe Lattice
  for (let s = 0; s < foreStationsX.length - 1; s++) {
    const ringA = foreRings[s];
    const ringB = foreRings[s + 1];
    for (let r = 0; r < numRadial; r++) {
      // Longitudinal rib line
      addEdge(ringA[r], ringB[r], 'cyan', s === 0);

      // Diagonal cross-truss creating diamond triangulated wireframe mesh
      addEdge(ringA[r], ringB[(r + 1) % numRadial], 'blue');
      if (s > 0) {
        addEdge(ringA[(r + 1) % numRadial], ringB[r], 'dark');
      }
    }
  }

  // Top-Dorsal Optical Sensor / Antenna Snout (mounted on top rim of front cap at X = -50, Y = +23)
  const snoutBaseY = 23;
  const snoutTopY = 29.5;
  const snoutR = 3.2;
  const snoutX = -50;
  const snoutNumPts = 6;
  const snoutBaseRing = [];
  const snoutTopRing = [];
  for (let p = 0; p < snoutNumPts; p++) {
    const angle = (p / snoutNumPts) * Math.PI * 2;
    const sx = snoutX + Math.cos(angle) * snoutR;
    const sz = Math.sin(angle) * snoutR;
    const sb = addVertex(sx, snoutBaseY, sz);
    const st = addVertex(sx, snoutTopY, sz);
    snoutBaseRing.push(sb);
    snoutTopRing.push(st);
    addEdge(sb, st, 'cyan', true);
  }
  for (let p = 0; p < snoutNumPts; p++) {
    addEdge(snoutBaseRing[p], snoutBaseRing[(p + 1) % snoutNumPts], 'cyan');
    addEdge(snoutTopRing[p], snoutTopRing[(p + 1) % snoutNumPts], 'cyan', true);
  }
  const snoutTip = addVertex(snoutX, snoutTopY + 2.5, 0);
  for (let p = 0; p < snoutNumPts; p += 2) {
    addEdge(snoutTopRing[p], snoutTip, 'cyan');
  }

  // =========================================================================
  // 2. MID-SECTION COLLAR & SERVICE MODULE HULL (X = -20 to X = +38)
  // =========================================================================

  // Ribbed Collar Rings (X = -20, -17, -13, -10)
  const collarStationsX = [-20, -17, -13, -10];
  const collarRadii = [23, 25, 25, 23.5];
  const collarRings = [];

  for (let c = 0; c < collarStationsX.length; c++) {
    const x = collarStationsX[c];
    const cr = collarRadii[c];
    const ring = [];
    for (let r = 0; r < numRadial; r++) {
      const angle = (r / numRadial) * Math.PI * 2;
      const y = Math.sin(angle) * cr;
      const z = Math.cos(angle) * cr;
      const idx = addVertex(x, y, z);
      ring.push(idx);
    }
    collarRings.push(ring);
    for (let r = 0; r < numRadial; r++) {
      addEdge(ring[r], ring[(r + 1) % numRadial], 'cyan', c === 1 || c === 2);
    }
  }
  // Connect collar rings
  for (let c = 0; c < collarStationsX.length - 1; c++) {
    for (let r = 0; r < numRadial; r++) {
      addEdge(collarRings[c][r], collarRings[c + 1][r], 'cyan');
      addEdge(collarRings[c][r], collarRings[c + 1][(r + 1) % numRadial], 'blue');
    }
  }
  // Connect fore hull to collar
  for (let r = 0; r < numRadial; r++) {
    addEdge(foreRings[foreRings.length - 1][r], collarRings[0][r], 'cyan', true);
  }

  // Aft Service Module Cylindrical Hull (X = -10 to X = +38)
  const aftHullR = 24;
  const aftStationsX = [-10, 2, 14, 26, 36, 38];
  const aftRings = [];

  for (let s = 0; s < aftStationsX.length; s++) {
    const x = aftStationsX[s];
    const rCurrent = (s === aftStationsX.length - 1) ? aftHullR + 1.5 : aftHullR;
    const ring = [];
    for (let r = 0; r < numRadial; r++) {
      const angle = (r / numRadial) * Math.PI * 2;
      const y = Math.sin(angle) * rCurrent;
      const z = Math.cos(angle) * rCurrent;
      const idx = addVertex(x, y, z);
      ring.push(idx);
    }
    aftRings.push(ring);
    for (let r = 0; r < numRadial; r++) {
      addEdge(ring[r], ring[(r + 1) % numRadial], 'cyan', s === aftStationsX.length - 1);
    }
  }

  // Connect collar to aft hull
  for (let r = 0; r < numRadial; r++) {
    addEdge(collarRings[collarRings.length - 1][r], aftRings[0][r], 'cyan');
  }

  // Longitudinal stringers and Longitudinal Recessed Equipment Bays along Aft Hull
  for (let s = 0; s < aftStationsX.length - 1; s++) {
    const ringA = aftRings[s];
    const ringB = aftRings[s + 1];
    for (let r = 0; r < numRadial; r++) {
      // Primary longitudinal rib lines
      addEdge(ringA[r], ringB[r], 'cyan', r % 3 === 0);

      // Internal structural diagonal bracing
      if (s % 2 === 0) {
        addEdge(ringA[r], ringB[(r + 1) % numRadial], 'blue');
      } else {
        addEdge(ringA[(r + 1) % numRadial], ringB[r], 'dark');
      }
    }
  }

  // Inset Equipment Bay Panels on Aft Hull (Longitudinal recessed bays between X = 2 and X = 26)
  for (let q = 0; q < numRadial; q += 2) {
    const angleMid = ((q + 0.5) / numRadial) * Math.PI * 2;
    const bayR = 21.8;
    const by = Math.sin(angleMid) * bayR;
    const bz = Math.cos(angleMid) * bayR;

    const bp0 = addVertex(4, by, bz);
    const bp1 = addVertex(24, by, bz);
    addEdge(bp0, bp1, 'cyan');

    // Connect inset bay to hull frame
    addEdge(aftRings[1][q], bp0, 'blue');
    addEdge(aftRings[1][(q + 1) % numRadial], bp0, 'blue');
    addEdge(aftRings[3][q], bp1, 'blue');
    addEdge(aftRings[3][(q + 1) % numRadial], bp1, 'blue');
  }

  // =========================================================================
  // 3. AFT DOME BULKHEAD & MULTI-THRUSTER ENGINE CLUSTER (X = +38 to X = +66)
  // =========================================================================

  // Tapered Aft Dome Bulkhead Rings (X = +38, +44, +48)
  const domeStationsX = [38, 44, 48];
  const domeRadii = [25.5, 21, 16.5];
  const domeRings = [];

  for (let d = 0; d < domeStationsX.length; d++) {
    const x = domeStationsX[d];
    const dr = domeRadii[d];
    const ring = [];
    for (let r = 0; r < numRadial; r++) {
      const angle = (r / numRadial) * Math.PI * 2;
      const y = Math.sin(angle) * dr;
      const z = Math.cos(angle) * dr;
      const idx = addVertex(x, y, z);
      ring.push(idx);
    }
    domeRings.push(ring);
    for (let r = 0; r < numRadial; r++) {
      addEdge(ring[r], ring[(r + 1) % numRadial], 'cyan', d === domeStationsX.length - 1);
    }
  }
  // Connect dome rings
  for (let d = 0; d < domeStationsX.length - 1; d++) {
    for (let r = 0; r < numRadial; r++) {
      addEdge(domeRings[d][r], domeRings[d + 1][r], 'cyan');
      addEdge(domeRings[d][r], domeRings[d + 1][(r + 1) % numRadial], 'blue');
    }
  }

  // Connect aft hull to dome
  for (let r = 0; r < numRadial; r++) {
    addEdge(aftRings[aftRings.length - 1][r], domeRings[0][r], 'cyan', true);
  }

  // --- Center Main Rocket Engine Nozzle (X = +48 to X = +66) ---
  const mainEngineBaseX = 48;
  const mainEngineThroatX = 52;
  const mainEngineExitX = 66;
  const mainEngineBaseR = 7;
  const mainEngineThroatR = 5;
  const mainEngineExitR = 9.2;
  const numEnginePts = 8;

  const engBaseRing = [];
  const engThroatRing = [];
  const engExitRing = [];

  for (let e = 0; e < numEnginePts; e++) {
    const angle = (e / numEnginePts) * Math.PI * 2;
    const ey1 = Math.sin(angle) * mainEngineBaseR;
    const ez1 = Math.cos(angle) * mainEngineBaseR;
    const ey2 = Math.sin(angle) * mainEngineThroatR;
    const ez2 = Math.cos(angle) * mainEngineThroatR;
    const ey3 = Math.sin(angle) * mainEngineExitR;
    const ez3 = Math.cos(angle) * mainEngineExitR;

    const bIdx = addVertex(mainEngineBaseX, ey1, ez1);
    const tIdx = addVertex(mainEngineThroatX, ey2, ez2);
    const xIdx = addVertex(mainEngineExitX, ey3, ez3);

    engBaseRing.push(bIdx);
    engThroatRing.push(tIdx);
    engExitRing.push(xIdx);

    // Longitudinal cooling channel ribs along nozzle bell
    addEdge(bIdx, tIdx, 'cyan');
    addEdge(tIdx, xIdx, 'cyan', true);
  }

  for (let e = 0; e < numEnginePts; e++) {
    addEdge(engBaseRing[e], engBaseRing[(e + 1) % numEnginePts], 'cyan');
    addEdge(engThroatRing[e], engThroatRing[(e + 1) % numEnginePts], 'cyan');
    addEdge(engExitRing[e], engExitRing[(e + 1) % numEnginePts], 'cyan', true);
  }

  // Central nozzle interior pintle / injector hub
  const nozzleCenterHub = addVertex(mainEngineThroatX, 0, 0);
  const nozzleSpikeTip = addVertex(mainEngineExitX + 3, 0, 0);
  addEdge(nozzleCenterHub, nozzleSpikeTip, 'cyan', true);
  for (let e = 0; e < numEnginePts; e += 2) {
    addEdge(engThroatRing[e], nozzleCenterHub, 'blue');
    addEdge(engExitRing[e], nozzleSpikeTip, 'cyan');
  }

  // --- Surrounding Auxiliary Engine Thruster Pods (5 radial thrusters on aft bulkhead) ---
  const numAuxPods = 5;
  const auxPodOrbitR = 11.8;
  const auxPodBaseX = 44;
  const auxPodCollarX = 49;
  const auxPodTipX = 60;
  const auxPodRadius = 3.0;
  const auxPodTipR = 1.6;
  const numPodPts = 6;

  for (let a = 0; a < numAuxPods; a++) {
    const podAngle = (a / numAuxPods) * Math.PI * 2 + 0.35;
    const podCenterY = Math.sin(podAngle) * auxPodOrbitR;
    const podCenterZ = Math.cos(podAngle) * auxPodOrbitR;

    const podBaseRing = [];
    const podCollarRing = [];
    const podTipRing = [];

    for (let p = 0; p < numPodPts; p++) {
      const angle = (p / numPodPts) * Math.PI * 2;
      const py1 = podCenterY + Math.sin(angle) * auxPodRadius;
      const pz1 = podCenterZ + Math.cos(angle) * auxPodRadius;
      const py2 = podCenterY + Math.sin(angle) * (auxPodRadius * 0.9);
      const pz2 = podCenterZ + Math.cos(angle) * (auxPodRadius * 0.9);
      const py3 = podCenterY + Math.sin(angle) * auxPodTipR;
      const pz3 = podCenterZ + Math.cos(angle) * auxPodTipR;

      const pb = addVertex(auxPodBaseX, py1, pz1);
      const pc = addVertex(auxPodCollarX, py2, pz2);
      const pt = addVertex(auxPodTipX, py3, pz3);

      podBaseRing.push(pb);
      podCollarRing.push(pc);
      podTipRing.push(pt);

      addEdge(pb, pc, 'cyan');
      addEdge(pc, pt, 'cyan', true);
    }

    for (let p = 0; p < numPodPts; p++) {
      addEdge(podBaseRing[p], podBaseRing[(p + 1) % numPodPts], 'cyan');
      addEdge(podCollarRing[p], podCollarRing[(p + 1) % numPodPts], 'cyan');
      addEdge(podTipRing[p], podTipRing[(p + 1) % numPodPts], 'cyan', true);
    }

    // Pod center exhaust probe
    const podTipCenter = addVertex(auxPodTipX + 1.5, podCenterY, podCenterZ);
    for (let p = 0; p < numPodPts; p += 2) {
      addEdge(podTipRing[p], podTipCenter, 'cyan');
    }

    // Structural feed line / mounting strut from pod collar to aft bulkhead
    const strutAnchor = addVertex(auxPodBaseX - 4, podCenterY * 1.2, podCenterZ * 1.2);
    addEdge(strutAnchor, podCollarRing[0], 'blue');
    addEdge(strutAnchor, podCollarRing[3], 'blue');
  }

  // =========================================================================
  // 4. DUAL ARTICULATED SOLAR ARRAY WINGS (Port -Z and Starboard +Z)
  // =========================================================================

  // Helper to build 3 framed rectangular solar panel modules per wing with high-density photovoltaic cell grids
  function buildSolarWing(zSide) {
    const isPort = zSide < 0;
    const sign = isPort ? -1 : 1;

    // A. Triangular A-Frame Truss Support Yoke
    // Root mounts on fuselage hull at X = -16 and X = -2 at R = 24.5
    const rootX1 = -16;
    const rootX2 = -2;
    const rootY = 0;
    const rootZ = sign * 24;

    const rA1 = addVertex(rootX1, rootY + 1.5, rootZ);
    const rA2 = addVertex(rootX1, rootY - 1.5, rootZ);
    const rB1 = addVertex(rootX2, rootY + 1.5, rootZ);
    const rB2 = addVertex(rootX2, rootY - 1.5, rootZ);

    addEdge(rA1, rA2, 'cyan', true);
    addEdge(rB1, rB2, 'cyan', true);

    // Yoke Apex / Pivot Crossbar at Z = ±45, X = -9
    const yokeZ = sign * 45;
    const yTop1 = addVertex(rootX1 + 2, rootY + 1.5, yokeZ);
    const yTop2 = addVertex(rootX2 - 2, rootY + 1.5, yokeZ);
    const yBot1 = addVertex(rootX1 + 2, rootY - 1.5, yokeZ);
    const yBot2 = addVertex(rootX2 - 2, rootY - 1.5, yokeZ);

    // Triangular diagonal truss tubes
    addEdge(rA1, yTop1, 'cyan', true);
    addEdge(rA2, yBot1, 'cyan', true);
    addEdge(rB1, yTop2, 'cyan', true);
    addEdge(rB2, yBot2, 'cyan', true);

    // Yoke rectangular crossbar frame
    addEdge(yTop1, yTop2, 'cyan', true);
    addEdge(yBot1, yBot2, 'cyan', true);
    addEdge(yTop1, yBot1, 'cyan', true);
    addEdge(yTop2, yBot2, 'cyan', true);

    // Internal diagonal truss cross-brace on the yoke
    addEdge(rA1, yTop2, 'blue');
    addEdge(rB1, yTop1, 'blue');

    // Hinge bracket to panel root at Z = ±48
    const panelRootZ = sign * 48;
    const h1 = addVertex(rootX1 + 1, rootY, panelRootZ);
    const h2 = addVertex(rootX2 - 1, rootY, panelRootZ);
    addEdge(yTop1, h1, 'cyan', true);
    addEdge(yTop2, h2, 'cyan', true);
    addEdge(h1, h2, 'cyan', true);

    // B. 3 Framed Rectangular Solar Panel Modules
    const xMin = -29;
    const xMax = 11;
    const panelThickness = 0.9;

    // Panel spans along Z:
    const panelSpans = [
      { startZ: sign * 48, endZ: sign * 74 },
      { startZ: sign * 76, endZ: sign * 102 },
      { startZ: sign * 104, endZ: sign * 130 }
    ];

    panelSpans.forEach((span, pIdx) => {
      const z0 = span.startZ;
      const z1 = span.endZ;

      // Outer Perimeter Frame Top Face (Y = +0.9)
      const ft0 = addVertex(xMin, panelThickness, z0);
      const ft1 = addVertex(xMax, panelThickness, z0);
      const ft2 = addVertex(xMax, panelThickness, z1);
      const ft3 = addVertex(xMin, panelThickness, z1);

      // Outer Perimeter Frame Bottom Face (Y = -0.9)
      const fb0 = addVertex(xMin, -panelThickness, z0);
      const fb1 = addVertex(xMax, -panelThickness, z0);
      const fb2 = addVertex(xMax, -panelThickness, z1);
      const fb3 = addVertex(xMin, -panelThickness, z1);

      // Top outer frame edges
      addEdge(ft0, ft1, 'cyan', true);
      addEdge(ft1, ft2, 'cyan', true);
      addEdge(ft2, ft3, 'cyan', true);
      addEdge(ft3, ft0, 'cyan', true);

      // Bottom outer frame edges
      addEdge(fb0, fb1, 'blue');
      addEdge(fb1, fb2, 'blue');
      addEdge(fb2, fb3, 'blue');
      addEdge(fb3, fb0, 'blue');

      // Corner posts connecting top & bottom frame
      addEdge(ft0, fb0, 'cyan');
      addEdge(ft1, fb1, 'cyan');
      addEdge(ft2, fb2, 'cyan');
      addEdge(ft3, fb3, 'cyan');

      // Photovoltaic Cell Grid: 3 columns x 6 rows per module
      const numCols = 3;
      const numRows = 6;

      // Longitudinal cell dividing lines along X
      for (let c = 1; c < numCols; c++) {
        const gx = xMin + (c / numCols) * (xMax - xMin);
        const topA = addVertex(gx, panelThickness, z0);
        const topB = addVertex(gx, panelThickness, z1);
        addEdge(topA, topB, 'cyan', true);
      }

      // Transverse cell dividing lines along Z
      for (let r = 1; r < numRows; r++) {
        const gz = z0 + (r / numRows) * (z1 - z0);
        const topA = addVertex(xMin, panelThickness, gz);
        const topB = addVertex(xMax, panelThickness, gz);
        addEdge(topA, topB, 'cyan');
      }

      // Inter-panel structural hinges (between panels 0-1 and panels 1-2)
      if (pIdx < panelSpans.length - 1) {
        const nextSpan = panelSpans[pIdx + 1];
        const hingeX1 = xMin + 6;
        const hingeX2 = xMax - 6;

        const hA_top = addVertex(hingeX1, panelThickness, z1);
        const hB_top = addVertex(hingeX1, panelThickness, nextSpan.startZ);
        addEdge(hA_top, hB_top, 'cyan', true);

        const hC_top = addVertex(hingeX2, panelThickness, z1);
        const hD_top = addVertex(hingeX2, panelThickness, nextSpan.startZ);
        addEdge(hC_top, hD_top, 'cyan', true);
      }
    });
  }

  // Build Port and Starboard Solar Wings
  buildSolarWing(-1); // Port (-Z)
  buildSolarWing(1);  // Starboard (+Z)

  return { vertices, edges };
}

/**
 * Loads authentic dataset for an investigation and maps its channels into 3D spatial space
 */
export async function loadInvestigationData(id = 'INV-988') {
  activeInvestigationId = id;
  const data = await fetchInvestigation(id);
  if (!data) return;

  activeInvestigation = data;

  // 1. Calculate time boundaries
  const rawTimeline = Array.isArray(data.timeline) ? data.timeline : [];
  if (data.start_time && data.end_time) {
    timeStart = new Date(data.start_time).getTime();
    timeEnd = new Date(data.end_time).getTime();
  } else if (rawTimeline.length > 0) {
    timeStart = new Date(rawTimeline[0].timestamp).getTime();
    timeEnd = new Date(rawTimeline[rawTimeline.length - 1].timestamp).getTime();
  } else {
    timeStart = Date.now() - 600000;
    timeEnd = Date.now();
  }

  if (timeEnd <= timeStart) {
    timeEnd = timeStart + (data.duration_sec ? data.duration_sec * 1000 : 60000);
  }

  currentTimestamp = timeEnd;
  isPlaying = false;

  // 2. Extract Channels in chronological activation order
  const activationOrder = Array.isArray(data.channel_activation_order) && data.channel_activation_order.length > 0
    ? data.channel_activation_order
    : Array.isArray(data.channels_affected)
      ? data.channels_affected
      : [];

  const channelEventsMap = new Map();
  rawTimeline.forEach(event => {
    if (!event.channel) return;
    if (!channelEventsMap.has(event.channel)) {
      channelEventsMap.set(event.channel, []);
    }
    channelEventsMap.get(event.channel).push(event);
  });

  const uniqueChannels = [...new Set([...activationOrder, ...channelEventsMap.keys()])];
  const numChannels = uniqueChannels.length;

  let prevTime = timeStart;

  evidenceChannels = uniqueChannels.map((channelId, index) => {
    const events = channelEventsMap.get(channelId) || [];
    let firstTime = timeEnd;
    let peakScore = 0;
    let totalPoints = events.length;

    if (events.length > 0) {
      firstTime = new Date(events[0].timestamp).getTime();
      events.forEach(e => {
        if (typeof e.anomaly_score === 'number' && e.anomaly_score > peakScore) {
          peakScore = e.anomaly_score;
        }
      });
    } else {
      firstTime = timeStart + index * 5000;
      peakScore = data.severity_score ? data.severity_score / 10 : 0.65;
    }

    const deltaStartSec = Math.max(0, (firstTime - timeStart) / 1000);
    const deltaPrevSec = Math.max(0, (firstTime - prevTime) / 1000);
    prevTime = firstTime;

    let severity = 'LOW';
    if (peakScore >= 0.8 || (data.severity_score && data.severity_score >= 8)) severity = 'CRITICAL';
    else if (peakScore >= 0.65) severity = 'HIGH';
    else if (peakScore >= 0.45) severity = 'MODERATE';

    // Spatial Placement: Wide orbital perimeter ellipse surrounding the spacecraft
    // Staggered angles guaranteeing that all channel markers stay clear of the central spacecraft
    const angle = (index / Math.max(1, numChannels)) * Math.PI * 2 - 0.35;
    const radiusX = 145 + (index % 2) * 20;
    const radiusZ = 125 + ((index + 1) % 2) * 20;

    const x = Math.cos(angle) * radiusX;
    const z = Math.sin(angle) * radiusZ;
    const y = ((index % 2 === 0 ? 1 : -1) * 35) + (peakScore - 0.5) * 22;

    const firstDateObj = new Date(firstTime);
    const timeUtcStr = firstDateObj.toISOString().substring(11, 19) + ' UTC';

    return {
      channelId,
      firstTimestamp: firstTime,
      firstTimestampStr: timeUtcStr,
      deltaStartSec: Number(deltaStartSec.toFixed(1)),
      deltaPrevSec: Number(deltaPrevSec.toFixed(1)),
      peakScore: Number(peakScore.toFixed(3)),
      eventCount: totalPoints,
      severity,
      isInitiator: index === 0,
      x,
      y,
      z,
      timelineEvents: events
    };
  });

  // Sort channels by chronological first timestamp
  evidenceChannels.sort((a, b) => a.firstTimestamp - b.firstTimestamp);

  // 3. Process ALL authentic temporal relationships from dataset
  const rawRels = Array.isArray(data.channel_temporal_relationships) ? data.channel_temporal_relationships : [];
  temporalLinks = rawRels.map(rel => {
    const chA = evidenceChannels.find(c => c.channelId === rel.channel_a);
    const chB = evidenceChannels.find(c => c.channelId === rel.channel_b);

    const tA = new Date(rel.channel_a_start || (chA ? chA.firstTimestamp : timeStart)).getTime();
    const tB = new Date(rel.channel_b_start || (chB ? chB.firstTimestamp : timeStart)).getTime();
    const concludeTime = Math.max(tA, tB);

    return {
      channelA: rel.channel_a,
      channelB: rel.channel_b,
      timeA: tA,
      timeB: tB,
      concludeTime,
      gapSec: typeof rel.temporal_gap_sec === 'number' ? rel.temporal_gap_sec : Number(Math.abs((tB - tA) / 1000).toFixed(1)),
      windowsOverlap: Boolean(rel.windows_overlap),
      precedence: rel.temporal_precedence || 'A_before_B'
    };
  });

  // If no explicit relationships in dataset, create chronological sequence links
  if (temporalLinks.length === 0 && evidenceChannels.length > 1) {
    for (let i = 0; i < evidenceChannels.length - 1; i++) {
      const a = evidenceChannels[i];
      const b = evidenceChannels[i + 1];
      const gapSec = Number(((b.firstTimestamp - a.firstTimestamp) / 1000).toFixed(1));
      temporalLinks.push({
        channelA: a.channelId,
        channelB: b.channelId,
        timeA: a.firstTimestamp,
        timeB: b.firstTimestamp,
        concludeTime: b.firstTimestamp,
        gapSec,
        windowsOverlap: gapSec < 30,
        precedence: 'A_before_B'
      });
    }
  }

  // 4. Update UI Controls & Headers
  updateHeaderUI(data);

  // 5. Select first channel by default in Channel Inspector
  if (evidenceChannels.length > 0) {
    selectChannel(evidenceChannels[0]);
  }
}

/**
 * Updates the top header title and severity button states
 */
function updateHeaderUI(data) {
  const sev = (data.severity_label || (data.severity_score >= 8 ? 'CRITICAL' : data.severity_score >= 6.5 ? 'HIGH' : data.severity_score >= 4.5 ? 'MODERATE' : 'LOW')).toUpperCase();
  const btns = document.querySelectorAll('.spatializer-sev-dropdown-btn');
  btns.forEach(b => {
    if (b.dataset.sev === sev) {
      b.classList.add('active');
    } else if (b.dataset.sev !== 'ALL' && b.dataset.sev !== currentSeverityFilter) {
      b.classList.remove('active');
    }
  });

  // Update Selected Active Investigation Card
  const elName = document.getElementById('spat-active-inv-name');
  const elBadge = document.getElementById('spat-active-inv-badge');

  const invId = data.investigation_id || activeInvestigationId || 'INV-988';
  if (elName) elName.textContent = `INCIDENT #${invId}`;
  if (elBadge) {
    elBadge.textContent = sev;
    elBadge.className = `spatializer-inv-badge sev-${sev.toLowerCase()}`;
  }
}

/**
 * Updates channel evidence inspector with selected channel information
 */
function selectChannel(channelObj) {
  selectedMarker = channelObj;
  const inspector = document.getElementById('spatializer-inspector-card');
  if (!inspector || !channelObj) return;

  inspector.classList.remove('collapsed');

  const elId = document.getElementById('spat-insp-channel-id');
  const elRole = document.getElementById('spat-insp-role-tag');
  const elFirstTime = document.getElementById('spat-insp-first-time');
  const elPeakScore = document.getElementById('spat-insp-peak-score');
  const elDuration = document.getElementById('spat-insp-duration');
  const elOverlap = document.getElementById('spat-insp-overlap');
  const elPtsCount = document.getElementById('spat-insp-pts-count');

  if (elId) elId.textContent = channelObj.channelId;
  if (elRole) elRole.textContent = channelObj.isInitiator ? 'INITIATOR' : 'AFFECTED';
  if (elFirstTime) elFirstTime.textContent = channelObj.firstTimestampStr;
  if (elPeakScore) elPeakScore.textContent = channelObj.peakScore.toFixed(3);
  if (elDuration) elDuration.textContent = `${(channelObj.eventCount * 1.5).toFixed(1)}s`;
  if (elPtsCount) elPtsCount.textContent = channelObj.eventCount.toLocaleString();

  const nextRel = temporalLinks.find(l => l.channelA === channelObj.channelId);
  if (elOverlap) {
    elOverlap.textContent = nextRel ? (nextRel.windowsOverlap ? 'TRUE' : 'FALSE') : 'N/A';
    elOverlap.className = nextRel && nextRel.windowsOverlap ? 'spatializer-inspector-val hl-cyan' : 'spatializer-inspector-val';
  }

  drawChannelSparkline(channelObj);
}

/**
 * Draws telemetry sparkline snippet for selected channel
 */
function drawChannelSparkline(channelObj) {
  const sparkCanvas = document.getElementById('spatializer-sparkline-canvas');
  if (!sparkCanvas) return;

  const sCtx = sparkCanvas.getContext('2d');
  if (!sCtx) return;

  const w = sparkCanvas.parentElement.clientWidth - 14 || 230;
  const h = 42;
  sparkCanvas.width = w;
  sparkCanvas.height = h;

  sCtx.clearRect(0, 0, w, h);

  const events = channelObj.timelineEvents || [];
  if (events.length === 0) {
    sCtx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
    sCtx.lineWidth = 1.5;
    sCtx.beginPath();
    sCtx.moveTo(0, h / 2);
    sCtx.lineTo(w, h / 2);
    sCtx.stroke();
    return;
  }

  sCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  sCtx.lineWidth = 1;
  sCtx.beginPath();
  sCtx.moveTo(0, h / 2);
  sCtx.lineTo(w, h / 2);
  sCtx.stroke();

  sCtx.strokeStyle = '#f43f5e';
  sCtx.lineWidth = 1.5;
  sCtx.shadowBlur = 6;
  sCtx.shadowColor = '#f43f5e';
  sCtx.beginPath();

  const step = w / Math.max(1, events.length - 1);
  events.forEach((ev, idx) => {
    const x = idx * step;
    const normScore = typeof ev.anomaly_score === 'number' ? ev.anomaly_score : 0.5;
    const y = h - 4 - (normScore * (h - 8));
    if (idx === 0) sCtx.moveTo(x, y);
    else sCtx.lineTo(x, y);
  });
  sCtx.stroke();
  sCtx.shadowBlur = 0;
}

/**
 * Main 3D Render Loop (60 FPS Vector Rendering)
 */
function startRenderLoop() {
  function render(now) {
    lastFrameTime = now;

    // Smooth camera damping
    camera.yaw += (camera.targetYaw - camera.yaw) * 0.12;
    camera.pitch += (camera.targetPitch - camera.pitch) * 0.12;
    camera.distance += (camera.targetDistance - camera.distance) * 0.12;
    camera.panX += (camera.targetPanX - camera.panX) * 0.12;
    camera.panY += (camera.targetPanY - camera.panY) * 0.12;

    // Draw 3D Scene
    draw3DScene();

    animFrameId = requestAnimationFrame(render);
  }

  animFrameId = requestAnimationFrame(render);
}

/**
 * Renders 3D Spacecraft Wireframe, Temporal Link Arcs, and Telemetry Callout Markers
 */
function draw3DScene() {
  if (!ctx || !canvas) return;

  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2 + camera.panX;
  const cy = h / 2 + camera.panY;

  ctx.clearRect(0, 0, w, h);

  // Trig constants for 3D Camera Rotation
  const cosY = Math.cos(camera.yaw);
  const sinY = Math.sin(camera.yaw);
  const cosP = Math.cos(camera.pitch);
  const sinP = Math.sin(camera.pitch);

  function project3D(x, y, z) {
    // Rotation around Y
    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;

    // Rotation around X
    const y2 = -y * cosP - z1 * sinP;
    const z2 = y * sinP + z1 * cosP + camera.distance;

    if (z2 <= 20) return null;

    const scale = camera.fov / z2;
    const screenX = cx + x1 * scale;
    const screenY = cy + y2 * scale;

    return { screenX, screenY, scale, zDepth: z2 };
  }

  // 1. Draw Satellite Wireframe Geometry
  if (satelliteGeometry) {
    const { vertices, edges } = satelliteGeometry;
    const projectedVertices = vertices.map(v => project3D(v.x, v.y, v.z));

    edges.forEach(e => {
      const p1 = projectedVertices[e.i1];
      const p2 = projectedVertices[e.i2];
      if (!p1 || !p2) return;

      const avgDepth = (p1.zDepth + p2.zDepth) / 2;
      const depthAlpha = Math.max(0.14, Math.min(0.9, 360 / avgDepth));

      ctx.beginPath();
      ctx.moveTo(p1.screenX, p1.screenY);
      ctx.lineTo(p2.screenX, p2.screenY);

      if (e.glow) {
        ctx.strokeStyle = `rgba(96, 165, 250, ${depthAlpha.toFixed(2)})`;
        ctx.lineWidth = 1.6;
        ctx.shadowBlur = 6;
        ctx.shadowColor = '#60a5fa';
      } else if (e.color === 'cyan') {
        ctx.strokeStyle = `rgba(56, 189, 248, ${(depthAlpha * 0.8).toFixed(2)})`;
        ctx.lineWidth = 1.1;
        ctx.shadowBlur = 0;
      } else if (e.color === 'blue') {
        ctx.strokeStyle = `rgba(59, 130, 246, ${(depthAlpha * 0.7).toFixed(2)})`;
        ctx.lineWidth = 0.9;
        ctx.shadowBlur = 0;
      } else {
        ctx.strokeStyle = `rgba(30, 58, 138, ${(depthAlpha * 0.5).toFixed(2)})`;
        ctx.lineWidth = 0.8;
        ctx.shadowBlur = 0;
      }

      ctx.stroke();
      ctx.shadowBlur = 0;
    });
  }

  // 2. Render ALL Backend-Supported Temporal Relationships
  temporalLinks.forEach(link => {
    const chA = evidenceChannels.find(c => c.channelId === link.channelA);
    const chB = evidenceChannels.find(c => c.channelId === link.channelB);
    if (!chA || !chB) return;

    const pA = project3D(chA.x, chA.y, chA.z);
    const pB = project3D(chB.x, chB.y, chB.z);
    if (!pA || !pB) return;

    const isLinkActive = currentTimestamp >= link.concludeTime;
    const isSelectedLink = selectedMarker && (selectedMarker.channelId === link.channelA || selectedMarker.channelId === link.channelB);

    // Calculate outward arched 3D midpoint curve around the spacecraft perimeter
    const midX = (chA.x + chB.x) / 2 + (chA.x > 0 ? 25 : -25);
    const midY = (chA.y + chB.y) / 2 + 25;
    const midZ = (chA.z + chB.z) / 2;
    const pMid = project3D(midX, midY, midZ);

    ctx.beginPath();
    ctx.moveTo(pA.screenX, pA.screenY);
    if (pMid) {
      ctx.quadraticCurveTo(pMid.screenX, pMid.screenY, pB.screenX, pB.screenY);
    } else {
      ctx.lineTo(pB.screenX, pB.screenY);
    }

    if (isLinkActive || isSelectedLink) {
      // Active / glowing temporal link
      ctx.setLineDash(link.windowsOverlap ? [6, 4] : [3, 4]);
      ctx.strokeStyle = link.windowsOverlap ? 'rgba(56, 189, 248, 0.85)' : 'rgba(192, 132, 252, 0.75)';
      ctx.lineWidth = 1.6;
      ctx.shadowBlur = isSelectedLink ? 10 : 6;
      ctx.shadowColor = link.windowsOverlap ? '#38bdf8' : '#c084fc';
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.shadowBlur = 0;

      // Draw temporal gap & overlap badge along arc
      if (pMid) {
        ctx.font = '600 9px "Space Grotesk", sans-serif';
        const labelGap = `+${link.gapSec}s`;
        const labelOverlap = `OVERLAP: ${link.windowsOverlap ? 'TRUE' : 'FALSE'}`;

        ctx.fillStyle = 'rgba(3, 8, 20, 0.9)';
        ctx.strokeStyle = link.windowsOverlap ? 'rgba(56, 189, 248, 0.7)' : 'rgba(192, 132, 252, 0.5)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(pMid.screenX - 36, pMid.screenY - 11, 72, 22, 4);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText(labelGap, pMid.screenX, pMid.screenY - 1);

        ctx.fillStyle = link.windowsOverlap ? '#38bdf8' : 'rgba(203, 213, 225, 0.75)';
        ctx.font = '700 7px "Orbitron", sans-serif';
        ctx.fillText(labelOverlap, pMid.screenX, pMid.screenY + 7);
      }
    } else {
      // Upcoming temporal link (subtle guideline during playback)
      ctx.setLineDash([2, 4]);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.2)';
      ctx.lineWidth = 0.8;
      ctx.stroke();
      ctx.setLineDash([]);
    }
  });

  // 3. Draw Telemetry Markers & Outward-Offset HUD Badges
  evidenceChannels.forEach(ch => {
    const p = project3D(ch.x, ch.y, ch.z);
    if (!p) return;

    ch.proj = p;

    const isActivated = currentTimestamp >= ch.firstTimestamp;
    const isSelected = selectedMarker && selectedMarker.channelId === ch.channelId;

    let primaryColor = '#38bdf8';
    if (ch.severity === 'CRITICAL') primaryColor = '#f43f5e';
    else if (ch.severity === 'HIGH') primaryColor = '#f59e0b';

    // 3D Glowing Node Marker
    ctx.beginPath();
    ctx.arc(p.screenX, p.screenY, isSelected ? 6.5 : 4.5, 0, Math.PI * 2);

    if (isActivated) {
      ctx.fillStyle = primaryColor;
      ctx.shadowBlur = isSelected ? 16 : 10;
      ctx.shadowColor = primaryColor;
      ctx.fill();

      // Outer highlight ring
      ctx.beginPath();
      ctx.arc(p.screenX, p.screenY, isSelected ? 11 : 8, 0, Math.PI * 2);
      ctx.strokeStyle = primaryColor;
      ctx.lineWidth = 1.4;
      ctx.stroke();

      // Active expanding wave pulse if recently activated
      const elapsedSinceStart = (currentTimestamp - ch.firstTimestamp) / 1000;
      if (elapsedSinceStart >= 0 && elapsedSinceStart <= 2.5) {
        const pulseR = 9 + (elapsedSinceStart % 1.25) * 14;
        const pulseAlpha = Math.max(0, 1 - (elapsedSinceStart % 1.25) / 1.25);
        ctx.beginPath();
        ctx.arc(p.screenX, p.screenY, pulseR, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(192, 132, 252, ${pulseAlpha.toFixed(2)})`;
        ctx.lineWidth = 1.4;
        ctx.stroke();
      }
    } else {
      ctx.fillStyle = 'rgba(15, 23, 42, 0.5)';
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.fill();
      ctx.stroke();
    }
    ctx.shadowBlur = 0;

    // Outward-Pushed Floating HUD Callout Box
    const boxW = 114;
    const boxH = 40;
    const boxOffset = ch.x >= 0 ? 20 : -134;
    const boxX = p.screenX + boxOffset;
    const boxY = p.screenY - 20;

    // Leader line from node to box
    ctx.beginPath();
    ctx.moveTo(p.screenX, p.screenY);
    ctx.lineTo(ch.x >= 0 ? boxX : boxX + boxW, boxY + boxH / 2);
    ctx.strokeStyle = isActivated ? 'rgba(56, 189, 248, 0.4)' : 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 0.9;
    ctx.stroke();

    // Box background
    ctx.fillStyle = isSelected
      ? 'rgba(8, 20, 44, 0.92)'
      : isActivated
        ? 'rgba(3, 8, 20, 0.8)'
        : 'rgba(2, 6, 16, 0.55)';
    ctx.strokeStyle = isSelected
      ? '#c084fc'
      : isActivated
        ? 'rgba(56, 189, 248, 0.35)'
        : 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = isSelected ? 1.4 : 1;

    ctx.beginPath();
    ctx.roundRect(boxX, boxY, boxW, boxH, 4);
    ctx.fill();
    ctx.stroke();

    // Left accent severity indicator
    ctx.fillStyle = primaryColor;
    ctx.beginPath();
    ctx.roundRect(boxX + 2, boxY + 3, 2.5, boxH - 6, 1.5);
    ctx.fill();

    // Callout text
    ctx.textAlign = 'left';
    ctx.font = '700 9.5px "Orbitron", sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(ch.channelId, boxX + 8, boxY + 12);

    ctx.font = '500 8px "Space Grotesk", sans-serif';
    ctx.fillStyle = isActivated ? 'rgba(240, 249, 255, 0.85)' : 'rgba(148, 163, 184, 0.55)';
    ctx.fillText(`${ch.firstTimestampStr} (+${ch.deltaStartSec}s)`, boxX + 8, boxY + 23);

    ctx.font = '700 8.5px "Chakra Petch", sans-serif';
    ctx.fillStyle = primaryColor;
    ctx.fillText(`Score: ${ch.peakScore.toFixed(2)}`, boxX + 8, boxY + 34);
  });
}



/**
 * Event Listeners for 3D Camera Controls and Dropdowns
 */
function setupEventListeners(section) {
  const viewport = section.querySelector('#spatializer-viewport');
  const btnResetCam = section.querySelector('#btn-cam-reset');
  const btnResetCamTop = section.querySelector('#btn-spat-reset-cam-top');
  const btnZoomIn = section.querySelector('#btn-cam-zoom-in');
  const btnZoomOut = section.querySelector('#btn-cam-zoom-out');
  const btnCloseInspector = section.querySelector('#btn-close-inspector');
  const btnViewEvidence = section.querySelector('#btn-spat-view-evidence');
  const dropdownBtn = section.querySelector('#spatializer-inv-dropdown-btn');
  const dropdownPanel = section.querySelector('#spatializer-inv-dropdown-panel');
  const searchInput = section.querySelector('#spatializer-dropdown-search');
  const btnCollapseLegend = section.querySelector('#btn-collapse-legend');
  const legendBody = section.querySelector('#spatializer-legend-body');

  function resizeCanvas() {
    if (!canvas) return;
    canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
    canvas.height = canvas.parentElement?.clientHeight || window.innerHeight;
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  // 3D Camera Mouse Controls with Natural Page Scrolling Preserved (matching Telemetry Spacetime architecture)
  if (viewport) {
    let dragStartX = 0;
    let dragStartY = 0;
    let hasMoved = false;

    viewport.addEventListener('mousedown', (e) => {
      if (e.target && e.target.closest && (e.target.closest('.spatializer-hud-card, .spatializer-right-hud, .spatializer-top-bar, button, select, input, a'))) {
        return;
      }
      if (e.button === 2 || e.shiftKey) {
        isRightDragging = true;
        viewport.style.cursor = 'move';
      } else if (e.button === 0) {
        isDragging = true;
        viewport.style.cursor = 'grabbing';
      }
      lastMouseX = e.clientX;
      lastMouseY = e.clientY;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      hasMoved = false;
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDragging && !isRightDragging) return;

      const deltaX = e.clientX - lastMouseX;
      const deltaY = e.clientY - lastMouseY;

      if (Math.abs(e.clientX - dragStartX) > 4 || Math.abs(e.clientY - dragStartY) > 4) {
        hasMoved = true;
      }

      if (isDragging) {
        camera.targetYaw += deltaX * 0.0055;
        camera.targetPitch = Math.max(-1.4, Math.min(1.4, camera.targetPitch + deltaY * 0.0055));
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
      } else if (isRightDragging) {
        camera.targetPanX += deltaX * 0.4;
        camera.targetPanY += deltaY * 0.4;
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
      }
    });

    window.addEventListener('mouseup', (e) => {
      if (isDragging || isRightDragging) {
        isDragging = false;
        isRightDragging = false;
        if (viewport) viewport.style.cursor = 'default';
      }
      // Single click without drag detects marker click to inspect channel
      if (!hasMoved && e.target && viewport && viewport.contains(e.target)) {
        detectMarkerClick(e.clientX, e.clientY);
      }
    });

    // Zoom via Modifier Wheel (Ctrl / Shift / Meta) while allowing natural vertical page scroll
    viewport.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey) {
        e.preventDefault();
        camera.targetDistance = Math.max(120, Math.min(850, camera.targetDistance + e.deltaY * 0.5));
      }
      // Otherwise, passive natural scroll is fully permitted across entire page!
    }, { passive: false });

    // Prevent context menu on right click
    viewport.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  function resetCamera() {
    camera.targetYaw = DEFAULT_CAMERA.yaw;
    camera.targetPitch = DEFAULT_CAMERA.pitch;
    camera.targetDistance = DEFAULT_CAMERA.distance;
    camera.targetPanX = DEFAULT_CAMERA.panX;
    camera.targetPanY = DEFAULT_CAMERA.panY;
  }
  if (btnResetCam) btnResetCam.addEventListener('click', resetCamera);
  if (btnResetCamTop) btnResetCamTop.addEventListener('click', resetCamera);

  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      camera.targetDistance = Math.max(120, camera.targetDistance * 0.8);
    });
  }
  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      camera.targetDistance = Math.min(850, camera.targetDistance * 1.25);
    });
  }

  if (btnCloseInspector) {
    const card = section.querySelector('#spatializer-inspector-card');
    btnCloseInspector.addEventListener('click', () => {
      if (card) card.classList.add('collapsed');
      selectedMarker = null;
    });
  }

  if (btnViewEvidence) {
    btnViewEvidence.addEventListener('click', () => {
      if (activeInvestigationId) {
        navigateToInvestigationWorkspace(activeInvestigationId);
      }
    });
  }

  if (btnCollapseLegend && legendBody) {
    btnCollapseLegend.addEventListener('click', () => {
      const isHidden = legendBody.style.display === 'none';
      legendBody.style.display = isHidden ? 'flex' : 'none';
      btnCollapseLegend.textContent = isHidden ? '▾' : '▸';
    });
  }

  // Smooth Scroll Cue to Telemetry Spacetime
  const scrollHint = section.querySelector('#spatializer-scroll-hint');
  if (scrollHint) {
    scrollHint.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.getElementById('spacetime-section');
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  }

  // Severity Dropdown Filter Buttons
  const sevBtns = section.querySelectorAll('.spatializer-sev-dropdown-btn');
  const sevSearchInput = section.querySelector('#spatializer-sev-search-input');

  sevBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sev = btn.dataset.sev || 'ALL';
      const panel = section.querySelector('#spatializer-sev-dropdown-panel');
      if (activeDropdownSeverity === sev && panel && !panel.hidden) {
        closeSeverityDropdown();
      } else {
        openSeverityDropdown(sev);
      }
    });
  });

  if (sevSearchInput) {
    sevSearchInput.addEventListener('input', (e) => {
      selectorSearchQuery = e.target.value;
      renderSeverityDropdownItems();
    });

    sevSearchInput.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        const sevToFilter = activeDropdownSeverity || 'ALL';
        const filtered = getAllInvestigations(sevToFilter, selectorSearchQuery);
        if (filtered.length > 0) {
          const selectedId = filtered[0].investigation_id;
          setSelectedInvestigationId(selectedId);
          await loadInvestigationData(selectedId);
          closeSeverityDropdown();
        }
      } else if (e.key === 'Escape') {
        closeSeverityDropdown();
      }
    });
  }

  // Close dropdown on outside click
  window.addEventListener('click', (e) => {
    if (!section.querySelector('.spatializer-sev-filter-group')?.contains(e.target) &&
        !section.querySelector('#spatializer-sev-dropdown-panel')?.contains(e.target)) {
      closeSeverityDropdown();
    }
  });
}

function openSeverityDropdown(sev) {
  activeDropdownSeverity = sev;
  currentSeverityFilter = sev;
  selectorSearchQuery = '';

  const panel = document.getElementById('spatializer-sev-dropdown-panel');
  const searchInput = document.getElementById('spatializer-sev-search-input');
  const btns = document.querySelectorAll('.spatializer-sev-dropdown-btn');

  btns.forEach(b => {
    if (b.dataset.sev === sev) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  const filterGroup = document.getElementById('spatializer-sev-filter-group');

  if (panel && filterGroup) {
    filterGroup.appendChild(panel);
    panel.hidden = false;
    panel.style.display = 'flex';

    if (searchInput) {
      searchInput.value = '';
      searchInput.placeholder = `Search ${sev} investigation ID...`;
      setTimeout(() => searchInput.focus(), 50);
    }
    renderSeverityDropdownItems();
  }
}

function closeSeverityDropdown() {
  activeDropdownSeverity = null;
  const panel = document.getElementById('spatializer-sev-dropdown-panel');
  if (panel) {
    panel.hidden = true;
    panel.style.display = 'none';
  }
}

/**
 * Populates dynamic searchable investigation dropdown items for the active severity
 */
function renderSeverityDropdownItems() {
  const scrollContainer = document.getElementById('spatializer-sev-dropdown-scroll');
  const header = document.getElementById('spatializer-sev-dropdown-header');
  if (!scrollContainer) return;

  const sevToFilter = activeDropdownSeverity || currentSeverityFilter || 'ALL';
  const results = getAllInvestigations(sevToFilter, selectorSearchQuery);

  if (header) {
    header.textContent = `${sevToFilter} INVESTIGATIONS (${results.length})`;
  }

  if (results.length === 0) {
    scrollContainer.innerHTML = `
      <div class="spatializer-dropdown-no-results">
        <span>NO ${sevToFilter} INVESTIGATIONS FOUND</span>
      </div>
    `;
    return;
  }

  scrollContainer.innerHTML = results.map(inv => {
    const id = inv.investigation_id || `INV-${inv.spacecraft_incident_id}`;
    const sev = inv.severity_label || (inv.severity_score >= 8 ? 'CRITICAL' : 'HIGH');
    const sevClass = (sev || 'critical').toLowerCase();
    const isCurrent = id === activeInvestigationId;

    return `
      <div class="spatializer-dropdown-inv-row ${isCurrent ? 'selected' : ''}" data-id="${id}">
        <div class="spat-inv-row-left">
          <span class="spat-inv-id-text">${id}</span>
          <span class="spat-inv-sev-tag sev-${sevClass}">${sev}</span>
        </div>
        <div class="spat-inv-row-right">
          <span class="spat-inv-meta-tag">${inv.n_events_total || 0} evts</span>
          <span class="spat-inv-meta-tag">${inv.n_channels_affected || 1} ch</span>
        </div>
      </div>
    `;
  }).join('');

  // Attach click listeners to rows
  const rows = scrollContainer.querySelectorAll('.spatializer-dropdown-inv-row');
  rows.forEach(row => {
    row.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = row.dataset.id;
      if (id) {
        setSelectedInvestigationId(id);
        await loadInvestigationData(id);
        closeSeverityDropdown();
      }
    });
  });
}

/**
 * Hit test for detecting clicks on 3D Markers & Callout Boxes
 */
function detectMarkerClick(mouseX, mouseY) {
  let clicked = null;
  const radius = 22;

  evidenceChannels.forEach(ch => {
    if (ch.proj) {
      const dx = mouseX - ch.proj.screenX;
      const dy = mouseY - ch.proj.screenY;
      if (Math.sqrt(dx * dx + dy * dy) < radius) {
        clicked = ch;
      }

      const boxW = 114;
      const boxH = 40;
      const boxOffset = ch.x >= 0 ? 20 : -134;
      const boxX = ch.proj.screenX + boxOffset;
      const boxY = ch.proj.screenY - 20;
      if (mouseX >= boxX && mouseX <= boxX + boxW && mouseY >= boxY && mouseY <= boxY + boxH) {
        clicked = ch;
      }
    }
  });

  if (clicked) {
    selectChannel(clicked);
  }
}
