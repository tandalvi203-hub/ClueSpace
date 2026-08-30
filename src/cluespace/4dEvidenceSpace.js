/**
 * ClueSpace — Telemetry Spacetime (Screen 2)
 * Full-Screen 4D Evidence Space
 *
 * 3D = Abstract Evidence Space (Deterministic Mapping from real data only)
 * 4D = Time (Controlled exclusively via temporal timeline cursor)
 *
 * Deterministic Mapping:
 *   X = Channel Lane (discrete lateral placement per unique channel in selected investigation)
 *   Y = Anomaly Score Elevation (Y = anomaly_score * vertical_scale; higher score = higher elevation)
 *   Z = Normalized Telemetry Value (scaled to channel [min, max]; TIME IS NEVER IN Z)
 *   T = Actual Timestamp (4th dimension controlled exclusively via temporal timeline cursor)
 *
 * Zero mock data, zero AI/LLM, zero simulated telemetry.
 * All coordinates, timestamps, channels, relationships, and explanations originate exclusively
 * from actual project investigation files.
 */

import { fetchInvestigation, getAllInvestigations } from './dataService.js';
import { getSelectedInvestigationId, setSelectedInvestigationId, navigateToInvestigationWorkspace, onInvestigationChange } from './navigation.js';

let isInitialized = false;
let activeInvestigation = null;
let activeInvestigationId = 'INV-988';
let currentSeverityFilter = 'ALL';
let selectorSearchQuery = '';
let activeDropdownSeverity = null; // Which severity dropdown is open ('ALL' | 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW' | null)

// 3D Canvas & Context
let canvas = null;
let ctx = null;
let animFrameId = null;

// Focused, closer default camera framing with prominent foreground
const DEFAULT_CAMERA = {
  yaw: -0.45,       // Clean 3/4 spatial perspective
  pitch: 0.30,      // Spatial tilt for clear depth and prominent foreground
  distance: 375,    // Significantly closer, focused framing occupying more viewport
  panX: 110,        // Centered in the open canvas area to the right of the cards
  panY: -20,        // Balanced vertical framing above bottom timeline
  fov: 720          // Immersive perspective FOV
};

// 3D Camera & Viewport State
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

// Mouse Interaction State
let isDragging = false;
let isRightDragging = false;
let lastMouseX = 0;
let lastMouseY = 0;
let hoveredNode = null;
let selectedNode = null;

// 4D Time & Playback State
let timeStart = 0;
let timeEnd = 0;
let currentTimestamp = 0; // Epoch milliseconds
let isPlaying = false;
let playbackSpeed = 1.0;  // Multiplier
let lastFrameTime = performance.now();

// Processed 3D Nodes and Relationships for current investigation
let evidenceNodes = [];
let temporalRelationships = [];
let channelLanes = [];
let keyMilestones = [];

// Entrance Staged Animation State
let entranceProgress = 1.0; // 0 to 1
let isEntranceComplete = false;

/**
 * Resets camera to the composed default angle
 */
function resetCameraToDefault() {
  camera.targetYaw = DEFAULT_CAMERA.yaw;
  camera.targetPitch = DEFAULT_CAMERA.pitch;
  camera.targetDistance = DEFAULT_CAMERA.distance;
  camera.targetPanX = DEFAULT_CAMERA.panX;
  camera.targetPanY = DEFAULT_CAMERA.panY;
}

/**
 * Mounts and initializes Telemetry Spacetime in the second full-screen section.
 */
export async function initTelemetrySpacetime() {
  if (isInitialized) return;

  const section = document.getElementById('spacetime-section');
  if (!section) return;

  // Render HTML structure into #spacetime-section
  section.innerHTML = `
    <!-- Star Dust & Ambience Canvas -->
    <canvas id="spacetime-bg-canvas" class="spacetime-bg-canvas"></canvas>

    <!-- Main Interactive 3D Evidence Space Canvas -->
    <div class="spacetime-viewport" id="spacetime-viewport">
      <canvas id="spacetime-3d-canvas" class="spacetime-3d-canvas"></canvas>
    </div>

    <!-- Left Information & Controls Hierarchy (All on LEFT, matching reference image) -->
    <aside class="spacetime-left-group" id="spacetime-left-group" aria-label="Evidence Space Information and Filters">
      <!-- 1. Severity Investigation Filter Dropdown Controls -->
      <div class="spacetime-sev-filter-group" id="spacetime-sev-filter-group" role="group" aria-label="Filter and select investigations by severity">
        <div class="sev-dropdown-wrap" data-sev="ALL">
          <button class="sev-dropdown-btn active" data-sev="ALL" id="btn-sev-all">
            <span>ALL</span>
            <span class="sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="sev-dropdown-wrap" data-sev="CRITICAL">
          <button class="sev-dropdown-btn sev-critical" data-sev="CRITICAL" id="btn-sev-critical">
            <span>CRITICAL</span>
            <span class="sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="sev-dropdown-wrap" data-sev="HIGH">
          <button class="sev-dropdown-btn sev-high" data-sev="HIGH" id="btn-sev-high">
            <span>HIGH</span>
            <span class="sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="sev-dropdown-wrap" data-sev="MODERATE">
          <button class="sev-dropdown-btn sev-moderate" data-sev="MODERATE" id="btn-sev-moderate">
            <span>MODERATE</span>
            <span class="sev-btn-arrow">▾</span>
          </button>
        </div>
        <div class="sev-dropdown-wrap" data-sev="LOW">
          <button class="sev-dropdown-btn sev-low" data-sev="LOW" id="btn-sev-low">
            <span>LOW</span>
            <span class="sev-btn-arrow">▾</span>
          </button>
        </div>
      </div>

      <!-- Dynamic Searchable Severity Dropdown Panel (Anchored dynamically to clicked severity button) -->
      <div class="spacetime-sev-dropdown-panel" id="spacetime-sev-dropdown-panel" hidden>
        <div class="sev-dropdown-search-box">
          <input 
            type="text" 
            id="spacetime-sev-search-input" 
            class="sev-search-input" 
            placeholder="Search investigation ID..." 
            autocomplete="off" 
            spellcheck="false"
            aria-label="Search investigation by ID"
          />
        </div>
        <div class="sev-dropdown-header" id="sev-dropdown-header">AVAILABLE INVESTIGATIONS</div>
        <div class="sev-dropdown-scroll" id="sev-dropdown-scroll"></div>
      </div>

      <!-- 2. Incident Card (Organized cleanly on the LEFT) -->
      <div class="spacetime-inspector-panel" id="spacetime-inspector-panel" aria-label="Incident and Event Inspector">
        <div class="spacetime-inspector-header">
          <span class="spacetime-inspector-title" id="st-inc-title">INCIDENT #INV-988</span>
          <span class="spacetime-sev-badge sev-critical" id="st-inc-sev">CRITICAL</span>
        </div>

        <div class="spacetime-metrics-grid">
          <div class="spacetime-metric-box">
            <span class="spacetime-m-lbl">SEVERITY SCORE</span>
            <span class="spacetime-m-val" id="st-m-sev">—</span>
          </div>
          <div class="spacetime-metric-box">
            <span class="spacetime-m-lbl">CONFIDENCE</span>
            <span class="spacetime-m-val text-cyan" id="st-m-conf">—</span>
          </div>
          <div class="spacetime-metric-box">
            <span class="spacetime-m-lbl">TOTAL EVENTS</span>
            <span class="spacetime-m-val" id="st-m-events">—</span>
          </div>
          <div class="spacetime-metric-box">
            <span class="spacetime-m-lbl">CHANNELS</span>
            <span class="spacetime-m-val" id="st-m-channels">—</span>
          </div>
          <div class="spacetime-metric-box full-width">
            <span class="spacetime-m-lbl">PARTICIPATING CHANNELS</span>
            <span class="spacetime-m-val" id="st-m-chan-list" style="font-size: 0.78rem; color: #38bdf8; word-break: break-all;">—</span>
          </div>
        </div>

        <!-- Live Selected Node Inspector -->
        <div class="spacetime-node-inspect-box" id="st-node-inspect-box">
          <div class="spacetime-node-inspect-title">
            <span>SELECTED EVENT</span>
            <span id="st-node-status" style="font-size: 0.70rem; color: rgba(186, 230, 253, 0.75);">CLICK ANY 3D NODE</span>
          </div>
          <div class="spacetime-node-field"><span class="k">CHANNEL</span><span class="v" id="st-n-chan">—</span></div>
          <div class="spacetime-node-field"><span class="k">TIMESTAMP</span><span class="v" id="st-n-time">—</span></div>
          <div class="spacetime-node-field"><span class="k">ANOMALY SCORE</span><span class="v" id="st-n-score">—</span></div>
          <div class="spacetime-node-field"><span class="k">TELEMETRY VALUE</span><span class="v" id="st-n-val">—</span></div>
          <div class="spacetime-node-field"><span class="k">SEGMENT</span><span class="v" id="st-n-seg">—</span></div>
        </div>
      </div>

      <!-- 3. PARTS TO KNOW Card -->
      <div class="spacetime-parts-panel">
        <div class="parts-header">PARTS TO KNOW</div>
        <div class="parts-list">
          <div class="part-item">
            <span class="legend-dot dot-telemetry"></span>
            <span class="part-text">Baseline Telemetry</span>
          </div>
          <div class="part-item">
            <span class="legend-dot dot-anomaly"></span>
            <span class="part-text">Elevated Anomaly</span>
          </div>
          <div class="part-item">
            <span class="legend-line-rel"></span>
            <span class="part-text">Temporal Relationship</span>
          </div>
          <div class="part-item">
            <span class="legend-dot dot-incident"></span>
            <span class="part-text">Events Belonging to Selected Investigation</span>
          </div>
        </div>
      </div>

      <!-- 4. EXPLAIN THIS Interactive Control -->
      <button class="btn-explain-this" id="btn-explain-this" aria-expanded="false" aria-controls="spacetime-explain-panel">
        <span>EXPLAIN THIS</span>
        <span class="explain-arrow">→</span>
      </button>
    </aside>

    <!-- Dedicated Right-Side Explanation Panel (Opens on RIGHT when "EXPLAIN THIS" is clicked) -->
    <aside class="spacetime-explain-panel" id="spacetime-explain-panel" hidden aria-label="Investigation Evidence Explanation">
      <div class="explain-header">
        <div class="explain-header-left">
          <span class="explain-header-badge" id="explain-header-badge">INV-988</span>
          <span class="explain-header-title">HOW THE EVIDENCE UNFOLDS</span>
        </div>
        <button class="btn-close-explain" id="btn-close-explain" aria-label="Close Explanation">✕</button>
      </div>
      <div class="explain-body" id="explain-body-content">
        <!-- Dynamically populated from selected investigation JSON data -->
      </div>
    </aside>

    <!-- Floating Bottom Transition Indicator & Controls Guide (Bottom Right) -->
    <div class="spacetime-bottom-widgets">
      <!-- Minimal Scroll Down Transition to Section 3 -->
      <a href="#workflow-section" class="spacetime-scroll-hint" id="spacetime-scroll-hint" aria-label="Scroll to continue to next section">
        <span>SCROLL TO CONTINUE</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </a>

      <div class="spacetime-controls-guide">
        <div class="control-item">
          <span>Left Drag: Rotate</span>
        </div>
        <div class="control-item">
          <span>Right Drag: Pan</span>
        </div>
        <div class="zoom-btn-group">
          <button class="btn-cam-zoom" id="btn-zoom-in" title="Zoom In (+)" aria-label="Zoom In">+</button>
          <button class="btn-cam-zoom" id="btn-zoom-out" title="Zoom Out (−)" aria-label="Zoom Out">−</button>
        </div>
        <button class="btn-reset-cam" id="btn-reset-cam">RESET CAMERA</button>
      </div>
    </div>

    <!-- Bottom 4D Timeline Bar (Temporal Dimension Control) -->
    <footer class="spacetime-bottom-timeline" aria-label="4D Timeline Controller">
      <div class="timeline-playback-btns">
        <button class="tb-btn" id="btn-tb-prev" title="Step to Previous Event">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
            <polygon points="19 20 9 12 19 4 19 20"/>
            <line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" stroke-width="2"/>
          </svg>
        </button>

        <button class="tb-btn" id="btn-tb-play" title="Play / Pause Timeline">
          <svg class="icon-play" viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
        </button>

        <button class="tb-btn" id="btn-tb-reset" title="Rewind to Start (T0)">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="1 4 1 10 7 10"></polyline>
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
          </svg>
        </button>

        <button class="tb-btn" id="btn-tb-next" title="Step to Next Event">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
            <polygon points="5 4 15 12 5 20 5 4"/>
            <line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2"/>
          </svg>
        </button>
      </div>

      <div class="timeline-track-wrapper">
        <div class="timeline-meta-row">
          <span class="time-t0-lbl" id="st-time-t0">T0: —</span>
          <span class="time-current-badge" id="st-time-current">TIME (4D): —</span>
          <span class="time-tend-lbl" id="st-time-tend">T_END: —</span>
        </div>

        <div class="timeline-slider-container" id="timeline-slider-container">
          <div class="timeline-milestones-track" id="timeline-milestones-track"></div>
          <input
            type="range"
            id="spacetime-timeline-slider"
            class="spacetime-range-input"
            min="0"
            max="1000"
            value="0"
            aria-label="4D Timeline Scrubber"
          />
        </div>
      </div>

      <div class="timeline-speed-selector">
        <button class="speed-btn" data-speed="0.5">0.5x</button>
        <button class="speed-btn active" data-speed="1.0">1x</button>
        <button class="speed-btn" data-speed="2.0">2x</button>
        <button class="speed-btn" data-speed="5.0">5x</button>
      </div>
    </footer>

    <!-- Floating 3D Hover Tooltip -->
    <div class="spacetime-node-tooltip" id="spacetime-node-tooltip"></div>
  `;

  // Initialize Canvas & Context
  canvas = document.getElementById('spacetime-3d-canvas');
  if (canvas) {
    ctx = canvas.getContext('2d');
  }

  // Setup Event Listeners
  setupEventListeners(section);

  // Setup Background Star Dust
  initBackgroundCanvas(document.getElementById('spacetime-bg-canvas'));

  // Load Initial Investigation (default or currently selected)
  const initialId = getSelectedInvestigationId() || 'INV-988';
  await loadInvestigationData(initialId);

  // Register investigation change listener from other screens
  onInvestigationChange(async (newId) => {
    if (newId && newId !== activeInvestigationId) {
      await loadInvestigationData(newId);
    }
  });

  // Setup Scroll-based Entrance Reveal Observer
  setupEntranceObserver(section);

  // Start Animation Render Loop
  startRenderLoop();

  isInitialized = true;
}

/**
 * Loads and prepares real investigation data from dataService.js
 */
async function loadInvestigationData(invId) {
  if (!invId) invId = 'INV-988';
  activeInvestigationId = invId;

  // Reset camera to default composed composition on each investigation load
  resetCameraToDefault();

  // Reset playback speed to 1x when switching investigations
  playbackSpeed = 1.0;
  const speedBtns = document.querySelectorAll('.speed-btn');
  speedBtns.forEach(btn => {
    if (btn.dataset.speed === '1.0' || btn.dataset.speed === '1') {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  const inv = await fetchInvestigation(invId);
  if (!inv) {
    console.warn(`Investigation ${invId} could not be loaded.`);
    return;
  }

  activeInvestigation = inv;

  // 1. Authoritative Incident Grouping & Metadata (From source investigation only)
  const timelineEvents = Array.isArray(inv.timeline) ? inv.timeline : [];
  const channelsAffected = Array.isArray(inv.channels_affected) ? inv.channels_affected : [];
  const sevScore = typeof inv.severity_score === 'number' ? inv.severity_score.toFixed(2) : (inv.severity_score || 'N/A');
  const sevLabel = inv.severity_label || inv.mission_impact_level || 'CRITICAL';
  const confidence = typeof inv.investigation_confidence === 'number' 
    ? (inv.investigation_confidence * 100).toFixed(1) + '%' 
    : (inv.investigation_confidence || 'N/A');
  const totalEvents = inv.n_events_total || timelineEvents.length || 0;

  // Update Inspector Panel UI
  updateInspectorMetadata({
    id: inv.investigation_id || invId,
    sevScore,
    sevLabel,
    confidence,
    totalEvents: totalEvents.toLocaleString(),
    channelCount: channelsAffected.length,
    channels: channelsAffected.join(', ') || 'N/A'
  });

  // 2. Parse Timestamps for 4th Dimension (T)
  const rawStartTime = inv.start_time || (timelineEvents[0]?.timestamp) || '2022-06-02T10:44:37Z';
  const rawEndTime = inv.end_time || (timelineEvents[timelineEvents.length - 1]?.timestamp) || rawStartTime;

  timeStart = new Date(rawStartTime).getTime();
  timeEnd = new Date(rawEndTime).getTime();

  if (timeEnd <= timeStart) {
    timeEnd = timeStart + ((inv.duration_sec || 60) * 1000);
  }

  currentTimestamp = timeStart;

  // Format T0 and T_END labels
  const t0Str = rawStartTime.replace('T', ' ').replace('Z', ' UTC');
  const tEndStr = rawEndTime.replace('T', ' ').replace('Z', ' UTC');
  const t0El = document.getElementById('st-time-t0');
  const tEndEl = document.getElementById('st-time-tend');
  if (t0El) t0El.textContent = `T0: ${t0Str}`;
  if (tEndEl) tEndEl.textContent = `T_END: ${tEndStr}`;

  // 3. Deterministic Spatial Layout in Abstract Evidence Space
  // Unique sorted channels from authoritative investigation definition
  const uniqueChannels = Array.from(new Set([
    ...channelsAffected,
    ...timelineEvents.map(e => e.channel)
  ])).filter(Boolean).sort();

  channelLanes = uniqueChannels;
  const numChannels = uniqueChannels.length || 1;
  const laneSpacing = Math.min(90, Math.max(48, 440 / numChannels));

  // Compute channel min/max telemetry values for normalized deterministic visual placement on Z
  const channelRanges = {};
  uniqueChannels.forEach(ch => {
    channelRanges[ch] = { min: Infinity, max: -Infinity };
  });

  timelineEvents.forEach(e => {
    if (typeof e.value === 'number' && channelRanges[e.channel]) {
      if (e.value < channelRanges[e.channel].min) channelRanges[e.channel].min = e.value;
      if (e.value > channelRanges[e.channel].max) channelRanges[e.channel].max = e.value;
    }
  });

  // Build deterministic 3D nodes (Conceptual: X = Channel, Y = Anomaly Score * Scale, Z = Normalized Telemetry Value)
  evidenceNodes = timelineEvents.map((e, index) => {
    const chIndex = uniqueChannels.indexOf(e.channel);
    // X = Channel Lane (deterministic lateral placement)
    const x = (chIndex - (numChannels - 1) / 2) * laneSpacing;

    // Y = Anomaly Score Elevation (Conceptual mapping: Y = anomaly_score * vertical_scale)
    const anomalyScore = typeof e.anomaly_score === 'number' ? Math.max(0, Math.min(1, e.anomaly_score)) : 0;
    const y = anomalyScore * 135; // Positive elevation in Evidence Space

    // Z = Telemetry Value Placement (Deterministic visual placement from real value; ZERO time in Z)
    const range = channelRanges[e.channel] || { min: 0, max: 1 };
    let normVal = 0.5;
    if (range.max > range.min && typeof e.value === 'number') {
      normVal = (e.value - range.min) / (range.max - range.min);
    }
    const z = (normVal - 0.5) * 150;

    const eventTime = new Date(e.timestamp).getTime();

    // Incident Membership: Authoritative membership from source dataset
    const isIncidentChannel = channelsAffected.includes(e.channel);
    const isHighAnomaly = anomalyScore >= 0.45;

    return {
      index,
      raw: e,
      x,
      y,
      z,
      timestamp: eventTime,
      channel: e.channel,
      anomalyScore,
      value: e.value,
      segment: e.segment,
      isIncidentGroup: isIncidentChannel && isHighAnomaly,
      isAnomaly: anomalyScore >= 0.4
    };
  });

  // 4. Dataset-Driven Temporal Relationships (Activating strictly at concluding timestamp)
  const rawRelationships = Array.isArray(inv.channel_temporal_relationships) 
    ? inv.channel_temporal_relationships 
    : [];

  temporalRelationships = rawRelationships.map(rel => {
    const tA = new Date(rel.channel_a_start).getTime();
    const tB = new Date(rel.channel_b_start).getTime();

    // Determine concluding timestamp from temporal precedence and start timestamps
    let concludeTime = Math.max(tA, tB);
    let precedenceTerm = 'TEMPORAL ASSOCIATION';

    if (rel.temporal_precedence === 'A_before_B') {
      concludeTime = tB;
      precedenceTerm = 'PRECEDED';
    } else if (rel.temporal_precedence === 'B_before_A' || rel.temporal_precedence === 'A_after_B') {
      concludeTime = tA;
      precedenceTerm = 'FOLLOWED';
    } else if (rel.windows_overlap) {
      precedenceTerm = 'OVERLAPPING WINDOW';
    }

    const gapText = typeof rel.temporal_gap_sec === 'number' ? `${rel.temporal_gap_sec}s` : '0s';
    const overlapText = rel.windows_overlap ? 'True' : 'False';

    const chAIndex = uniqueChannels.indexOf(rel.channel_a);
    const chBIndex = uniqueChannels.indexOf(rel.channel_b);
    const xA = (chAIndex - (numChannels - 1) / 2) * laneSpacing;
    const xB = (chBIndex - (numChannels - 1) / 2) * laneSpacing;

    return {
      channelA: rel.channel_a,
      channelB: rel.channel_b,
      timeA: tA,
      timeB: tB,
      concludeTime,
      precedence: rel.temporal_precedence,
      precedenceTerm,
      gapSec: rel.temporal_gap_sec,
      windowsOverlap: rel.windows_overlap,
      label: `${precedenceTerm}: ${rel.channel_a} ↔ ${rel.channel_b} (Gap: ${gapText}, Overlap: ${overlapText})`,
      xA,
      xB,
      yA: 65, // Elevated baseline for relationship connectors in Evidence Space
      yB: 65,
      zA: 0,
      zB: 0
    };
  });

  // 5. Intelligent Timeline Milestone Density Management
  buildTimelineMilestones();

  // 6. Generate Investigation-Specific Deterministic Explanation
  updateExplanationPanel(inv);

  // Reset selected node
  selectedNode = null;
  resetNodeInspectBox();

  // Update slider bounds & set initial timestamp to start
  updateTimelineSlider();
}

/**
 * Generates and renders a deterministic, evidence-based, human-readable explanation
 * derived purely from the selected investigation's actual JSON data. Zero AI/LLM/API.
 */
function updateExplanationPanel(inv) {
  const badge = document.getElementById('explain-header-badge');
  const body = document.getElementById('explain-body-content');
  if (!badge || !body || !inv) return;

  const id = inv.investigation_id || `INV-${inv.spacecraft_incident_id}`;
  const sev = inv.severity_label || inv.mission_impact_level || (inv.severity_score >= 8 ? 'CRITICAL' : 'HIGH');
  const sevScore = typeof inv.severity_score === 'number' ? inv.severity_score.toFixed(2) : (inv.severity_score || 'N/A');
  const conf = typeof inv.investigation_confidence === 'number' ? `${(inv.investigation_confidence * 100).toFixed(1)}%` : (inv.investigation_confidence || 'N/A');
  const durationText = inv.duration_sec ? `${inv.duration_sec} seconds` : 'the incident window';
  const totalEvents = inv.n_events_total || (inv.timeline ? inv.timeline.length : 0);
  const channels = Array.isArray(inv.channels_affected) ? inv.channels_affected : [];
  const chanOrder = Array.isArray(inv.channel_activation_order) ? inv.channel_activation_order : channels;
  const rels = Array.isArray(inv.channel_temporal_relationships) ? inv.channel_temporal_relationships : [];
  const timeline = Array.isArray(inv.timeline) ? inv.timeline : [];

  // Peak anomaly score & strongest channel calculation
  let peakScore = 'N/A';
  let strongestChan = channels[0] || 'primary';
  let maxScoreVal = 0;
  if (typeof inv.peak_anomaly_score === 'number') {
    peakScore = inv.peak_anomaly_score.toFixed(3);
    maxScoreVal = inv.peak_anomaly_score;
  }
  if (timeline.length > 0) {
    timeline.forEach(e => {
      if (typeof e.anomaly_score === 'number' && e.anomaly_score > maxScoreVal) {
        maxScoreVal = e.anomaly_score;
        peakScore = maxScoreVal.toFixed(3);
        if (e.channel) strongestChan = e.channel;
      }
    });
  }

  // Count elevated anomalies (score >= 0.45) vs baseline
  let elevatedCount = 0;
  let baselineCount = 0;
  timeline.forEach(e => {
    if (typeof e.anomaly_score === 'number' && e.anomaly_score >= 0.45) {
      elevatedCount++;
    } else {
      baselineCount++;
    }
  });

  badge.textContent = id;

  const firstChan = chanOrder[0] || channels[0] || 'Unknown';
  const lastChan = chanOrder.length > 1 ? chanOrder[chanOrder.length - 1] : firstChan;

  // 1. WHAT HAPPENED
  let whatHappenedHtml = '';
  if (channels.length > 1) {
    whatHappenedHtml = `During this <strong class="hl-cyan">${durationText}</strong> observation window, telemetry anomalies were cataloged across <strong class="hl-cyan">${channels.length} sensor channels</strong> (${channels.join(', ')}). The sequence initiated on channel <strong class="hl-cyan">${firstChan}</strong> and culminated in <strong class="hl-cyan">${totalEvents.toLocaleString()} recorded events</strong>, registering a peak anomaly score of <strong class="hl-purple">${peakScore}</strong> on channel <strong class="hl-cyan">${strongestChan}</strong>.`;
  } else {
    whatHappenedHtml = `A single-sensor telemetry anomaly of <strong class="hl-cyan">${totalEvents.toLocaleString()} recorded events</strong> was observed on channel <strong class="hl-cyan">${firstChan}</strong> over a duration of <strong class="hl-cyan">${durationText}</strong>. Activity peaked with an anomaly score of <strong class="hl-purple">${peakScore}</strong> without spreading to neighboring telemetry streams.`;
  }

  // 2. WHAT IS THE EVIDENCE
  let whatIsTheEvidenceHtml = '';
  if (channels.length > 1) {
    whatIsTheEvidenceHtml = `The 3D Evidence Space organizes telemetry across <strong>${channels.length} discrete channel lanes</strong>. Anomalous data rises vertically along the elevation axis, with <strong>${elevatedCount} event(s)</strong> elevated above nominal levels and <strong>${baselineCount} event(s)</strong> defining baseline state. Channel <strong class="hl-cyan">${strongestChan}</strong> exhibits the highest vertical displacement, with <strong>${rels.length} temporal connection arc(s)</strong> linking corresponding channels.`;
  } else {
    whatIsTheEvidenceHtml = `The 3D Evidence Space isolates all telemetry to a single lane for channel <strong class="hl-cyan">${firstChan}</strong>. Vertical elevation reflects an elevated anomaly profile with <strong>${elevatedCount} event(s)</strong> elevated up to score <strong class="hl-purple">${peakScore}</strong> and <strong>${baselineCount} event(s)</strong> at nominal baseline. No cross-lane connection arcs are present.`;
  }

  // 3. HOW DID IT PROGRESS?
  let howDidItProgressHtml = '';
  if (chanOrder.length > 1) {
    let firstTime = timeline.find(e => e.channel === firstChan)?.timestamp;
    let lastTime = timeline.filter(e => e.channel === lastChan).pop()?.timestamp;
    let spanSec = (firstTime && lastTime) ? Math.max(0, Math.round((new Date(lastTime) - new Date(firstTime)) / 1000)) : inv.duration_sec || 0;
    
    howDidItProgressHtml = `<div style="margin-bottom: 4px;">Activation sequence: <strong class="hl-cyan">${chanOrder.join(' → ')}</strong></div>`;
    howDidItProgressHtml += `<div>Activity began on channel <strong>${firstChan}</strong>, progressing across <strong>${chanOrder.length - 1} subsequent channel(s)</strong> to <strong>${lastChan}</strong> across a span of <strong>${spanSec}s</strong> from first to last activation.</div>`;
  } else {
    howDidItProgressHtml = `Telemetry anomaly initiated and concluded exclusively on channel <strong class="hl-cyan">${firstChan}</strong>. The activity persisted across <strong>${durationText}</strong> without sequential propagation to any other channel.`;
  }

  // 4. WHAT IS THE CONNECTION?
  let whatIsTheConnectionHtml = '';
  if (rels.length > 0) {
    const overlappingRels = rels.filter(r => r.windows_overlap);
    const avgGap = (rels.reduce((sum, r) => sum + (typeof r.temporal_gap_sec === 'number' ? r.temporal_gap_sec : 0), 0) / rels.length).toFixed(1);
    
    whatIsTheConnectionHtml = `<div style="margin-bottom: 4px;"><strong>${overlappingRels.length} of ${rels.length}</strong> calculated channel pair(s) exhibit overlapping anomaly windows (average temporal gap: <strong>${avgGap}s</strong>).</div>`;
    const relItems = rels.slice(0, 3).map(r => {
      const overlapStatus = r.windows_overlap ? 'Overlapping' : 'Sequential';
      const gapVal = typeof r.temporal_gap_sec === 'number' ? `${r.temporal_gap_sec}s` : '0s';
      return `<li class="explain-list-item">• <strong class="hl-cyan">${r.channel_a}</strong> → <strong class="hl-cyan">${r.channel_b}</strong>: ${gapVal} gap (${overlapStatus})</li>`;
    }).join('');
    whatIsTheConnectionHtml += `<ul class="explain-list">${relItems}</ul>`;
    if (rels.length > 3) {
      whatIsTheConnectionHtml += `<div class="explain-subtext">+ ${rels.length - 3} additional calculated temporal connection(s).</div>`;
    }
  } else {
    whatIsTheConnectionHtml = `Isolated activity: No cross-channel temporal relationships or inter-channel window overlaps were detected in the telemetry dataset.`;
  }

  // 5. CONCLUSION
  let conclusionHtml = '';
  if (Array.isArray(inv.hypothesis_statements) && inv.hypothesis_statements.length > 0) {
    conclusionHtml = inv.hypothesis_statements[0];
  } else if (channels.length > 1) {
    conclusionHtml = `Deterministic telemetry analysis indicates a coordinated multi-channel sequence across ${channels.length} sensors with ${rels.length} corroborating temporal relationships.`;
  } else {
    conclusionHtml = `Telemetry analysis confirms an isolated anomaly sequence confined strictly to channel ${firstChan} with no systemic propagation.`;
  }

  // Render the structured 6-part panel
  body.innerHTML = `
    <div class="explain-block">
      <div class="explain-sec-title">1. WHAT HAPPENED</div>
      <div class="explain-sec-text">${whatHappenedHtml}</div>
    </div>

    <div class="explain-block">
      <div class="explain-sec-title">2. WHAT IS THE EVIDENCE</div>
      <div class="explain-sec-text">${whatIsTheEvidenceHtml}</div>
    </div>

    <div class="explain-block">
      <div class="explain-sec-title">3. HOW DID IT PROGRESS?</div>
      <div class="explain-sec-text">${howDidItProgressHtml}</div>
    </div>

    <div class="explain-block">
      <div class="explain-sec-title">4. WHAT IS THE CONNECTION?</div>
      <div class="explain-sec-text">${whatIsTheConnectionHtml}</div>
    </div>

    <div class="explain-block">
      <div class="explain-sec-title">5. CONCLUSION</div>
      <div class="explain-sec-text">${conclusionHtml}</div>
    </div>

    <div class="explain-block" style="margin-top: 4px;">
      <div class="explain-meta-pill">ASSESSMENT: ${sev} (${sevScore}/10) · CONFIDENCE: ${conf}</div>
    </div>
  `;
}

/**
 * Builds data-driven milestone markers with visual density management
 */
function buildTimelineMilestones() {
  const container = document.getElementById('timeline-milestones-track');
  if (!container || timeEnd <= timeStart) return;

  container.innerHTML = '';
  keyMilestones = [];

  // Collect candidate timestamps from actual dataset: anomaly peaks and relationship timings
  const rawTimestamps = [];

  evidenceNodes.forEach(n => {
    if (n.anomalyScore >= 0.5) {
      rawTimestamps.push({ time: n.timestamp, type: 'anomaly', score: n.anomalyScore, channel: n.channel });
    }
  });

  temporalRelationships.forEach(r => {
    rawTimestamps.push({ time: r.concludeTime, type: 'relationship', label: r.label });
  });

  // Sort by time
  rawTimestamps.sort((a, b) => a.time - b.time);

  // Visual density filter: Enforce minimum pixel distance threshold between visible milestone ticks
  const minSpacingRatio = 0.04; // 4% of track width minimum separation
  let lastRatio = -1;

  rawTimestamps.forEach(item => {
    const ratio = (item.time - timeStart) / (timeEnd - timeStart);
    if (ratio >= 0 && ratio <= 1) {
      if (lastRatio === -1 || (ratio - lastRatio) >= minSpacingRatio) {
        lastRatio = ratio;
        keyMilestones.push({ ...item, ratio });

        const dot = document.createElement('div');
        dot.className = `milestone-tick tick-${item.type}`;
        dot.style.left = `${(ratio * 100).toFixed(2)}%`;
        dot.title = `${new Date(item.time).toISOString().replace('T', ' ').replace('Z', ' UTC')} (${item.type === 'relationship' ? 'Relationship Concluded' : `Anomaly on ${item.channel}`})`;
        container.appendChild(dot);
      }
    }
  });
}

/**
 * Updates floating inspector panel header and metadata cards
 */
function updateInspectorMetadata({ id, sevScore, sevLabel, confidence, totalEvents, channelCount, channels }) {
  const incTitle = document.getElementById('st-inc-title');
  const incSev = document.getElementById('st-inc-sev');
  const mSev = document.getElementById('st-m-sev');
  const mConf = document.getElementById('st-m-conf');
  const mEvents = document.getElementById('st-m-events');
  const mChannels = document.getElementById('st-m-channels');
  const mChanList = document.getElementById('st-m-chan-list');

  if (incTitle) incTitle.textContent = `INCIDENT #${id}`;
  if (incSev) {
    incSev.textContent = sevLabel;
    incSev.className = `spacetime-sev-badge sev-${sevLabel.toLowerCase()}`;
  }
  if (mSev) mSev.textContent = `${sevScore} / 10`;
  if (mConf) mConf.textContent = confidence;
  if (mEvents) mEvents.textContent = totalEvents;
  if (mChannels) mChannels.textContent = `${channelCount}`;
  if (mChanList) mChanList.textContent = channels;
}

/**
 * Resets selected node inspection box
 */
function resetNodeInspectBox() {
  const nStatus = document.getElementById('st-node-status');
  const nChan = document.getElementById('st-n-chan');
  const nTime = document.getElementById('st-n-time');
  const nScore = document.getElementById('st-n-score');
  const nVal = document.getElementById('st-n-val');
  const nSeg = document.getElementById('st-n-seg');

  if (nStatus) nStatus.textContent = 'CLICK ANY 3D NODE';
  if (nChan) nChan.textContent = '—';
  if (nTime) nTime.textContent = '—';
  if (nScore) nScore.textContent = '—';
  if (nVal) nVal.textContent = '—';
  if (nSeg) nSeg.textContent = '—';
}

/**
 * Updates selected node inspect box with exact real dataset fields
 */
function displaySelectedNode(node) {
  if (!node) return;
  const nStatus = document.getElementById('st-node-status');
  const nChan = document.getElementById('st-n-chan');
  const nTime = document.getElementById('st-n-time');
  const nScore = document.getElementById('st-n-score');
  const nVal = document.getElementById('st-n-val');
  const nSeg = document.getElementById('st-n-seg');

  const formattedTime = new Date(node.timestamp).toISOString().replace('T', ' ').replace('Z', ' UTC');

  if (nStatus) nStatus.textContent = `NODE #${node.index + 1}`;
  if (nChan) nChan.textContent = node.channel || 'N/A';
  if (nTime) nTime.textContent = formattedTime;
  if (nScore) nScore.textContent = typeof node.anomalyScore === 'number' ? node.anomalyScore.toFixed(4) : 'N/A';
  if (nVal) nVal.textContent = typeof node.value === 'number' ? node.value.toString() : 'N/A';
  if (nSeg) nSeg.textContent = node.segment !== undefined ? node.segment : 'N/A';
}

/**
 * Opens and renders the severity dropdown panel directly anchored beneath the clicked button
 */
function openSeverityDropdown(sev) {
  activeDropdownSeverity = sev;
  currentSeverityFilter = sev;
  selectorSearchQuery = '';

  const panel = document.getElementById('spacetime-sev-dropdown-panel');
  const searchInput = document.getElementById('spacetime-sev-search-input');
  const btns = document.querySelectorAll('.sev-dropdown-btn');

  btns.forEach(b => {
    if (b.dataset.sev === sev) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  const filterGroup = document.getElementById('spacetime-sev-filter-group');

  if (panel && filterGroup) {
    // Mount the dropdown directly inside the filter group container on frontmost layer
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
  const panel = document.getElementById('spacetime-sev-dropdown-panel');
  if (panel) {
    panel.hidden = true;
    panel.style.display = 'none';
  }
}

/**
 * Populates dynamic searchable investigation dropdown items for the active severity
 */
function renderSeverityDropdownItems() {
  const scrollContainer = document.getElementById('sev-dropdown-scroll');
  const header = document.getElementById('sev-dropdown-header');
  if (!scrollContainer) return;

  const sevToFilter = activeDropdownSeverity || currentSeverityFilter || 'ALL';
  const results = getAllInvestigations(sevToFilter, selectorSearchQuery);

  if (header) {
    header.textContent = `${sevToFilter} INVESTIGATIONS (${results.length})`;
  }

  if (results.length === 0) {
    scrollContainer.innerHTML = `
      <div class="dropdown-no-results">
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
      <div class="dropdown-inv-row ${isCurrent ? 'selected' : ''}" data-id="${id}">
        <div class="inv-row-left">
          <span class="inv-id-text">${id}</span>
          <span class="inv-sev-tag sev-${sevClass}">${sev}</span>
        </div>
        <div class="inv-row-right">
          <span class="inv-meta-tag">${inv.n_events_total || 0} evts</span>
          <span class="inv-meta-tag">${inv.n_channels_affected || 1} ch</span>
        </div>
      </div>
    `;
  }).join('');

  // Attach click listeners to rows
  const rows = scrollContainer.querySelectorAll('.dropdown-inv-row');
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
 * Event Listeners for 3D Camera, Timeline Slider, Playback, and Navigation
 */
function setupEventListeners(section) {
  const viewport = section.querySelector('#spacetime-viewport');
  const slider = section.querySelector('#spacetime-timeline-slider');
  const btnPlay = section.querySelector('#btn-tb-play');
  const btnReset = section.querySelector('#btn-tb-reset');
  const btnPrev = section.querySelector('#btn-tb-prev');
  const btnNext = section.querySelector('#btn-tb-next');
  const btnResetCam = section.querySelector('#btn-reset-cam');
  const btnZoomIn = section.querySelector('#btn-zoom-in');
  const btnZoomOut = section.querySelector('#btn-zoom-out');
  const speedBtns = section.querySelectorAll('.speed-btn');
  const tooltip = section.querySelector('#spacetime-node-tooltip');
  const sevBtns = section.querySelectorAll('.sev-dropdown-btn');
  const sevSearchInput = section.querySelector('#spacetime-sev-search-input');
  const btnExplainThis = section.querySelector('#btn-explain-this');
  const btnCloseExplain = section.querySelector('#btn-close-explain');
  const explainPanel = section.querySelector('#spacetime-explain-panel');

  // 1. Severity Dropdown Buttons (Opens dropdown anchored directly beneath the button)
  sevBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sev = btn.dataset.sev || 'ALL';
      const panel = section.querySelector('#spacetime-sev-dropdown-panel');
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
    if (!section.querySelector('.spacetime-sev-filter-group')?.contains(e.target) &&
        !section.querySelector('#spacetime-sev-dropdown-panel')?.contains(e.target)) {
      closeSeverityDropdown();
    }
  });

  // 2. EXPLAIN THIS Interactive Control & Progressive Disclosure (Opens directly below Explain This button)
  if (btnExplainThis && explainPanel) {
    btnExplainThis.addEventListener('click', (e) => {
      e.stopPropagation();
      const isHidden = explainPanel.hidden;
      explainPanel.hidden = !isHidden;
      explainPanel.style.display = isHidden ? 'flex' : 'none';
      btnExplainThis.setAttribute('aria-expanded', String(isHidden));
      if (isHidden) {
        btnExplainThis.classList.add('active');
      } else {
        btnExplainThis.classList.remove('active');
      }
    });
  }

  if (btnCloseExplain && explainPanel) {
    btnCloseExplain.addEventListener('click', (e) => {
      e.stopPropagation();
      explainPanel.hidden = true;
      explainPanel.style.display = 'none';
      if (btnExplainThis) {
        btnExplainThis.setAttribute('aria-expanded', 'false');
        btnExplainThis.classList.remove('active');
      }
    });
  }

  // 3. 3D Camera Mouse Controls with Natural Page Scrolling Preserved
  if (viewport) {
    viewport.addEventListener('mousedown', (e) => {
      if (e.button === 2 || e.shiftKey) {
        isRightDragging = true;
        viewport.style.cursor = 'move';
      } else if (e.button === 0) {
        isDragging = true;
        viewport.style.cursor = 'grabbing';
      }
      lastMouseX = e.clientX;
      lastMouseY = e.clientY;
    });

    window.addEventListener('mousemove', (e) => {
      const rect = viewport.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (isDragging) {
        const deltaX = e.clientX - lastMouseX;
        const deltaY = e.clientY - lastMouseY;
        camera.targetYaw += deltaX * 0.0055;
        camera.targetPitch = Math.max(0.05, Math.min(1.35, camera.targetPitch - deltaY * 0.0055));
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
      } else if (isRightDragging) {
        const deltaX = e.clientX - lastMouseX;
        const deltaY = e.clientY - lastMouseY;
        camera.targetPanX += deltaX * 0.4;
        camera.targetPanY += deltaY * 0.4;
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
      } else {
        // Raycast / Hover Detection
        detectHoveredNode(mouseX, mouseY, tooltip);
      }
    });

    window.addEventListener('mouseup', () => {
      if (isDragging || isRightDragging) {
        isDragging = false;
        isRightDragging = false;
        if (viewport) viewport.style.cursor = 'default';
      }
    });

    // Zoom via Modifier Wheel (Ctrl / Shift / Meta) while allowing natural vertical page scroll
    viewport.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey) {
        e.preventDefault();
        camera.targetDistance = Math.max(220, Math.min(1000, camera.targetDistance + e.deltaY * 0.5));
      }
      // Otherwise, passive natural scroll is fully permitted across entire page!
    }, { passive: false });

    // Prevent context menu on right click
    viewport.addEventListener('contextmenu', (e) => e.preventDefault());

    // Click on 3D node selection
    viewport.addEventListener('click', () => {
      if (hoveredNode) {
        selectedNode = hoveredNode;
        displaySelectedNode(selectedNode);
      }
    });
  }

  // 4. Dedicated Zoom Controls
  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      camera.targetDistance = Math.max(220, camera.targetDistance - 60);
    });
  }

  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      camera.targetDistance = Math.min(1000, camera.targetDistance + 60);
    });
  }

  // 5. Camera Reset to Composed Default
  if (btnResetCam) {
    btnResetCam.addEventListener('click', () => {
      resetCameraToDefault();
    });
  }

  // 6. Timeline Slider Scrubber (4th Dimension)
  if (slider) {
    slider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      const ratio = val / 1000;
      currentTimestamp = timeStart + ratio * (timeEnd - timeStart);
      updateTimelineDisplay();
    });
  }

  // 7. Play / Pause Playback
  if (btnPlay) {
    btnPlay.addEventListener('click', () => {
      isPlaying = !isPlaying;
      updatePlayButtonUI();
    });
  }

  // 8. Reset to Start (T0)
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      currentTimestamp = timeStart;
      isPlaying = false;
      updatePlayButtonUI();
      updateTimelineDisplay();
    });
  }

  // 9. Step Previous Event
  if (btnPrev) {
    btnPrev.addEventListener('click', () => {
      const pastEvents = evidenceNodes.filter(n => n.timestamp < currentTimestamp);
      if (pastEvents.length > 0) {
        currentTimestamp = pastEvents[pastEvents.length - 1].timestamp;
      } else {
        currentTimestamp = timeStart;
      }
      updateTimelineDisplay();
    });
  }

  // 10. Step Next Event
  if (btnNext) {
    btnNext.addEventListener('click', () => {
      const futureEvents = evidenceNodes.filter(n => n.timestamp > currentTimestamp);
      if (futureEvents.length > 0) {
        currentTimestamp = futureEvents[0].timestamp;
      } else {
        currentTimestamp = timeEnd;
      }
      updateTimelineDisplay();
    });
  }

  // 11. Speed Buttons
  speedBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      speedBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      playbackSpeed = parseFloat(btn.dataset.speed) || 1.0;
    });
  });

  // Window Resize
  window.addEventListener('resize', handleResize);
  handleResize();
}

function handleResize() {
  if (canvas) {
    canvas.width = canvas.parentElement.clientWidth || window.innerWidth;
    canvas.height = canvas.parentElement.clientHeight || window.innerHeight;
  }
}

function setupEntranceObserver(section) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !isEntranceComplete) {
        triggerEntranceAnimation();
      }
    });
  }, { threshold: 0.35 });

  observer.observe(section);
}

function triggerEntranceAnimation() {
  entranceProgress = 0;
  const startTime = performance.now();
  const duration = 1200; // ms

  function step(now) {
    const elapsed = now - startTime;
    entranceProgress = Math.min(1.0, elapsed / duration);
    if (entranceProgress < 1.0) {
      requestAnimationFrame(step);
    } else {
      isEntranceComplete = true;
    }
  }
  requestAnimationFrame(step);
}

function updatePlayButtonUI() {
  const btnPlay = document.getElementById('btn-tb-play');
  if (!btnPlay) return;

  if (isPlaying) {
    btnPlay.classList.add('active-play');
    btnPlay.innerHTML = `
      <svg class="icon-pause" viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
        <rect x="6" y="4" width="4" height="16" rx="1"/>
        <rect x="14" y="4" width="4" height="16" rx="1"/>
      </svg>
    `;
  } else {
    btnPlay.classList.remove('active-play');
    btnPlay.innerHTML = `
      <svg class="icon-play" viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
    `;
  }
}

function updateTimelineSlider() {
  const slider = document.getElementById('spacetime-timeline-slider');
  if (slider && timeEnd > timeStart) {
    const ratio = Math.max(0, Math.min(1, (currentTimestamp - timeStart) / (timeEnd - timeStart)));
    slider.value = Math.round(ratio * 1000);
  }
  updateTimelineDisplay();
}

function updateTimelineDisplay() {
  const timeCurrentBadge = document.getElementById('st-time-current');
  const slider = document.getElementById('spacetime-timeline-slider');

  if (slider && timeEnd > timeStart) {
    const ratio = Math.max(0, Math.min(1, (currentTimestamp - timeStart) / (timeEnd - timeStart)));
    slider.value = Math.round(ratio * 1000);
  }

  if (timeCurrentBadge) {
    const dateObj = new Date(currentTimestamp);
    const dateStr = dateObj.toISOString().replace('T', ' ').replace('Z', ' UTC');
    const elapsedSec = Math.max(0, Math.floor((currentTimestamp - timeStart) / 1000));
    const m = Math.floor(elapsedSec / 60).toString().padStart(2, '0');
    const s = (elapsedSec % 60).toString().padStart(2, '0');
    timeCurrentBadge.textContent = `TIME (4D): ${dateStr} [T+${m}:${s}]`;
  }
}

/**
 * 3D Raycaster: Finds closest node to mouse cursor in screen space
 */
function detectHoveredNode(mouseX, mouseY, tooltip) {
  if (!evidenceNodes.length || !ctx) {
    hoveredNode = null;
    if (tooltip) tooltip.classList.remove('visible');
    return;
  }

  let closest = null;
  let minDist = 16; // screen pixel radius

  evidenceNodes.forEach(node => {
    // Only test nodes that are currently visible in time
    if (node.timestamp <= currentTimestamp && node.proj) {
      const dx = mouseX - node.proj.screenX;
      const dy = mouseY - node.proj.screenY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < minDist) {
        minDist = dist;
        closest = node;
      }
    }
  });

  hoveredNode = closest;

  if (hoveredNode && tooltip) {
    const timeStr = new Date(hoveredNode.timestamp).toISOString().replace('T', ' ').replace('Z', ' UTC');
    tooltip.innerHTML = `
      <div style="color: #38bdf8; font-weight: 700; margin-bottom: 2px;">${hoveredNode.channel}</div>
      <div>Timestamp: ${timeStr}</div>
      <div>Anomaly Score: ${hoveredNode.anomalyScore.toFixed(4)}</div>
      <div>Telemetry Value: ${hoveredNode.value}</div>
      ${hoveredNode.segment !== undefined ? `<div>Segment: ${hoveredNode.segment}</div>` : ''}
    `;
    tooltip.style.left = `${hoveredNode.proj.screenX}px`;
    tooltip.style.top = `${hoveredNode.proj.screenY}px`;
    tooltip.classList.add('visible');
  } else if (tooltip) {
    tooltip.classList.remove('visible');
  }
}

/**
 * Main 3D Hardware-Accelerated Vector Render Loop
 */
function startRenderLoop() {
  function render(now) {
    const deltaMs = now - lastFrameTime;
    lastFrameTime = now;

    // 1. 4D Time Playback Progression
    if (isPlaying && timeEnd > timeStart) {
      const advanceMs = deltaMs * playbackSpeed * 12; // Scaled playback progression
      currentTimestamp += advanceMs;
      if (currentTimestamp >= timeEnd) {
        currentTimestamp = timeEnd;
        isPlaying = false;
        updatePlayButtonUI();
      }
      updateTimelineSlider();
    }

    // 2. Smooth Camera Interpolation (Momentum Damping)
    camera.yaw += (camera.targetYaw - camera.yaw) * 0.12;
    camera.pitch += (camera.targetPitch - camera.pitch) * 0.12;
    camera.distance += (camera.targetDistance - camera.distance) * 0.12;
    camera.panX += (camera.targetPanX - camera.panX) * 0.12;
    camera.panY += (camera.targetPanY - camera.panY) * 0.12;

    // 3. Draw 3D Scene
    drawScene();

    animFrameId = requestAnimationFrame(render);
  }

  animFrameId = requestAnimationFrame(render);
}

/**
 * 3D Projection & Rasterization Engine
 */
function drawScene() {
  if (!ctx || !canvas) return;

  const width = canvas.width;
  const height = canvas.height;
  const centerX = width / 2 + camera.panX;
  const centerY = height / 2 + camera.panY;

  // Clear frame
  ctx.clearRect(0, 0, width, height);

  // Trig constants for 3D Camera Rotation
  const cosY = Math.cos(camera.yaw);
  const sinY = Math.sin(camera.yaw);
  const cosP = Math.cos(camera.pitch);
  const sinP = Math.sin(camera.pitch);

  // 3D Point Projection Helper (Screen coordinate inversion handled inside renderer)
  function project3D(x, y, z) {
    // 1. Yaw rotation around Y axis
    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;

    // 2. Pitch rotation around X axis (+y elevates upward in Evidence Space; in canvas space screen Y decreases upward)
    const y2 = -y * cosP - z1 * sinP;
    const z2 = y * sinP + z1 * cosP + camera.distance;

    if (z2 <= 20) return null; // Behind camera plane

    // 3. Perspective divide
    const scale = camera.fov / z2;
    const screenX = centerX + x1 * scale;
    const screenY = centerY + y2 * scale;

    return { screenX, screenY, scale, zDepth: z2 };
  }

  // 1. Draw Subtle 3D Base Evidence Plane Grid & Channel Lanes
  drawEvidenceGrid(project3D);

  // 2. Draw Subtle Evidence Space Reticle Indicator
  drawEvidenceSpaceIndicator(project3D);

  // 3. Project & Filter Active 4D Nodes
  const renderList = [];

  evidenceNodes.forEach(node => {
    // 4th Dimension (T) Filter: Event visible if timestamp <= currentTimestamp
    if (node.timestamp <= currentTimestamp) {
      const proj = project3D(node.x, node.y, node.z);
      if (proj) {
        node.proj = proj;
        // Age in seconds for visual pulse/decay animation
        const ageSec = (currentTimestamp - node.timestamp) / 1000;
        renderList.push({
          type: 'node',
          data: node,
          zDepth: proj.zDepth,
          ageSec
        });
      }
    } else {
      node.proj = null;
    }
  });

  // 4. Project & Filter Active Dataset Temporal Relationships (Concluded at concluding timestamp)
  temporalRelationships.forEach(rel => {
    // Concluding event rule: Relationship visible when current timeline reaches concluding timestamp
    if (currentTimestamp >= rel.concludeTime) {
      // Find active nodes on channel A and B
      const nodeA = evidenceNodes.filter(n => n.channel === rel.channelA && n.timestamp <= currentTimestamp).pop();
      const nodeB = evidenceNodes.filter(n => n.channel === rel.channelB && n.timestamp <= currentTimestamp).pop();

      if (nodeA && nodeB && nodeA.proj && nodeB.proj) {
        const midZ = (nodeA.proj.zDepth + nodeB.proj.zDepth) / 2;
        renderList.push({
          type: 'relationship',
          rel,
          nodeA,
          nodeB,
          zDepth: midZ
        });
      }
    }
  });

  // 5. Depth Sort (Painter's Algorithm: Furthest first)
  renderList.sort((a, b) => b.zDepth - a.zDepth);

  // 6. Rasterize Render List
  renderList.forEach(item => {
    if (item.type === 'relationship') {
      drawRelationshipEdge(item.rel, item.nodeA, item.nodeB);
    } else if (item.type === 'node') {
      drawEvidenceNode(item.data, item.ageSec);
    }
  });
}

/**
 * Draws the 3D Base Evidence Plane Grid with restrained opacity and persistent channel lanes
 */
function drawEvidenceGrid(project3D) {
  const gridSize = 220;
  const gridStep = 44;

  ctx.save();
  ctx.strokeStyle = 'rgba(0, 242, 254, 0.05)';
  ctx.lineWidth = 1;

  // Grid lines along X
  for (let z = -gridSize; z <= gridSize; z += gridStep) {
    const p1 = project3D(-gridSize, 0, z);
    const p2 = project3D(gridSize, 0, z);
    if (p1 && p2) {
      ctx.beginPath();
      ctx.moveTo(p1.screenX, p1.screenY);
      ctx.lineTo(p2.screenX, p2.screenY);
      ctx.stroke();
    }
  }

  // Grid lines along Z
  for (let x = -gridSize; x <= gridSize; x += gridStep) {
    const p1 = project3D(x, 0, -gridSize);
    const p2 = project3D(x, 0, gridSize);
    if (p1 && p2) {
      ctx.beginPath();
      ctx.moveTo(p1.screenX, p1.screenY);
      ctx.lineTo(p2.screenX, p2.screenY);
      ctx.stroke();
    }
  }

  // Distinct Channel Lanes on Grid Plane
  if (channelLanes.length > 0) {
    const numChannels = channelLanes.length;
    const laneSpacing = Math.min(90, Math.max(48, 440 / numChannels));

    channelLanes.forEach((ch, idx) => {
      const x = (idx - (numChannels - 1) / 2) * laneSpacing;
      
      // Persistent channel lane guideline along Z
      const pLaneStart = project3D(x, 0, -gridSize);
      const pLaneEnd = project3D(x, 0, gridSize);
      if (pLaneStart && pLaneEnd) {
        ctx.strokeStyle = 'rgba(0, 242, 254, 0.12)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(pLaneStart.screenX, pLaneStart.screenY);
        ctx.lineTo(pLaneEnd.screenX, pLaneEnd.screenY);
        ctx.stroke();
      }

      // Channel name tag label at the front of each lane
      const pTag = project3D(x, 0, gridSize + 18);
      if (pTag) {
        ctx.fillStyle = 'rgba(0, 242, 254, 0.65)';
        const fontSize = Math.max(9, Math.round(10.5 * pTag.scale));
        ctx.font = `${fontSize}px monospace`;
        ctx.textAlign = 'center';
        ctx.fillText(ch, pTag.screenX, pTag.screenY);
      }
    });
  }

  ctx.restore();
}

/**
 * Draws Subtle Evidence Space Reticle Indicator (Replacing giant axis labels)
 */
function drawEvidenceSpaceIndicator(project3D) {
  const origin = project3D(0, 0, 0);
  const axisLen = 35;
  const pX = project3D(axisLen, 0, 0);
  const pY = project3D(0, axisLen, 0); // Elevation
  const pZ = project3D(0, 0, axisLen);

  if (!origin) return;

  ctx.save();
  ctx.lineWidth = 1;

  // Mini X (Channel) Axis
  if (pX) {
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.35)';
    ctx.beginPath();
    ctx.moveTo(origin.screenX, origin.screenY);
    ctx.lineTo(pX.screenX, pX.screenY);
    ctx.stroke();
  }

  // Mini Y (Anomaly Elevation) Axis
  if (pY) {
    ctx.strokeStyle = 'rgba(192, 132, 252, 0.4)';
    ctx.beginPath();
    ctx.moveTo(origin.screenX, origin.screenY);
    ctx.lineTo(pY.screenX, pY.screenY);
    ctx.stroke();
  }

  // Mini Z (Telemetry Value) Axis
  if (pZ) {
    ctx.strokeStyle = 'rgba(251, 146, 60, 0.35)';
    ctx.beginPath();
    ctx.moveTo(origin.screenX, origin.screenY);
    ctx.lineTo(pZ.screenX, pZ.screenY);
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Draws a 3D Temporal Relationship Edge (Thin, precise lines with traveling pulse)
 */
function drawRelationshipEdge(rel, nodeA, nodeB) {
  const pA = nodeA.proj;
  const pB = nodeB.proj;
  if (!pA || !pB) return;

  const isConnectedToSelected = selectedNode && (selectedNode === nodeA || selectedNode === nodeB);
  const isConnectedToHovered = hoveredNode && (hoveredNode === nodeA || hoveredNode === nodeB);
  const isHighlighted = isConnectedToSelected || isConnectedToHovered;

  ctx.save();
  ctx.beginPath();
  ctx.moveTo(pA.screenX, pA.screenY);

  // Curved quadratic bezier in 3D perspective
  const midX = (pA.screenX + pB.screenX) / 2;
  const midY = (pA.screenY + pB.screenY) / 2 - 20;
  ctx.quadraticCurveTo(midX, midY, pB.screenX, pB.screenY);

  ctx.strokeStyle = isHighlighted ? 'rgba(0, 242, 254, 0.85)' : 'rgba(0, 242, 254, 0.38)';
  ctx.lineWidth = isHighlighted ? 2.0 : Math.max(1, 1.3 * ((pA.scale + pB.scale) / 2));
  ctx.shadowColor = '#00f2fe';
  ctx.shadowBlur = isHighlighted ? 12 : 5;
  ctx.stroke();

  // Dynamic particle pulse along the active edge
  const pulsePhase = (performance.now() * 0.0018) % 1;
  const px = (1 - pulsePhase) * (1 - pulsePhase) * pA.screenX + 2 * (1 - pulsePhase) * pulsePhase * midX + pulsePhase * pulsePhase * pB.screenX;
  const py = (1 - pulsePhase) * (1 - pulsePhase) * pA.screenY + 2 * (1 - pulsePhase) * pulsePhase * midY + pulsePhase * pulsePhase * pB.screenY;

  ctx.fillStyle = '#ffffff';
  ctx.shadowColor = '#00f2fe';
  ctx.shadowBlur = 6;
  ctx.beginPath();
  ctx.arc(px, py, 2.0, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}

/**
 * Draws a 3D Evidence Node with tightly controlled sizing (Small core + subtle halo)
 */
function drawEvidenceNode(node, ageSec) {
  const proj = node.proj;
  if (!proj) return;

  const isSelected = selectedNode === node;
  const isHovered = hoveredNode === node;

  // Tightly controlled visual radius range (Not creating giant nodes for high anomalies)
  let baseRadius = 2.4;
  if (node.isIncidentGroup) {
    baseRadius = 3.4;
  } else if (node.isAnomaly) {
    baseRadius = 3.0;
  }

  const radius = Math.max(1.8, Math.min(6.5, baseRadius * proj.scale * (isSelected ? 1.4 : (isHovered ? 1.25 : 1.0))));

  ctx.save();

  // Color & Halo configuration
  let fillColor = 'rgba(255, 255, 255, 0.85)';
  let glowColor = 'rgba(0, 242, 254, 0.45)';
  let alpha = ageSec > 8.0 ? 0.65 : 1.0; // Historical events settle into subtle resting opacity

  if (node.isIncidentGroup) {
    fillColor = `rgba(244, 63, 94, ${alpha})`; // Coral red for events on affected channels in investigation
    glowColor = '#f43f5e';
  } else if (node.isAnomaly) {
    fillColor = `rgba(192, 132, 252, ${alpha})`; // Purple for anomaly events
    glowColor = '#a855f7';
  } else {
    fillColor = `rgba(255, 255, 255, ${alpha * 0.9})`;
    glowColor = 'rgba(0, 242, 254, 0.4)';
  }

  // Newly visible event birth pulse (Purely visual animation parameter, e.g. 3 seconds duration)
  if (ageSec >= 0 && ageSec < 3.0) {
    const birthProgress = ageSec / 3.0;
    const pulseRadius = radius + (1 - birthProgress) * 7;
    ctx.strokeStyle = `rgba(0, 242, 254, ${(1 - birthProgress) * 0.75})`;
    ctx.lineWidth = 1.0;
    ctx.beginPath();
    ctx.arc(proj.screenX, proj.screenY, pulseRadius, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Subtle halo / glow (Intensity scaled with anomaly score rather than inflating radius)
  const haloIntensity = 4 + (node.anomalyScore * 8);
  ctx.shadowColor = glowColor;
  ctx.shadowBlur = isSelected ? 16 : (isHovered ? 12 : haloIntensity);

  // Crisp Node Core
  ctx.fillStyle = fillColor;
  ctx.beginPath();
  ctx.arc(proj.screenX, proj.screenY, radius, 0, Math.PI * 2);
  ctx.fill();

  // Selection / Targeting Reticle Ring
  if (isSelected || isHovered) {
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(proj.screenX, proj.screenY, radius + 3.5, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Initializes Star Dust & Deep-Space Starfield Canvas in Background
 */
function initBackgroundCanvas(bgCanvas) {
  if (!bgCanvas) return;
  const ctx = bgCanvas.getContext('2d');
  if (!ctx) return;

  let width = 0;
  let height = 0;
  let dpr = window.devicePixelRatio || 1;
  let animId = null;

  const STAR_COUNT = 85;
  const stars = [];

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const parent = bgCanvas.parentElement;
    width = parent ? parent.clientWidth : window.innerWidth;
    height = parent ? parent.clientHeight : window.innerHeight;
    bgCanvas.width = Math.floor(width * dpr);
    bgCanvas.height = Math.floor(height * dpr);
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
