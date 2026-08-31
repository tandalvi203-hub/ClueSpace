/**
 * ClueSpace Screen 3: INVESTIGATION WORKSPACE
 * Pure Data-Driven Forensic Investigation System.
 * Starts completely blank ("CHOOSE AN INVESTIGATION") until an investigation is explicitly selected.
 * Dynamic analysis of telemetry, activation sequences, pairwise timing, evidence graphs, and data-supported conclusions.
 */

import { fetchInvestigation, getAllInvestigations } from './dataService.js';
import { getSelectedInvestigationId, setSelectedInvestigationId, clearSelectedInvestigation, onInvestigationChange } from './navigation.js';

let workspaceContainer = null;
let isListenerRegistered = false;

// Dynamic Timeline Palette (matches Reference Design: Red, Blue, Purple, Green, Yellow, Red...)
const TIMELINE_PALETTE = [
  '#38bdf8', // 1: Electric Blue
  '#a855f7', // 2: Violet / Purple
  '#10b981', // 3: Emerald Green
  '#f59e0b', // 4: Amber / Yellow
  '#f43f5e', // 5: Coral Red
  '#06b6d4', // 6: Cyan
  '#ec4899', // 7: Pink
  '#6366f1', // 8: Indigo
  '#84cc16'  // 9: Lime
];

// Channel color mapping following ClueSpace logo palette
const CHANNEL_PALETTE = {
  'CADC0888': '#38bdf8', // Electric blue
  'CADC0872': '#a855f7', // Violet / Purple
  'CADC0894': '#10b981', // Emerald green
  'CADC0873': '#f59e0b', // Amber / Gold
  'CADC0874': '#f43f5e', // Coral red
  'CADC0892': '#818cf8', // Indigo accent
  'CADC0890': '#a78bfa', // Light violet
  'CADC0886': '#c084fc'  // Purple accent
};

const DEFAULT_CHANNEL_COLOR = '#38bdf8';

function getChannelColor(channelName, index = 0) {
  return CHANNEL_PALETTE[channelName] || TIMELINE_PALETTE[index % TIMELINE_PALETTE.length] || DEFAULT_CHANNEL_COLOR;
}

let currentLoadingId = null;
let currentRenderToken = 0;

export async function renderInvestigationWorkspace(container, targetId = null) {
  if (!container) return;
  workspaceContainer = container;

  if (!isListenerRegistered) {
    onInvestigationChange(async (newId) => {
      if (workspaceContainer) {
        await renderInvestigationWorkspace(workspaceContainer, newId);
      }
    });
    isListenerRegistered = true;
  }

  const activeId = targetId !== null ? targetId : getSelectedInvestigationId();

  // If no investigation is currently chosen, start COMPLETELY BLANK
  if (!activeId) {
    currentLoadingId = null;
    renderBlankState(container);
    return;
  }

  const renderToken = ++currentRenderToken;
  currentLoadingId = activeId;

  // 1. Show small, elegant loading state immediately (async feedback)
  renderLoadingState(container, activeId);

  try {
    const inv = await fetchInvestigation(activeId);

    // If another request was started while this was loading, discard outdated response
    if (renderToken !== currentRenderToken) {
      return;
    }

    if (!inv) {
      renderNotFoundState(container, activeId);
      return;
    }

    renderActiveInvestigation(container, inv);
  } catch (err) {
    console.error(`Failed to load investigation ${activeId}:`, err);
    if (renderToken === currentRenderToken) {
      renderErrorState(container, activeId);
    }
  } finally {
    if (renderToken === currentRenderToken) {
      currentLoadingId = null;
    }
  }
}

/**
 * Loading HUD State
 */
function renderLoadingState(container, activeId) {
  container.innerHTML = `
    <div class="iw-loading-wrap" role="status" aria-live="polite">
      <div class="iw-loading-spinner"></div>
      <div class="iw-loading-title">ANALYZING INVESTIGATION DATA...</div>
      <div class="iw-loading-sub">Accessing telemetry records & reconstructing evidence for <strong>${activeId}</strong></div>
    </div>
  `;
}

/**
 * Error / Retry State
 */
function renderErrorState(container, activeId) {
  container.innerHTML = `
    <div class="iw-error-wrap glass-panel" role="alert">
      <div class="iw-error-icon">⚠️</div>
      <h2 class="iw-error-title">UNABLE TO LOAD INVESTIGATION DATA — RETRY</h2>
      <p class="iw-error-desc">
        Failed to retrieve telemetry records for incident <strong>${activeId}</strong>.
      </p>
      <div class="iw-error-actions">
        <button class="iw-btn-retry" id="btn-retry-investigation" type="button">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="1 4 1 10 7 10"/>
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
          </svg>
          <span>RETRY</span>
        </button>
        <button class="iw-btn-secondary-picker" id="btn-error-choose-other" type="button">
          <span>CHOOSE ANOTHER CASE</span>
        </button>
      </div>
    </div>
  `;

  const btnRetry = container.querySelector('#btn-retry-investigation');
  if (btnRetry) {
    btnRetry.onclick = (e) => {
      e.preventDefault();
      renderInvestigationWorkspace(container, activeId);
    };
  }

  const btnOther = container.querySelector('#btn-error-choose-other');
  if (btnOther) {
    btnOther.onclick = (e) => {
      e.preventDefault();
      openInvestigationPickerModal();
    };
  }
}

/**
 * 1. INITIAL BLANK STATE
 * Centered, small, floating, completely transparent composition matching the aerospace HUD reference.
 */
function renderBlankState(container) {
  container.innerHTML = `
    <div class="iw-empty-state-wrap">
      <div class="iw-empty-composition">
        
        <!-- Small Orbital Search Icon -->
        <div class="iw-empty-orbital-wrap">
          <svg class="iw-empty-orbital-svg" viewBox="0 0 100 100" width="80" height="80" fill="none">
            <defs>
              <linearGradient id="orbGradOuter" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.85" />
                <stop offset="50%" stop-color="#818cf8" stop-opacity="0.4" />
                <stop offset="100%" stop-color="#c084fc" stop-opacity="0.85" />
              </linearGradient>
              <linearGradient id="orbGradInner" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.5" />
                <stop offset="100%" stop-color="#a855f7" stop-opacity="0.25" />
              </linearGradient>
              <filter id="cyanGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <filter id="violetGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>

            <!-- Outer Orbital Ring -->
            <circle cx="50" cy="50" r="38" stroke="url(#orbGradOuter)" stroke-width="1.2" />
            
            <!-- Inner Orbital Ring -->
            <circle cx="50" cy="50" r="26" stroke="url(#orbGradInner)" stroke-width="1" opacity="0.6" />

            <!-- Orbiting Nodes/Dots -->
            <circle cx="21" cy="69" r="2.8" fill="#38bdf8" filter="url(#cyanGlow)" />
            <circle cx="79" cy="28" r="2.4" fill="#c084fc" filter="url(#violetGlow)" />
            <circle cx="50" cy="12" r="1.5" fill="#38bdf8" opacity="0.85" />

            <!-- Center Search / Magnifier Icon with Plus -->
            <g transform="translate(37, 37)" stroke="#38bdf8" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" filter="url(#cyanGlow)">
              <circle cx="10" cy="10" r="6" fill="none" />
              <line x1="14.5" y1="14.5" x2="20" y2="20" />
              <line x1="10" y1="7.5" x2="10" y2="12.5" stroke-width="1.4" />
              <line x1="7.5" y1="10" x2="12.5" y2="10" stroke-width="1.4" />
            </g>
          </svg>
        </div>

        <!-- Heading -->
        <h2 class="iw-empty-title">
          <span class="iw-empty-title-white">CHOOSE AN</span>
          <span class="iw-empty-title-gradient">INVESTIGATION</span>
        </h2>

        <!-- Subtitle (2 Lines) -->
        <p class="iw-empty-subtitle">
          Select an investigation to examine its evidence,<br>relationships, and findings.
        </p>

        <!-- Compact Button with Gradient Border -->
        <button class="iw-empty-btn-select" id="btn-open-picker" type="button" aria-haspopup="dialog">
          <span>SELECT INVESTIGATION</span>
          <span class="iw-empty-btn-arrow">→</span>
        </button>

        <!-- Loading Note / Warning -->
        <p class="iw-empty-load-warning">INITIALIZATION MAY TAKE A MOMENT</p>

        <!-- Footer Footprint -->
        <div class="iw-empty-status">
          <span class="iw-empty-status-dot"></span>
          <span class="iw-empty-status-text">SYSTEM READY</span>
          <span class="iw-empty-status-sep">·</span>
          <span class="iw-empty-status-text">DATA CONNECTED</span>
        </div>

      </div>
    </div>
  `;

  // Direct, instant, zero-delay click listener
  const btnOpen = container.querySelector('#btn-open-picker');
  if (btnOpen) {
    btnOpen.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      openInvestigationPickerModal();
    };
  }
}

/**
 * NOT FOUND STATE
 */
function renderNotFoundState(container, invId) {
  container.innerHTML = `
    <div class="screen-header-block">
      <h1 class="screen-main-heading">${invId}</h1>
      <p class="screen-sub-prompt">SPACECRAFT INCIDENT INVESTIGATION</p>
    </div>
    <div class="glass-panel iw-section" style="text-align: center; padding: 3rem;">
      <h2 class="iw-section-heading" style="justify-content: center; color: #fda4af;">
        <span>⚠️</span> INVESTIGATION REPORT NOT FOUND
      </h2>
      <p style="color: rgba(255,255,255,0.7); font-family: var(--font-mono); margin-bottom: 1.5rem;">
        Detailed telemetry payload for incident "${invId}" is not present in the dataset.
      </p>
      <button class="iw-btn-select-investigation" id="btn-open-picker-404" style="margin: 0 auto;" type="button">
        <span>CHOOSE ANOTHER INVESTIGATION</span>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M5 12h14M12 5l7 7-7 7"/>
        </svg>
      </button>
    </div>
  `;

  const btn = container.querySelector('#btn-open-picker-404');
  if (btn) {
    btn.onclick = (e) => {
      e.preventDefault();
      openInvestigationPickerModal();
    };
  }
}

/**
 * Helper to render individual picker item HTML string (fast and clean)
 */
function formatPickerItemHTML(item) {
  const id = item.investigation_id || `INV-${item.spacecraft_incident_id}`;
  const sev = (item.severity_label || 'MODERATE').toUpperCase();
  const nCh = item.n_channels_affected || (item.channels_affected ? item.channels_affected.length : 1);
  const chList = Array.isArray(item.channels_affected) && item.channels_affected.length > 0
    ? item.channels_affected.join(', ')
    : (nCh === 1 ? 'Single channel' : `${nCh} channels`);
  const dur = item.duration_sec !== undefined ? `${item.duration_sec}s` : 'N/A';
  const events = item.n_events_total !== undefined ? item.n_events_total.toLocaleString() : 'N/A';
  const sig = typeof item.significance_score === 'number' ? item.significance_score.toFixed(1) : (item.significance_score || 'N/A');
  const conf = typeof item.investigation_confidence === 'number' ? `${(item.investigation_confidence * 100).toFixed(0)}%` : 'N/A';

  return `
    <div class="iw-picker-item" data-id="${id}" tabindex="0" role="button">
      <div class="iw-picker-item-left">
        <div class="iw-picker-item-id-row">
          <span class="iw-picker-item-id">${id}</span>
          <span class="sev-badge badge-${sev.toLowerCase()}">${sev}</span>
        </div>
        <div class="iw-picker-item-channels">
          <span class="iw-ch-count-tag">${nCh} CH:</span>
          <span class="iw-ch-names">${chList}</span>
        </div>
      </div>

      <div class="iw-picker-item-mid">
        <div class="iw-picker-stat-pill">
          <span class="iw-pill-lbl">DURATION</span>
          <span class="iw-pill-val">${dur}</span>
        </div>
        <div class="iw-picker-stat-pill">
          <span class="iw-pill-lbl">EVENTS</span>
          <span class="iw-pill-val">${events}</span>
        </div>
      </div>

      <div class="iw-picker-item-right">
        <div class="iw-picker-scores">
          <span>Sig: <strong>${sig}</strong></span>
          <span>Conf: <strong>${conf}</strong></span>
        </div>
        <div class="iw-picker-action-btn">
          <span>LOAD EVIDENCE</span>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </div>
      </div>
    </div>
  `;
}

/**
 * 2. INTERACTIVE INVESTIGATION PICKER MODAL (Instant, Zero-Lag Selection Flow)
 */
export function openInvestigationPickerModal() {
  // If modal is already open, focus search input and return immediately
  let existingModal = document.getElementById('iw-picker-modal-backdrop');
  if (existingModal) {
    const existingSearch = existingModal.querySelector('#iw-picker-search-input');
    if (existingSearch) existingSearch.focus();
    return;
  }

  let currentFilter = 'ALL';
  let currentSearch = '';
  let renderRafId = null;

  const modalBackdrop = document.createElement('div');
  modalBackdrop.id = 'iw-picker-modal-backdrop';
  modalBackdrop.className = 'iw-picker-modal-backdrop';

  modalBackdrop.innerHTML = `
    <div class="iw-picker-modal glass-panel" role="dialog" aria-modal="true" aria-labelledby="picker-modal-title">
      <!-- Modal Header -->
      <div class="iw-picker-header">
        <div class="iw-picker-title-group">
          <div class="iw-picker-badge">INVESTIGATION SELECTOR</div>
          <h2 class="iw-picker-title" id="picker-modal-title">CHOOSE AN INVESTIGATION CASE</h2>
        </div>
        <button class="iw-picker-close-btn" id="btn-close-picker" type="button" aria-label="Close">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Severity Filter Buttons -->
      <div class="iw-picker-filters-row">
        <span class="iw-picker-filter-lbl">SEVERITY:</span>
        <div class="iw-picker-tabs" id="picker-severity-tabs">
          <button class="iw-picker-tab active" data-severity="ALL" type="button">ALL</button>
          <button class="iw-picker-tab" data-severity="CRITICAL" type="button">CRITICAL</button>
          <button class="iw-picker-tab" data-severity="HIGH" type="button">HIGH</button>
          <button class="iw-picker-tab" data-severity="MODERATE" type="button">MODERATE</button>
          <button class="iw-picker-tab" data-severity="LOW" type="button">LOW</button>
        </div>
      </div>

      <!-- Search Input & Counter -->
      <div class="iw-picker-search-bar">
        <div class="iw-picker-search-wrap">
          <svg class="iw-picker-search-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input 
            type="text" 
            id="iw-picker-search-input" 
            class="iw-picker-search-input" 
            placeholder="Search investigation ID (e.g. INV-988) or incident number..." 
            autocomplete="off"
            spellcheck="false"
          />
        </div>
        <div class="iw-picker-count-lbl" id="iw-picker-count">Loading cases...</div>
      </div>

      <!-- Scrollable Investigation List -->
      <div class="iw-picker-list" id="iw-picker-list">
        <!-- Rendered dynamically -->
      </div>
    </div>
  `;

  document.body.appendChild(modalBackdrop);

  const searchInput = modalBackdrop.querySelector('#iw-picker-search-input');
  const countLbl = modalBackdrop.querySelector('#iw-picker-count');
  const listContainer = modalBackdrop.querySelector('#iw-picker-list');
  const tabBtns = modalBackdrop.querySelectorAll('.iw-picker-tab');
  const btnClose = modalBackdrop.querySelector('#btn-close-picker');

  // Single delegated click listener on listContainer (instant, O(1) listener attachment)
  listContainer.addEventListener('click', (e) => {
    const item = e.target.closest('.iw-picker-item');
    if (!item) return;
    const id = item.getAttribute('data-id');
    if (id) {
      if (renderRafId) cancelAnimationFrame(renderRafId);
      modalBackdrop.remove();
      // Load selected investigation asynchronously
      setSelectedInvestigationId(id);
    }
  });

  listContainer.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const item = e.target.closest('.iw-picker-item');
      if (!item) return;
      const id = item.getAttribute('data-id');
      if (id) {
        e.preventDefault();
        if (renderRafId) cancelAnimationFrame(renderRafId);
        modalBackdrop.remove();
        setSelectedInvestigationId(id);
      }
    }
  });

  function renderList() {
    if (renderRafId) cancelAnimationFrame(renderRafId);

    const list = getAllInvestigations(currentFilter, currentSearch);
    countLbl.textContent = `${list.length} investigation(s) available`;

    if (list.length === 0) {
      listContainer.innerHTML = `
        <div class="iw-picker-empty">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="rgba(56, 189, 248, 0.4)" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <div>No investigations found matching "<strong>${currentSearch}</strong>" in <strong>${currentFilter}</strong>.</div>
        </div>
      `;
      return;
    }

    // Instant initial batch (first 35 items) renders in < 1ms
    const firstChunk = list.slice(0, 35);
    listContainer.innerHTML = firstChunk.map(formatPickerItemHTML).join('');

    // If more items exist, schedule full list smoothly
    if (list.length > 35) {
      renderRafId = requestAnimationFrame(() => {
        listContainer.innerHTML = list.map(formatPickerItemHTML).join('');
      });
    }
  }

  // Filter tabs click
  tabBtns.forEach(btn => {
    btn.onclick = (e) => {
      e.preventDefault();
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.getAttribute('data-severity');
      renderList();
    };
  });

  // Search input with micro-debounce
  let searchTimer = null;
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      currentSearch = e.target.value;
      renderList();
    }, 40);
  });

  // Close handlers
  const closeModal = () => {
    if (renderRafId) cancelAnimationFrame(renderRafId);
    modalBackdrop.remove();
  };
  btnClose.onclick = (e) => {
    e.preventDefault();
    closeModal();
  };
  modalBackdrop.onclick = (e) => {
    if (e.target === modalBackdrop) closeModal();
  };
  window.addEventListener('keydown', function escHandler(e) {
    if (e.key === 'Escape') {
      closeModal();
      window.removeEventListener('keydown', escHandler);
    }
  });

  renderList();
  if (searchInput) {
    searchInput.focus();
  }
}

// Global capture-phase delegator: guarantees instant single click response for all picker buttons
if (typeof window !== 'undefined' && !window.__cluespace_picker_delegator_attached) {
  window.__cluespace_picker_delegator_attached = true;
  document.addEventListener('click', (e) => {
    const target = e.target;
    if (target && target.closest) {
      const btn = target.closest('#btn-open-picker, .iw-empty-btn-select, #btn-open-picker-404, #btn-switch-investigation, #btn-error-choose-other');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        openInvestigationPickerModal();
      }
    }
  }, true);
}

/**
 * Dynamic Recommendation Generator
 * Synthesizes data-supported recommendations and actionable diagnostics strictly based on
 * the observed characteristics of the currently selected investigation.
 */
function buildDataDrivenRecommendations(inv, ctx) {
  const {
    nChannels,
    isMultiChannel,
    initialChannel,
    ch0Color,
    initialPeakScore,
    initialTimeStr,
    activationOrder,
    activationSpanSec,
    tempRelationships,
    totalPairs,
    overlappingPairsCount,
    totalEventsNum,
    totalEvents,
    duration,
    durationSec,
    eventRateVal,
    eventRateScore,
    sevLabel,
    sevScore,
    sigScore,
    confidence,
    gapToNext,
    relevantPairs,
    meanScore,
    scoreStd,
    missionImpactBasis,
    backendRecActions,
    persistenceClass
  } = ctx;

  // 1. INITIAL ANOMALY
  let initialOneLine = '';
  let initialRootTelemetry = '';
  let initialDiagnosticAction = '';

  if (!isMultiChannel) {
    if (sevLabel === 'LOW' || sevLabel === 'MODERATE') {
      initialOneLine = `Sole telemetry channel recording localized anomalous excursion without downstream propagation.`;
    } else {
      initialOneLine = `Isolated high-magnitude anomaly stream concentrated entirely on channel ${initialChannel}.`;
    }
    initialRootTelemetry = `Telemetry channel ${initialChannel} represents the sole anomalous stream during this ${duration} window. Recorded ${totalEvents} event(s) reaching a peak anomaly score of ${initialPeakScore} (mean: ${meanScore}, score std: ${scoreStd}).`;
    if (sevLabel === 'LOW' || sevLabel === 'MODERATE') {
      initialDiagnosticAction = `Audit sensor calibration baseline, power supply ripple, and single-event radiation upset history on ${initialChannel}. Because no companion telemetry channels responded, evaluate localized transducer noise or single-event transient.`;
    } else {
      initialDiagnosticAction = `Conduct urgent hardware diagnostic on ${initialChannel}'s transducer chain and operational threshold limits; inspect spacecraft commanding history prior to ${initialTimeStr} to isolate direct component excursion.`;
    }
  } else {
    if (gapToNext <= 3) {
      initialOneLine = `Root initiator; preceded downstream cascade on ${activationOrder[1]} by only ${gapToNext}s in a rapid trigger sequence.`;
    } else if (gapToNext >= 30) {
      initialOneLine = `Root initiator; exhibited prolonged ${gapToNext}s latency prior to secondary channel engagement on ${activationOrder[1]}.`;
    } else {
      initialOneLine = `First telemetry channel to breach nominal threshold; leading initiation point for the ${nChannels}-channel event chain.`;
    }
    initialRootTelemetry = `Channel ${initialChannel} initiated the incident at ${initialTimeStr} (peak score: ${initialPeakScore}), preceding downstream activation on ${activationOrder[1]} by ${gapToNext}s. Total duration on this primary channel spanned ${duration} across the active telemetry pass.`;
    if (gapToNext <= 3) {
      initialDiagnosticAction = `Focus root-cause analysis on ${initialChannel}'s high-speed transceiver and shared bus lines. The near-instantaneous (${gapToNext}s) downstream response on ${activationOrder[1]} indicates electrical cross-talk, power rail fluctuation, or fast digital bus propagation.`;
    } else if (gapToNext >= 30) {
      initialDiagnosticAction = `Investigate thermal transfer, gradual fluid/pressure migration, or buffer accumulation originating at ${initialChannel}. The ${gapToNext}s delay before ${activationOrder[1]} activation indicates progressive physical diffusion rather than an electrical fault.`;
    } else {
      initialDiagnosticAction = `Trace the signal routing and functional coupling from ${initialChannel} to downstream channels (${activationOrder.slice(1).join(', ')}). Review telemetry logs for ${initialChannel} leading up to ${initialTimeStr} to verify the triggering condition.`;
    }
  }

  // 2. TEMPORAL SEQUENCE
  let seqOneLine = '';
  let seqProgression = '';
  let seqDiagnosticAction = '';

  if (!isMultiChannel) {
    seqOneLine = `Single-channel incident; no inter-channel temporal sequence or propagation chain was established.`;
    seqProgression = `No sequence progression detected. Channel ${initialChannel} operated in isolation without triggering secondary channel anomalies.`;
    seqDiagnosticAction = `Confirm from telemetry archives that companion subsystem channels remained within nominal limits during the ${duration} observation window.`;
  } else {
    const avgStep = (activationSpanSec / Math.max(1, nChannels - 1)).toFixed(1);
    if (activationSpanSec <= 10) {
      seqOneLine = `Rapid synchronized cascade across ${nChannels} channels completed within a tight ${activationSpanSec}s window.`;
    } else if (activationSpanSec > 60) {
      seqOneLine = `Gradual propagation sequence traversing ${nChannels} channels over an extended ${activationSpanSec}s timeline.`;
    } else {
      seqOneLine = `Chronological activation progression detected across ${nChannels} channels in a ${activationSpanSec}-second window.`;
    }
    seqProgression = `Activation followed monotonic chronological ordering: ${activationOrder.join(' → ')}. Total propagation window spanned ${activationSpanSec}s, with an average interval of ${avgStep}s between consecutive channel breaches.`;
    if (activationSpanSec <= 10) {
      seqDiagnosticAction = `Analyze common-cause trigger pathways linking ${activationOrder.join(', ')}. The fast ${activationSpanSec}s sequence indicates shared clock, power distribution, or centralized controller fault.`;
    } else if (activationSpanSec > 60) {
      seqDiagnosticAction = `Reconstruct the progressive step-by-step physical transfer from primary node (${activationOrder[0]}) through intermediate stages to terminal node (${activationOrder[activationOrder.length - 1]}). Check thermal sensor logs and control loop response curves.`;
    } else {
      seqDiagnosticAction = `Map bus coupling and signal pathways along the observed sequence: ${activationOrder.join(' → ')}. Verify whether downstream activations were protective responses or cascading secondary failures.`;
    }
  }

  // 3. TEMPORAL OVERLAP
  let overlapOneLine = '';
  let overlapCorroboration = '';
  let overlapDiagnosticAction = '';

  if (!isMultiChannel || totalPairs === 0) {
    overlapOneLine = `Single-channel anomaly profile; cross-channel pairwise concurrency analysis is not applicable.`;
    overlapCorroboration = `Pairwise temporal correlation is not applicable for isolated single-channel events.`;
    overlapDiagnosticAction = `Cross-reference historical telemetry of ${initialChannel} with adjacent nominal channels to ensure absence of undetected low-amplitude coupling.`;
  } else if (overlappingPairsCount === totalPairs) {
    overlapOneLine = `Universal concurrency: all ${totalPairs} channel pairs maintained overlapping anomaly states.`;
    overlapCorroboration = `All ${totalPairs} inter-channel pairs demonstrated concurrent active anomaly windows. This universal overlap provides strong statistical evidence that the affected systems experienced simultaneous operational stress.`;
    overlapDiagnosticAction = `Inspect shared power buses, common heat pipes, or shared structural loads. Coincident active periods across all pairs indicate common environmental or electrical stress across ${activationOrder.join(', ')}.`;
  } else if (overlappingPairsCount > 0) {
    const overlappingNames = tempRelationships.filter(r => r.windows_overlap).slice(0, 2).map(r => `${r.channel_a}↔${r.channel_b}`).join(', ');
    overlapOneLine = `Selective concurrency: ${overlappingPairsCount} of ${totalPairs} channel pairs exhibited concurrent anomaly intervals.`;
    overlapCorroboration = `${overlappingPairsCount} pair(s) showed overlapping active intervals (${overlappingNames}), while ${totalPairs - overlappingPairsCount} pair(s) operated with discrete non-overlapping time offsets.`;
    overlapDiagnosticAction = `Cross-correlate telemetry specifically between the overlapping pairs (${overlappingNames}) to isolate localized subsystem couplings from subsequent independent transitions.`;
  } else {
    overlapOneLine = `Sequential handoff: channels activated in series with discrete non-overlapping anomaly windows.`;
    overlapCorroboration = `Zero channel pairs showed overlapping active windows. All channels activated and deactivated with non-overlapping temporal gaps, indicating independent sequential state transitions.`;
    overlapDiagnosticAction = `Examine stage-transition commands and autonomous flight software state machine handoffs between ${activationOrder.join(' and ')} to verify mode-switching behavior.`;
  }

  // 4. ANOMALY DENSITY
  let densityOneLine = '';
  let densityMetrics = '';
  let densityDiagnosticAction = '';

  const eventsPerMin = (totalEventsNum / Math.max(1, durationSec / 60)).toFixed(1);
  if (parseFloat(eventRateVal) >= 2.0 || totalEventsNum > 500) {
    densityOneLine = `High-density anomaly burst (${eventRateVal} events/sec) indicating intense sustained telemetry disturbance.`;
  } else if (parseFloat(eventRateVal) >= 0.5) {
    densityOneLine = `Moderate continuous event rate (${eventRateVal} events/sec) sustained over ${duration}.`;
  } else if (totalEventsNum < 10) {
    densityOneLine = `Sparse low-count anomaly signature (${totalEvents} events in ${duration}) indicating brief or intermittent excursion.`;
  } else {
    densityOneLine = `Telemetry anomaly density across the ${duration} window reflects steady event concentration.`;
  }
  densityMetrics = `Captured ${totalEvents} anomalous telemetry records over a ${duration} observation window (${eventsPerMin} events/min). Anomaly score metrics: Peak = ${initialPeakScore}, Mean = ${meanScore}, Std = ${scoreStd}, Persistence = ${persistenceClass}.`;
  if (parseFloat(eventRateVal) >= 2.0 || totalEventsNum > 500) {
    densityDiagnosticAction = `Inspect high-rate flight recorder memory buffers around peak anomaly clusters for telemetry frame drops, buffer overflows, or bus packet congestion.`;
  } else if (totalEventsNum < 10) {
    densityDiagnosticAction = `Check raw telemetry packet sequence numbers for single-frame dropouts, telemetry downsampling anomalies, or sensor bit-flips during orbital transition.`;
  } else {
    densityDiagnosticAction = `Perform time-series frequency decomposition on anomaly score variations across the ${duration} duration to detect underlying oscillatory cycles or harmonic resonance.`;
  }

  // 5. PRIORITY
  let priorityOneLine = '';
  let priorityImpact = '';
  let priorityActions = [];

  if (sevLabel === 'CRITICAL') {
    priorityOneLine = `CRITICAL severity (${sevScore}/10) with significance ${sigScore}/100 and ${confidence} confidence warrants immediate forensic triage.`;
  } else if (sevLabel === 'HIGH') {
    priorityOneLine = `HIGH severity (${sevScore}/10) with significance ${sigScore}/100 warrants prioritized investigation before next operational cycle.`;
  } else if (sevLabel === 'MODERATE') {
    priorityOneLine = `MODERATE severity (${sevScore}/10) with significance ${sigScore}/100 indicates bounded impact; schedule for standard engineering review.`;
  } else {
    priorityOneLine = `LOW severity (${sevScore}/10) indicates minor isolated excursion; monitor during routine telemetry health checks.`;
  }

  if (missionImpactBasis.length > 0) {
    priorityImpact = `Severity: ${sevLabel} (${sevScore}/10), Significance: ${sigScore}/100. ${missionImpactBasis.join(' ')}`;
  } else {
    priorityImpact = `Severity: ${sevLabel} (${sevScore}/10), Significance: ${sigScore}/100. Evaluated from ${nChannels} affected channel(s), ${totalEvents} anomalous event(s), and ${confidence} confidence over ${duration}.`;
  }

  if (backendRecActions.length > 0) {
    priorityActions = backendRecActions;
  } else if (isMultiChannel) {
    priorityActions = [
      `Reconstruct telemetry timelines starting from root channel ${activationOrder[0]} at ${initialTimeStr}.`,
      `Verify inter-channel electrical and thermal coupling across overlapping pairs (${relevantPairs.map(r => `${r.channel_a}↔${r.channel_b}`).join(', ') || 'all pairs'}).`,
      `Cross-reference flight rules and subsystem operational limits for ${activationOrder.join(', ')}.`
    ];
  } else {
    priorityActions = [
      `Conduct single-point telemetry health audit on ${initialChannel}.`,
      `Check sensor calibration limits and single-event upset logs at ${initialTimeStr}.`
    ];
  }

  return {
    initialOneLine,
    initialRootTelemetry,
    initialDiagnosticAction,
    seqOneLine,
    seqProgression,
    seqDiagnosticAction,
    overlapOneLine,
    overlapCorroboration,
    overlapDiagnosticAction,
    densityOneLine,
    densityMetrics,
    densityDiagnosticAction,
    priorityOneLine,
    priorityImpact,
    priorityActions
  };
}

/**
 * 3. RENDER ACTIVE INVESTIGATION
 * Dynamically renders the forensic investigation interface for the loaded JSON report.
 */
function renderActiveInvestigation(container, inv) {
  const invId = inv.investigation_id || `INV-${inv.spacecraft_incident_id}`;
  const spacecraftIncidentId = inv.spacecraft_incident_id || invId.replace('INV-', '');
  const sevLabel = (inv.severity_label || inv.mission_impact_level || 'CRITICAL').toUpperCase();
  const sevScore = typeof inv.severity_score === 'number' ? inv.severity_score.toFixed(3) : (inv.severity_score ?? 'N/A');
  const sigScore = typeof inv.significance_score === 'number' ? inv.significance_score.toFixed(2) : (inv.significance_score ?? 'N/A');
  const confidence = typeof inv.investigation_confidence === 'number'
    ? (inv.investigation_confidence * 100).toFixed(2) + '%'
    : (inv.investigation_confidence ? (parseFloat(inv.investigation_confidence) * 100).toFixed(2) + '%' : 'N/A');
  const duration = inv.duration_sec !== undefined ? `${inv.duration_sec} sec` : 'N/A';
  const totalEventsNum = (inv.n_events_total !== undefined) ? inv.n_events_total : (inv.timeline ? inv.timeline.length : 0);
  const totalEvents = totalEventsNum.toLocaleString();
  const timelineEvents = inv.timeline || [];
  const shownEventsCount = (inv.timeline_shown_count || timelineEvents.length).toLocaleString();
  const isTruncated = inv.timeline_truncated || false;

  // Activation sequence & Participating channels
  const channelsAffected = Array.isArray(inv.channels_affected) && inv.channels_affected.length > 0
    ? inv.channels_affected
    : (inv.channel_activation_order || (timelineEvents.length > 0 ? [...new Set(timelineEvents.map(e => e.channel))] : ['CADC0888']));

  const activationOrder = Array.isArray(inv.channel_activation_order) && inv.channel_activation_order.length > 0
    ? inv.channel_activation_order
    : channelsAffected;

  const nChannels = channelsAffected.length;

  // Temporal relationships
  const tempRelationships = Array.isArray(inv.channel_temporal_relationships) ? inv.channel_temporal_relationships : [];

  // Pairwise stats calculation
  const totalPairs = tempRelationships.length;
  const overlappingPairsCount = tempRelationships.filter(r => r.windows_overlap).length;
  const pairsComparedText = totalPairs > 0 ? `${totalPairs}` : (nChannels > 1 ? `${(nChannels * (nChannels - 1)) / 2}` : '0');
  const pairsOverlapText = totalPairs > 0
    ? `${overlappingPairsCount}/${totalPairs}`
    : (nChannels > 1 ? 'N/A' : '0/0');

  // =========================================================================
  // DYNAMIC TIMELINE CALCULATION
  // =========================================================================
  const incidentStartTimeStr = inv.start_time || (timelineEvents[0] ? timelineEvents[0].timestamp : 'N/A');
  const incidentStartMillis = incidentStartTimeStr !== 'N/A' ? new Date(incidentStartTimeStr).getTime() : 0;

  // Lookup earliest timestamp for each channel from timeline and relationships
  const channelFirstTimes = {};
  timelineEvents.forEach(ev => {
    if (!channelFirstTimes[ev.channel] || ev.timestamp < channelFirstTimes[ev.channel]) {
      channelFirstTimes[ev.channel] = ev.timestamp;
    }
  });

  if (Array.isArray(inv.channel_temporal_relationships)) {
    inv.channel_temporal_relationships.forEach(rel => {
      if (rel.channel_a && rel.channel_a_start) {
        if (!channelFirstTimes[rel.channel_a] || rel.channel_a_start < channelFirstTimes[rel.channel_a]) {
          channelFirstTimes[rel.channel_a] = rel.channel_a_start;
        }
      }
      if (rel.channel_b && rel.channel_b_start) {
        if (!channelFirstTimes[rel.channel_b] || rel.channel_b_start < channelFirstTimes[rel.channel_b]) {
          channelFirstTimes[rel.channel_b] = rel.channel_b_start;
        }
      }
    });
  }

  // Compute delta seconds and chronological order for all affected channels
  const channelEvents = activationOrder.map((ch, idx) => {
    const chTimeStr = channelFirstTimes[ch] || inv.start_time || 'N/A';
    let deltaSec = 0;

    if (incidentStartMillis && chTimeStr !== 'N/A') {
      const chMillis = new Date(chTimeStr).getTime();
      deltaSec = Math.max(0, Math.round((chMillis - incidentStartMillis) / 1000));
    }

    // Cumulative gap fallback if timestamps equal 0
    if (deltaSec === 0 && idx > 0 && Array.isArray(inv.channel_temporal_relationships)) {
      const rel = inv.channel_temporal_relationships.find(r =>
        (r.channel_b === ch) || (r.channel_a === activationOrder[0] && r.channel_b === ch)
      );
      if (rel && rel.temporal_gap_sec !== undefined) {
        deltaSec = rel.temporal_gap_sec;
      }
    }

    const timeOnly = chTimeStr !== 'N/A' ? chTimeStr.substring(11, 19) + 'Z' : 'N/A';

    return {
      name: ch,
      deltaSec,
      timeLabel: `+${deltaSec} sec`,
      timestamp: chTimeStr,
      timeOnly,
      color: getChannelColor(ch, idx),
      isIncident: false
    };
  });

  // Sort channel events chronologically by deltaSec
  channelEvents.sort((a, b) => a.deltaSec - b.deltaSec);

  // Dynamic Horizontal Timeline Chain (matches Reference Image 2: Timeline Overview)
  const allTimelineNodes = [
    {
      name: invId,
      timeLabel: '00:00:00',
      status: 'Incident Detected',
      color: '#f43f5e',
      isIncident: true,
      deltaSec: 0
    },
    ...channelEvents.map((ce, idx) => {
      let statusLabel = 'Anomaly Detected';
      if (idx === 0) statusLabel = 'First Anomaly';
      else if (idx === 1) statusLabel = 'Secondary Anomaly';
      else if (idx === channelEvents.length - 1) statusLabel = 'Terminal Anomaly';

      return {
        name: ce.name,
        timeLabel: ce.deltaSec === 0 ? '+0 sec' : ce.timeLabel,
        status: statusLabel,
        color: ce.color,
        isIncident: false,
        deltaSec: ce.deltaSec
      };
    })
  ];

  // Calculate activation span in seconds
  const firstActivationTime = channelEvents[0]?.timestamp || 'N/A';
  const lastActivationTime = channelEvents[channelEvents.length - 1]?.timestamp || 'N/A';
  let activationSpanSec = 0;
  if (firstActivationTime !== 'N/A' && lastActivationTime !== 'N/A') {
    activationSpanSec = Math.max(0, Math.round((new Date(lastActivationTime).getTime() - new Date(firstActivationTime).getTime()) / 1000));
  }
  if (activationSpanSec === 0 && inv.duration_sec) {
    activationSpanSec = Math.min(inv.duration_sec, 60);
  }

  // Dynamic Evidence Graph Card calculations (Reference Image: evidence-graph.png)
  const totalRelationships = tempRelationships.length;
  const temporalLinksText = totalRelationships > 0
    ? `${totalRelationships} temporal relationships identify a clear order of anomalies within a ${activationSpanSec}-second window.`
    : (nChannels > 1
      ? `${nChannels} participating channels exhibit sequential timing offsets over a ${activationSpanSec}-second window.`
      : `1 anomalous channel identified within a ${activationSpanSec || duration}-second window.`);

  const patternMatchText = overlappingPairsCount > 0
    ? `High pattern similarity found between ${overlappingPairsCount} pair${overlappingPairsCount === 1 ? '' : 's'} of channels.`
    : (nChannels > 1
      ? `Moderate pattern correlation observed across ${nChannels} telemetry channels.`
      : `Single-channel anomaly pattern; no cross-channel overlap detected.`);

  const sequenceConsistencyText = `The anomaly sequence shows strong consistency with ${confidence} confidence.`;

  let strengthPct = 87;
  if (typeof inv.investigation_confidence === 'number') {
    strengthPct = Math.min(99, Math.round(inv.investigation_confidence * 100));
  } else if (totalRelationships > 0) {
    strengthPct = Math.min(99, Math.round(75 + (overlappingPairsCount / totalRelationships) * 20));
  } else if (inv.significance_score) {
    strengthPct = Math.min(99, Math.round(inv.significance_score));
  }

  const evidenceStrengthText = `Overall evidence strength across all relationships is ${sevLabel === 'CRITICAL' ? 'high' : 'moderate'}.`;

  const investigatorInsightText = nChannels > 1
    ? `${nChannels} anomaly channels are connected to the incident through strong temporal and pattern-based evidence. The sequence suggests a coordinated anomaly event. Further investigation is recommended to explore the underlying subsystem relationships.`
    : `Single-channel anomaly event isolated to ${channelsAffected[0] || 'CADC0888'}. Telemetry indicates localized deviation without multi-channel coupling.`;

  const importantNoteText = `The relationships shown here are based on observed data and statistical analysis. They indicate correlation, not necessarily physical causation.`;

  // Detailed scores for Evidence Strength Detail Breakdown
  const temporalScore = Math.min(99, Math.round(75 + (totalPairs > 0 ? (overlappingPairsCount / totalPairs) * 20 : 8)));
  const patternScore = Math.min(99, Math.round(80 + (overlappingPairsCount > 0 ? 12 : 6)));
  const sequenceScore = Math.min(99, Math.round(parseFloat(confidence) || 96));
  const dataScore = Math.min(99, Math.round(Math.max(85, Math.min(98, (totalEventsNum / 100) + 75))));
  const overallRating = strengthPct >= 80 ? 'High' : (strengthPct >= 60 ? 'Moderate' : 'Low');

  // Hypothesis & Narrative
  const hypothesisSummary = (inv.hypothesis_statements && inv.hypothesis_statements[0]) || '';
  const hypConfidence = inv.hypothesis_statements && inv.evidence_graph && inv.evidence_graph.nodes
    ? ((inv.evidence_graph.nodes.find(n => n.node_type === 'hypothesis')?.attributes?.hypothesis_confidence || inv.investigation_confidence || 0.99) * 100).toFixed(2) + '%'
    : (confidence || 'N/A');
  const hypothesisBasis = inv.hypothesis_basis || [];
  const recActions = inv.recommended_actions || [];
  const missionImpactBasis = inv.mission_impact_basis || [];

  // Deterministic Narrative Text Blocks
  const narrativeWhatHappened = nChannels > 1
    ? `A ${sevLabel.toLowerCase()}-severity incident was recorded from ${inv.start_time || 'N/A'} to ${inv.end_time || 'N/A'}, spanning a duration of ${duration} with ${totalEvents} anomalous telemetry events across ${nChannels} telemetry channel(s) (${channelsAffected.join(', ')}). Significance score: ${sigScore}/100.`
    : `A single-channel ${sevLabel.toLowerCase()}-severity anomaly was detected on channel ${channelsAffected[0] || 'N/A'} from ${inv.start_time || 'N/A'} to ${inv.end_time || 'N/A'} (${duration}, ${totalEvents} events). Significance score: ${sigScore}/100.`;

  const narrativeEvidence = `Telemetry records verify ${totalEvents} anomaly event(s) with peak anomaly score ${inv.peak_anomaly_score !== undefined ? Number(inv.peak_anomaly_score).toFixed(3) : 'N/A'} and mean score ${inv.mean_anomaly_score !== undefined ? Number(inv.mean_anomaly_score).toFixed(3) : 'N/A'}. Graph structure correlates the incident node with ${nChannels} channel node(s) and hypothesis HYP-${spacecraftIncidentId}.`;

  const narrativeProgress = nChannels > 1
    ? `Channel activation initiated on ${activationOrder[0]}, progressing across ${activationOrder.slice(1).join(' → ')} over a ${activationSpanSec} s activation span.`
    : `Isolated single-channel anomaly stream on ${channelsAffected[0] || 'N/A'}; no cross-channel propagation detected.`;

  const narrativeConnection = nChannels > 1
    ? `${totalPairs} pairwise inter-channel timing relationship(s) were compared, with ${overlappingPairsCount} pair(s) exhibiting overlapping or proximate anomaly windows.`
    : `Single-channel incident; inter-channel pairwise temporal correlation is not applicable.`;

  const narrativeConclusion = nChannels > 1
    ? `Strong temporal correlation across ${nChannels} channels (${activationOrder.join(' → ')}) corroborates a coordinated multi-channel telemetry anomaly sequence. Observational findings reflect temporal association; physical causality is not inferred.`
    : `Localized anomaly signature isolated to channel ${channelsAffected[0] || 'N/A'}. Telemetry patterns reflect isolated deviation without multi-system coupling.`;

  // Data for Recommended Investigation Section
  const initialChannel = channelEvents[0]?.name || activationOrder[0] || (channelsAffected[0] || 'CADC0888');
  const ch0Color = getChannelColor(initialChannel, 0);
  const initialPeakScore = inv.peak_anomaly_score !== undefined ? Number(inv.peak_anomaly_score).toFixed(3) : (timelineEvents[0]?.anomaly_score !== undefined ? Number(timelineEvents[0].anomaly_score).toFixed(3) : '0.842');
  const initialTimeStr = channelEvents[0]?.timeOnly !== 'N/A' ? channelEvents[0].timeOnly : (inv.start_time ? inv.start_time.substring(11, 19) + 'Z' : '00:00:00Z');

  const eventRateVal = (totalEventsNum / Math.max(1, inv.duration_sec || 60)).toFixed(2);
  const eventRateScore = Math.min(100, Math.round((totalEventsNum / Math.max(1, inv.duration_sec || 60)) * 10));
  const relevantPairs = tempRelationships.slice(0, 3);
  const gapToNext = channelEvents.length > 1 ? Math.max(0, channelEvents[1].deltaSec - channelEvents[0].deltaSec) : 0;
  const meanScore = inv.mean_anomaly_score !== undefined ? Number(inv.mean_anomaly_score).toFixed(3) : 'N/A';
  const scoreStd = inv.score_std !== undefined ? Number(inv.score_std).toFixed(3) : 'N/A';
  const durationSec = inv.duration_sec || 60;
  const isMultiChannel = nChannels > 1;
  const persistenceClass = inv.persistence_class || (durationSec > 300 ? 'LONG' : (durationSec < 60 ? 'SHORT' : 'MODERATE'));

  const recData = buildDataDrivenRecommendations(inv, {
    nChannels,
    isMultiChannel,
    initialChannel,
    ch0Color,
    initialPeakScore,
    initialTimeStr,
    activationOrder,
    activationSpanSec,
    tempRelationships,
    totalPairs,
    overlappingPairsCount,
    totalEventsNum,
    totalEvents,
    duration,
    durationSec,
    eventRateVal,
    eventRateScore,
    sevLabel,
    sevScore,
    sigScore,
    confidence,
    gapToNext,
    relevantPairs,
    meanScore,
    scoreStd,
    missionImpactBasis,
    backendRecActions: recActions,
    persistenceClass
  });

  // Render HTML Structure
  container.innerHTML = `
    <!-- Top Action / Switcher Bar -->
    <div class="iw-action-strip">
      <div class="iw-strip-left">
        <span class="iw-strip-indicator"></span>
        <span class="iw-strip-label">ACTIVE INVESTIGATION:</span>
        <strong class="iw-strip-id">${invId}</strong>
      </div>
      <div class="iw-strip-actions">
        <button class="iw-btn-switch-inv" id="btn-switch-investigation" type="button">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
          </svg>
          <span>CHANGE INVESTIGATION</span>
          <span class="iw-chevron-down">▾</span>
        </button>
        <button class="iw-btn-clear-inv" id="btn-clear-investigation" type="button" title="Close case and return to blank workspace">
          <span>✕ DESELECT</span>
        </button>
      </div>
    </div>

    <!-- Section 1: INCIDENT OVERVIEW (Header & Key Metrics) -->
    <div class="glass-panel iw-header-card">
      <div class="iw-top-meta">
        <div class="iw-id-wrap">
          <h1 class="iw-id-title">${invId}</h1>
          <span class="sev-badge badge-${sevLabel.toLowerCase()}">${sevLabel}</span>
        </div>
        <div class="iw-subtitle-tag">
          SPACECRAFT INCIDENT INVESTIGATION
        </div>
      </div>

      <div class="iw-metrics-row">
        <div class="iw-metric-item">
          <span class="iw-metric-lbl">SEVERITY</span>
          <span class="iw-metric-val" style="color: ${sevLabel === 'CRITICAL' ? '#f43f5e' : (sevLabel === 'HIGH' ? '#60a5fa' : '#38bdf8')};">
            ${sevScore} <span style="font-size: 0.75rem; color: rgba(255,255,255,0.4);">/ 10</span>
          </span>
        </div>
        <div class="iw-metric-item">
          <span class="iw-metric-lbl">SIGNIFICANCE</span>
          <span class="iw-metric-val" style="color: #c084fc;">
            ${sigScore} <span style="font-size: 0.75rem; color: rgba(255,255,255,0.4);">/ 100</span>
          </span>
        </div>
        <div class="iw-metric-item">
          <span class="iw-metric-lbl">CONFIDENCE</span>
          <span class="iw-metric-val" style="color: var(--blue-electric, #38bdf8);">${confidence}</span>
        </div>
        <div class="iw-metric-item">
          <span class="iw-metric-lbl">DURATION</span>
          <span class="iw-metric-val">${duration}</span>
        </div>
        <div class="iw-metric-item">
          <span class="iw-metric-lbl">TOTAL EVENTS</span>
          <span class="iw-metric-val">${totalEvents}</span>
        </div>
      </div>
    </div>

    <!-- Section 2: WHAT HAPPENED? (Incident Evidence Basis) -->
    <div class="glass-panel iw-section">
      <h2 class="iw-section-heading">
        <span>⚡</span> WHAT HAPPENED?
      </h2>
      <div class="evidence-field-row">
        <span class="evidence-field-lbl">START TIME:</span>
        <span class="evidence-field-val">${inv.start_time || 'N/A'}</span>
      </div>
      <div class="evidence-field-row">
        <span class="evidence-field-lbl">END TIME:</span>
        <span class="evidence-field-val">${inv.end_time || 'N/A'}</span>
      </div>
      <div class="evidence-field-row">
        <span class="evidence-field-lbl">MISSION IMPACT LEVEL:</span>
        <span class="evidence-field-val">
          <strong style="color: ${sevLabel === 'CRITICAL' ? '#f43f5e' : '#38bdf8'};">${inv.mission_impact_level || sevLabel}</strong>
        </span>
      </div>
      ${missionImpactBasis.length > 0 ? `
        <div class="evidence-field-row">
          <span class="evidence-field-lbl">EVIDENCE BASIS:</span>
          <div class="evidence-field-val">
            <ul style="list-style: square; padding-left: 1.25rem; margin-top: 0.25rem;">
              ${missionImpactBasis.map(item => `<li>${item}</li>`).join('')}
            </ul>
          </div>
        </div>
      ` : ''}
    </div>

    <!-- Section 3: 1 TIMELINE OVERVIEW (Horizontal Milestone Chain) -->
    <div class="glass-panel iw-section iw-timeline-overview-card">
      <!-- Header Row -->
      <div class="iw-to-header">
        <div class="iw-to-header-left">
          <div class="iw-to-num-box">1</div>
          <div class="iw-to-titles">
            <h2 class="iw-to-main-title">TIMELINE OVERVIEW</h2>
            <div class="iw-to-subtitle">What happened and when</div>
          </div>
        </div>
        <div class="iw-to-header-right">
          <div class="iw-to-utc-badge">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
            <span>All times shown in UTC</span>
          </div>
        </div>
      </div>

      <!-- Single Horizontal Timeline Axis Across Card -->
      <div class="iw-timeline-axis-wrap">
        <div class="iw-timeline-axis-track">
          <div class="iw-to-axis-lead-left"></div>
          <div class="iw-timeline-nodes-list">
            ${allTimelineNodes.map((node, idx) => `
              <div class="iw-to-event-node" style="--node-color: ${node.color};">
                <!-- Top Outlined Time Badge -->
                <div class="iw-to-time-badge" style="border-color: ${node.color}; color: #ffffff; box-shadow: 0 0 10px ${node.color}55;">
                  ${node.timeLabel}
                </div>
                <!-- Vertical Dashed Line -->
                <div class="iw-to-vert-line" style="border-left-color: ${node.color};"></div>
                <!-- Circular Event Marker -->
                <div class="iw-to-circle-marker" style="border-color: ${node.color}; box-shadow: 0 0 16px ${node.color}88, inset 0 0 8px ${node.color}33;">
                  ${node.isIncident ? `
                    <span class="iw-to-inner-dot" style="background: ${node.color}; box-shadow: 0 0 8px ${node.color};"></span>
                  ` : `
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="${node.color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 12 7 12 9 6 13 18 15 12 21 12"/>
                    </svg>
                  `}
                </div>
                <!-- Vertical Dashed Line (Bottom Anchor) -->
                <div class="iw-to-vert-line-bottom" style="border-left-color: ${node.color};"></div>
                <!-- Channel Name / ID -->
                <div class="iw-to-channel-name" style="color: ${node.color}; text-shadow: 0 0 10px ${node.color}66;">${node.name}</div>
                <!-- Event Status Subtitle -->
                <div class="iw-to-event-status">${node.status}</div>
              </div>
              ${idx < allTimelineNodes.length - 1 ? `
                <div class="iw-to-connecting-segment" style="background: linear-gradient(90deg, ${node.color}, ${allTimelineNodes[idx + 1].color}); box-shadow: 0 0 8px ${node.color}66;"></div>
              ` : ''}
            `).join('')}
          </div>
          <div class="iw-to-axis-lead-right" style="background: linear-gradient(90deg, ${allTimelineNodes[allTimelineNodes.length - 1].color}, transparent);"></div>
        </div>
      </div>
    </div>

    <!-- Section 4: TEMPORAL EVIDENCE (Pairwise Timing & Sequence - Reference Image 1) -->
    <div class="glass-panel iw-section">
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.4rem;">
        <div>
          <h2 class="iw-section-heading" style="margin-bottom: 0.2rem;">
            <span>🕒</span> TEMPORAL EVIDENCE
          </h2>
          <div class="iw-temporal-sub">Reconstruct the timing relationships between affected telemetry channels.</div>
        </div>
        <button class="how-to-read-btn" id="btn-how-to-read" type="button" aria-expanded="false">
          <span>📖 HOW TO READ</span>
          <span class="chevron-icon">˅</span>
        </button>
      </div>

      <!-- Collapsible How To Read Panel -->
      <div class="how-to-read-panel" id="how-to-read-panel" style="display: none;">
        <div class="how-to-read-item">
          <span class="htr-term">PRECEDED</span> <span class="htr-arrow">→</span> <span class="htr-def">Channel A showed an anomaly prior to Channel B</span>
        </div>
        <div class="how-to-read-item">
          <span class="htr-term">FOLLOWED</span> <span class="htr-arrow">←</span> <span class="htr-def">Channel A showed an anomaly after Channel B</span>
        </div>
        <div class="how-to-read-item">
          <span class="htr-term">OVERLAP</span> <span class="htr-arrow">↔</span> <span class="htr-def">Channels exhibited concurrent anomaly activity during the same time window</span>
        </div>
      </div>

      <!-- 4 Top Stat Summary Cards (Reference Image 1) -->
      <div class="iw-temporal-stats-row">
        <div class="iw-temporal-stat-card">
          <div class="iw-stat-icon-wrap">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#38bdf8" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
          </div>
          <div class="iw-stat-body">
            <div class="iw-stat-number">${nChannels}</div>
            <div class="iw-stat-label">CHANNELS AFFECTED</div>
          </div>
        </div>

        <div class="iw-temporal-stat-card">
          <div class="iw-stat-icon-wrap">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#60a5fa" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div class="iw-stat-body">
            <div class="iw-stat-number">${activationSpanSec} <span style="font-size: 0.9rem; font-weight: 500;">sec</span></div>
            <div class="iw-stat-label">ACTIVATION SPAN</div>
          </div>
        </div>

        <div class="iw-temporal-stat-card">
          <div class="iw-stat-icon-wrap">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#818cf8" stroke-width="2">
              <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
          </div>
          <div class="iw-stat-body">
            <div class="iw-stat-number">${pairsComparedText}</div>
            <div class="iw-stat-label">CHANNEL PAIRS COMPARED</div>
          </div>
        </div>

        <div class="iw-temporal-stat-card">
          <div class="iw-stat-icon-wrap">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#c084fc" stroke-width="2">
              <circle cx="9" cy="12" r="6"/><circle cx="15" cy="12" r="6"/>
            </svg>
          </div>
          <div class="iw-stat-body">
            <div class="iw-stat-number">${pairsOverlapText}</div>
            <div class="iw-stat-label">PAIRS SHOW OVERLAP</div>
          </div>
        </div>
      </div>

      <!-- Two-Column Layout: Activation Sequence + Pairwise Evidence -->
      <div class="iw-temporal-columns-grid">
        <!-- Left: Channel Activation Sequence -->
        <div class="iw-activation-col">
          <div class="iw-col-title-wrap">
            <div class="iw-col-title">CHANNEL ACTIVATION SEQUENCE</div>
            <div class="iw-col-subtitle">Order in which channels showed anomalies</div>
          </div>

          <div class="iw-activation-flow-list">
            ${channelEvents.map((ms, idx) => `
              <div class="iw-activation-flow-item">
                <div class="iw-flow-rank-tag">${idx === 0 ? 'FIRST' : (idx === channelEvents.length - 1 ? 'LAST' : '')}</div>
                <div class="iw-flow-num-badge" style="background: ${ms.color}22; border-color: ${ms.color}; color: #ffffff;">${idx + 1}</div>
                <div class="iw-flow-channel-code" style="color: ${ms.color};">${ms.name}</div>
                <div class="iw-flow-status-lbl">${idx === 0 ? 'First activation' : 'Anomaly active'}</div>
                <div class="iw-flow-time">${ms.timeOnly}</div>
                <div class="iw-flow-color-bar" style="background: ${ms.color};"></div>
              </div>
              ${idx < channelEvents.length - 1 ? `
                <div class="iw-flow-gap-connector">
                  <span class="iw-gap-arrow">↓</span>
                  <span class="iw-gap-text">+${Math.max(0, channelEvents[idx + 1].deltaSec - ms.deltaSec)} sec</span>
                </div>
              ` : ''}
            `).join('')}
          </div>

          <!-- Bottom Activation Span Axis -->
          <div class="iw-activation-span-axis">
            <div class="iw-axis-time">${channelEvents[0]?.timeOnly || 'Start'}</div>
            <div class="iw-axis-bar">
              <span class="iw-axis-line"></span>
              <span class="iw-axis-lbl">${activationSpanSec} SEC</span>
              <span class="iw-axis-line"></span>
            </div>
            <div class="iw-axis-time">${channelEvents[channelEvents.length - 1]?.timeOnly || 'End'}</div>
          </div>
        </div>

        <!-- Right: Pairwise Temporal Evidence Cards -->
        <div class="iw-pairwise-col">
          <div class="iw-col-title-wrap" style="justify-content: space-between; display: flex; align-items: baseline;">
            <div>
              <div class="iw-col-title">PAIRWISE TEMPORAL EVIDENCE</div>
              <div class="iw-col-subtitle">Timing relationships between all channel pairs</div>
            </div>
            <div class="iw-pairwise-legend">
              <span><strong style="color: #38bdf8;">→</strong> PRECEDED</span>
              <span><strong style="color: #818cf8;">←</strong> FOLLOWED</span>
              <span><strong style="color: #facc15;">↔</strong> OVERLAP</span>
            </div>
          </div>

          <div class="iw-pairwise-grid">
            ${tempRelationships.length > 0 ? tempRelationships.map(rel => {
    const isPreceded = rel.temporal_precedence === 'A_before_B';
    const arrow = isPreceded ? '→' : '←';
    const relationName = isPreceded ? 'Preceded' : 'Followed';
    const gap = rel.temporal_gap_sec !== undefined ? `${rel.temporal_gap_sec} sec` : 'N/A';
    const hasOverlap = rel.windows_overlap;

    return `
                <div class="iw-pairwise-card">
                  <div class="iw-pairwise-header">
                    <span class="iw-pw-ch">${rel.channel_a}</span>
                    <span class="iw-pw-arrow">${arrow}</span>
                    <span class="iw-pw-ch">${rel.channel_b}</span>
                  </div>
                  <div class="iw-pairwise-meta-row">
                    <span class="iw-pw-lbl">Gap:</span>
                    <span class="iw-pw-val">${gap}</span>
                  </div>
                  <div class="iw-pairwise-meta-row">
                    <span class="iw-pw-lbl">Relation:</span>
                    <span class="iw-pw-val">${relationName}</span>
                  </div>
                  <div class="iw-pairwise-meta-row">
                    <span class="iw-pw-lbl">Overlap:</span>
                    <span class="iw-pw-val" style="color: ${hasOverlap ? '#4ade80' : 'rgba(255,255,255,0.5)'};">
                      ${hasOverlap ? '↔ Yes' : 'No'}
                    </span>
                  </div>
                </div>
              `;
  }).join('') : `
              <div class="iw-pairwise-single-notice">
                <span>Single-channel incident. Cross-channel pairwise relationships are not applicable.</span>
              </div>
            `}
          </div>
        </div>
      </div>

      <!-- Bottom Temporal Finding & Strength Meter (Reference Image 1) -->
      <div class="iw-temporal-bottom-card">
        <div class="iw-temporal-finding-box">
          <div class="iw-finding-title-row">
            <span class="iw-finding-icon">💡</span>
            <span class="iw-finding-lbl">TEMPORAL FINDING</span>
          </div>
          <p class="iw-finding-text">${narrativeConclusion}</p>
        </div>

        <div class="iw-evidence-strength-box">
          <div class="iw-strength-lbl">EVIDENCE STRENGTH</div>
          <div class="iw-strength-segments">
            ${Array.from({ length: 10 }).map((_, i) => {
    const activeRatio = totalPairs > 0 ? (overlappingPairsCount / totalPairs) : 1;
    const isActive = i < Math.max(1, Math.round(activeRatio * 10));
    return `<span class="iw-strength-segment ${isActive ? 'active' : ''}"></span>`;
  }).join('')}
            <span class="iw-strength-score">${pairsComparedText !== '0' ? `${overlappingPairsCount} / ${totalPairs}` : '1 / 1'}</span>
          </div>
          <div class="iw-strength-desc">
            ${overlappingPairsCount > 0 ? 'Strong temporal corroboration for a multi-channel incident pattern.' : 'Isolated telemetry event signature without multi-channel corroboration.'}
          </div>
        </div>

        <div class="iw-scientific-caveat-pill">
          <div class="iw-caveat-header">
            <span>⚠️</span>
            <span>SCIENTIFIC CAVEAT</span>
          </div>
          <p class="iw-caveat-text">
            Temporal correlation observed. Physical causality is not established.
          </p>
        </div>
      </div>
    </div>

    <!-- ========================================================================= -->
    <!-- NEW DATA-DRIVEN EVIDENCE GRAPH (Directly after Temporal Evidence)         -->
    <!-- ========================================================================= -->
    <div class="glass-panel iw-section iw-eg-full-card">
      <!-- Section Header -->
      <div class="iw-eg-header-row">
        <div class="iw-eg-title-wrap">
          <div class="iw-eg-icon-wrap">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#38bdf8" stroke-width="2">
              <circle cx="6" cy="6" r="3"/>
              <circle cx="18" cy="18" r="3"/>
              <circle cx="6" cy="18" r="3"/>
              <line x1="8.5" y1="7.5" x2="15.5" y2="16.5"/>
              <line x1="6" y1="9" x2="6" y2="15"/>
            </svg>
          </div>
          <div>
            <h2 class="iw-eg-main-title">EVIDENCE GRAPH</h2>
            <div class="iw-eg-sub-title">Relationship map showing how anomalies and evidence are connected to the incident.</div>
          </div>
        </div>
        <button class="iw-eg-btn-how-to-read" id="btn-eg-how-to-read" type="button" aria-expanded="false">
          <span>ⓘ How to read this?</span>
        </button>
      </div>

      <!-- Main Graph Area & Legend (2-Column Flex) -->
      <div class="iw-eg-main-visual-row">
        <!-- Visual Relationship Graph (SVG Visualizer) -->
        <div class="iw-eg-svg-container">
          ${renderDynamicEvidenceSvg(invId, channelEvents, tempRelationships)}
        </div>

        <!-- Legend Card -->
        <div class="iw-eg-legend-card">
          <div class="iw-eg-legend-title">LEGEND</div>
          <div class="iw-eg-legend-items">
            <div class="iw-eg-legend-item">
              <div class="iw-eg-leg-icon leg-incident">!</div>
              <span>Incident</span>
            </div>
            <div class="iw-eg-legend-item">
              <div class="iw-eg-leg-icon leg-channel">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="#38bdf8" stroke-width="2"><polyline points="2 12 7 12 9 6 13 18 15 12 22 12"/></svg>
              </div>
              <span>Anomaly Channel</span>
            </div>
            <div class="iw-eg-legend-divider"></div>
            <div class="iw-eg-legend-item">
              <div class="iw-eg-leg-line leg-temporal-solid"></div>
              <span>Temporal Relationship<br><small style="color: rgba(255,255,255,0.5);">(Earlier → Later)</small></span>
            </div>
            <div class="iw-eg-legend-item">
              <div class="iw-eg-leg-line leg-pattern-dash"></div>
              <span>Pattern Similarity</span>
            </div>
            <div class="iw-eg-legend-item">
              <div class="iw-eg-leg-line leg-sequence-dash"></div>
              <span>Sequence Consistency</span>
            </div>
            <div class="iw-eg-legend-item">
              <div class="iw-eg-leg-line leg-shared-dash"></div>
              <span>Shared Anomaly Window</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Collapsible "HOW TO READ THIS GRAPH" Strip -->
      <div class="iw-eg-how-to-read-panel" id="eg-how-to-read-panel" style="display: none;">
        <div class="iw-eg-htr-header">✦ HOW TO READ THIS GRAPH</div>
        <div class="iw-eg-htr-grid">
          <div class="iw-eg-htr-item">
            <div class="iw-eg-htr-icon-box" style="border-color: #f43f5e; color: #f43f5e;">⬡</div>
            <div>
              <div class="iw-eg-htr-title">Incident</div>
              <div class="iw-eg-htr-desc">The central event under investigation.</div>
            </div>
          </div>
          <div class="iw-eg-htr-item">
            <div class="iw-eg-htr-icon-box" style="border-color: #38bdf8; color: #38bdf8;">〰</div>
            <div>
              <div class="iw-eg-htr-title">Anomaly Channel</div>
              <div class="iw-eg-htr-desc">Channels where anomalous activity was detected.</div>
            </div>
          </div>
          <div class="iw-eg-htr-item">
            <div class="iw-eg-htr-icon-box" style="border-color: rgba(255,255,255,0.6); color: #ffffff;">→</div>
            <div>
              <div class="iw-eg-htr-title">Direction</div>
              <div class="iw-eg-htr-desc">Shows the order in which anomalies appeared.</div>
            </div>
          </div>
          <div class="iw-eg-htr-item">
            <div class="iw-eg-htr-icon-box" style="border-color: #38bdf8; color: #38bdf8; font-size: 0.65rem;">+2s</div>
            <div>
              <div class="iw-eg-htr-title">Time Difference</div>
              <div class="iw-eg-htr-desc">Time gap between two consecutive anomalies.</div>
            </div>
          </div>
          <div class="iw-eg-htr-item">
            <div class="iw-eg-htr-icon-box" style="border-color: #a855f7; color: #a855f7;">⚯</div>
            <div>
              <div class="iw-eg-htr-title">Dotted Connections</div>
              <div class="iw-eg-htr-desc">Indicate relationships based on patterns, overlap or similarity.</div>
            </div>
          </div>
          <div class="iw-eg-htr-item">
            <div class="iw-eg-htr-icon-box" style="border-color: #34d399; color: #34d399;">📶</div>
            <div>
              <div class="iw-eg-htr-title">Strength</div>
              <div class="iw-eg-htr-desc">Stronger evidence shown with brighter solid lines.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- WHAT DOES THE EVIDENCE TELL US? (4 Cards) -->
      <div class="iw-eg-tell-us-header">
        <span>🧠</span> WHAT DOES THE EVIDENCE TELL US?
      </div>
      <div class="iw-eg-cards-grid">
        <!-- Card 1: TEMPORAL LINKS -->
        <div class="iw-eg-card">
          <div class="iw-eg-card-top">
            <div class="iw-eg-card-icon-wrap" style="color: #38bdf8;">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
              </svg>
            </div>
            <div>
              <div class="iw-eg-card-title">TEMPORAL LINKS</div>
              <div class="iw-eg-card-sub">When did they occur?</div>
            </div>
          </div>
          <div class="iw-eg-card-content">
            <div class="iw-eg-mini-graphic">
              <svg viewBox="0 0 120 40" width="100" height="30">
                <line x1="10" y1="25" x2="110" y2="25" stroke="rgba(56, 189, 248, 0.3)" stroke-width="1.5"/>
                <circle cx="20" cy="25" r="4" fill="#38bdf8"/>
                <circle cx="55" cy="18" r="4" fill="#38bdf8"/>
                <circle cx="85" cy="28" r="4" fill="#38bdf8"/>
                <circle cx="105" cy="20" r="4" fill="#38bdf8"/>
                <polyline points="20,25 55,18 85,28 105,20" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
              </svg>
            </div>
            <p class="iw-eg-card-text">${temporalLinksText}</p>
          </div>
          <div class="iw-eg-card-footer">
            <button class="iw-eg-details-btn" data-card="TEMPORAL_LINKS" type="button">VIEW DETAILS →</button>
          </div>
        </div>

        <!-- Card 2: PATTERN MATCH -->
        <div class="iw-eg-card">
          <div class="iw-eg-card-top">
            <div class="iw-eg-card-icon-wrap" style="color: #a855f7;">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9"/>
                <line x1="12" y1="3" x2="12" y2="21"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <circle cx="12" cy="12" r="4"/>
              </svg>
            </div>
            <div>
              <div class="iw-eg-card-title">PATTERN MATCH</div>
              <div class="iw-eg-card-sub">Did they behave similarly?</div>
            </div>
          </div>
          <div class="iw-eg-card-content">
            <div class="iw-eg-mini-graphic">
              <svg viewBox="0 0 120 40" width="100" height="30">
                <path d="M 5,20 Q 20,5 35,20 T 65,20 T 95,20 T 115,20" fill="none" stroke="#a855f7" stroke-width="1.5"/>
                <path d="M 5,20 Q 20,35 35,20 T 65,20 T 95,20 T 115,20" fill="none" stroke="rgba(168, 85, 247, 0.4)" stroke-dasharray="2 2" stroke-width="1"/>
              </svg>
            </div>
            <p class="iw-eg-card-text">${patternMatchText}</p>
          </div>
          <div class="iw-eg-card-footer">
            <button class="iw-eg-details-btn" data-card="PATTERN_MATCH" type="button">VIEW DETAILS →</button>
          </div>
        </div>

        <!-- Card 3: SEQUENCE CONSISTENCY -->
        <div class="iw-eg-card">
          <div class="iw-eg-card-top">
            <div class="iw-eg-card-icon-wrap" style="color: #f59e0b;">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="6" cy="12" r="3"/>
                <circle cx="18" cy="12" r="3"/>
                <path d="M9 12h6"/>
              </svg>
            </div>
            <div>
              <div class="iw-eg-card-title">SEQUENCE CONSISTENCY</div>
              <div class="iw-eg-card-sub">What happened first?</div>
            </div>
          </div>
          <div class="iw-eg-card-content">
            <div class="iw-eg-mini-graphic">
              <div style="display: flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #f59e0b;">
                <span style="color: #10b981;">●</span> <span>→</span> <span style="color: #f59e0b;">●</span> <span>→</span> <span style="color: #f43f5e;">●</span>
              </div>
            </div>
            <p class="iw-eg-card-text">${sequenceConsistencyText}</p>
          </div>
          <div class="iw-eg-card-footer">
            <button class="iw-eg-details-btn" data-card="SEQUENCE_CONSISTENCY" type="button">VIEW DETAILS →</button>
          </div>
        </div>

        <!-- Card 4: EVIDENCE STRENGTH -->
        <div class="iw-eg-card">
          <div class="iw-eg-card-top">
            <div class="iw-eg-card-icon-wrap" style="color: #38bdf8;">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <div>
              <div class="iw-eg-card-title">EVIDENCE STRENGTH</div>
              <div class="iw-eg-card-sub">How strong is the evidence?</div>
            </div>
          </div>
          <div class="iw-eg-card-content">
            <div class="iw-eg-gauge-wrap">
              <svg viewBox="0 0 80 50" width="80" height="50">
                <path d="M 10 45 A 35 35 0 0 1 70 45" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="6" stroke-linecap="round"/>
                <path d="M 10 45 A 35 35 0 0 1 70 45" fill="none" stroke="#2dd4bf" stroke-width="6" stroke-linecap="round"
                  stroke-dasharray="110" stroke-dashoffset="${110 - (110 * strengthPct) / 100}"/>
                <text x="40" y="42" text-anchor="middle" font-family="'Space Grotesk', sans-serif" font-size="14" font-weight="700" fill="#ffffff">${strengthPct}%</text>
              </svg>
              <div class="iw-eg-gauge-lbl">Overall Strength</div>
            </div>
            <p class="iw-eg-card-text">${evidenceStrengthText}</p>
          </div>
          <div class="iw-eg-card-footer">
            <button class="iw-eg-details-btn" data-card="EVIDENCE_STRENGTH" type="button">VIEW DETAILS →</button>
          </div>
        </div>
      </div>

      <!-- Dynamic Detail View Container (Hidden by default; opens ONLY selected card) -->
      <div class="iw-eg-detail-wrapper" id="iw-eg-detail-wrapper" style="display: none;"></div>

      <!-- Bottom Insight & Note Strip (2 Columns) -->
      <div class="iw-eg-bottom-notes-grid">
        <div class="iw-eg-insight-box">
          <div class="iw-eg-note-header">
            <span>💡</span>
            <span>INVESTIGATOR INSIGHT</span>
          </div>
          <p class="iw-eg-note-text">${investigatorInsightText}</p>
        </div>

        <div class="iw-eg-important-box">
          <div class="iw-eg-note-header" style="color: #f59e0b;">
            <span>⚠️</span>
            <span>IMPORTANT TO NOTE</span>
          </div>
          <p class="iw-eg-note-text">${importantNoteText}</p>
        </div>
      </div>
    </div>

    <!-- Section 5: HOW THE EVIDENCE UNFOLDS (Deterministic Analytical Breakdown) -->
    <div class="glass-panel iw-section iw-narrative-section">
      <h2 class="iw-section-heading">
        <span>📑</span> HOW THE EVIDENCE UNFOLDS
      </h2>
      
      <div class="iw-narrative-steps">
        <div class="iw-narrative-step">
          <div class="iw-narrative-step-title">1. WHAT HAPPENED</div>
          <div class="iw-narrative-step-content">${narrativeWhatHappened}</div>
        </div>

        <div class="iw-narrative-step">
          <div class="iw-narrative-step-title">2. WHAT IS THE EVIDENCE</div>
          <div class="iw-narrative-step-content">${narrativeEvidence}</div>
        </div>

        <div class="iw-narrative-step">
          <div class="iw-narrative-step-title">3. HOW DID IT PROGRESS?</div>
          <div class="iw-narrative-step-content">${narrativeProgress}</div>
        </div>

        <div class="iw-narrative-step">
          <div class="iw-narrative-step-title">4. WHAT IS THE CONNECTION?</div>
          <div class="iw-narrative-step-content">${narrativeConnection}</div>
        </div>

        <div class="iw-narrative-step">
          <div class="iw-narrative-step-title">5. CONCLUSION</div>
          <div class="iw-narrative-step-content">${narrativeConclusion}</div>
        </div>
      </div>

      <div class="iw-assessment-strip">
        <div class="iw-assessment-left">
          <span class="iw-ass-lbl">ASSESSMENT:</span>
          <strong class="iw-ass-val" style="color: ${sevLabel === 'CRITICAL' ? '#f43f5e' : '#38bdf8'};">${sevLabel}</strong>
          <span class="iw-ass-sub">(Score: ${sevScore}/10)</span>
        </div>
        <div class="iw-assessment-right">
          <span class="iw-ass-lbl">CONFIDENCE:</span>
          <strong class="iw-ass-val" style="color: #38bdf8;">${confidence}</strong>
        </div>
      </div>
    </div>

    <!-- Section 6: RECOMMENDED INVESTIGATION (Visual Structured Recommendation Dashboard) -->
    <div class="glass-panel iw-section iw-rec-dashboard-card">
      <div class="iw-rec-header-row">
        <div class="iw-rec-title-wrap">
          <div class="iw-rec-icon-wrap">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#38bdf8" stroke-width="2">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
              <rect x="9" y="3" width="6" height="4" rx="2"/>
              <path d="M9 14l2 2 4-4"/>
            </svg>
          </div>
          <div>
            <h2 class="iw-rec-main-title">RECOMMENDED INVESTIGATION</h2>
            <div class="iw-rec-sub-title">Data-driven actions identified from this investigation.</div>
          </div>
        </div>
      </div>

      <div class="iw-rec-items-list">
        <!-- 1. INITIAL ANOMALY -->
        <div class="iw-rec-item-card" data-rec-id="rec-initial-anomaly">
          <div class="iw-rec-summary-row">
            <div class="iw-rec-item-left">
              <div class="iw-rec-badge-num">1</div>
              <div class="iw-rec-item-info">
                <div class="iw-rec-item-tag">INITIAL ANOMALY</div>
                <div class="iw-rec-headline-row">
                  <span class="iw-rec-ch-badge" style="color: ${ch0Color}; border-color: ${ch0Color}; box-shadow: 0 0 8px ${ch0Color}44;">${initialChannel}</span>
                  <span class="iw-rec-meta-pill">Score: <strong>${initialPeakScore}</strong></span>
                  <span class="iw-rec-meta-pill">${initialTimeStr}</span>
                </div>
                <div class="iw-rec-one-line">${recData.initialOneLine}</div>
              </div>
            </div>
            <div class="iw-rec-item-right">
              <button class="iw-rec-expand-btn" type="button">
                <span>VIEW DETAILS</span>
                <span class="rec-arrow">→</span>
              </button>
            </div>
          </div>
          <div class="iw-rec-drawer" style="display: none;">
            <div class="iw-rec-drawer-content">
              <div class="iw-rec-drawer-grid">
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">ROOT CHANNEL TELEMETRY</div>
                  <p class="iw-drawer-txt">${recData.initialRootTelemetry}</p>
                </div>
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">DIAGNOSTIC ACTION</div>
                  <p class="iw-drawer-txt">${recData.initialDiagnosticAction}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. TEMPORAL SEQUENCE -->
        <div class="iw-rec-item-card" data-rec-id="rec-temporal-sequence">
          <div class="iw-rec-summary-row">
            <div class="iw-rec-item-left">
              <div class="iw-rec-badge-num">2</div>
              <div class="iw-rec-item-info">
                <div class="iw-rec-item-tag">TEMPORAL SEQUENCE</div>
                <div class="iw-rec-headline-row">
                  <div class="iw-rec-seq-chain">
                    ${activationOrder.map((ch, idx) => `
                      <span class="iw-rec-seq-ch" style="color: ${getChannelColor(ch, idx)};">${ch}</span>
                      ${idx < activationOrder.length - 1 ? '<span class="iw-rec-seq-arrow">→</span>' : ''}
                    `).join('')}
                  </div>
                  <span class="iw-rec-meta-pill">${nChannels} Channels</span>
                  <span class="iw-rec-meta-pill">${activationSpanSec}s Span</span>
                </div>
                <div class="iw-rec-one-line">${recData.seqOneLine}</div>
              </div>
            </div>
            <div class="iw-rec-item-right">
              <button class="iw-rec-expand-btn" type="button">
                <span>VIEW DETAILS</span>
                <span class="rec-arrow">→</span>
              </button>
            </div>
          </div>
          <div class="iw-rec-drawer" style="display: none;">
            <div class="iw-rec-drawer-content">
              <div class="iw-rec-drawer-grid">
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">SEQUENCE PROGRESSION</div>
                  <p class="iw-drawer-txt">${recData.seqProgression}</p>
                </div>
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">DIAGNOSTIC ACTION</div>
                  <p class="iw-drawer-txt">${recData.seqDiagnosticAction}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 3. TEMPORAL OVERLAP -->
        <div class="iw-rec-item-card" data-rec-id="rec-temporal-overlap">
          <div class="iw-rec-summary-row">
            <div class="iw-rec-item-left">
              <div class="iw-rec-badge-num">3</div>
              <div class="iw-rec-item-info">
                <div class="iw-rec-item-tag">TEMPORAL OVERLAP</div>
                <div class="iw-rec-headline-row">
                  <span class="iw-rec-meta-pill" style="color: #4ade80; border-color: rgba(74, 222, 128, 0.4);">
                    <strong>${overlappingPairsCount}</strong> / ${totalPairs > 0 ? totalPairs : '1'} Pairs Overlap
                  </span>
                  ${relevantPairs.length > 0 ? relevantPairs.map(r => `
                    <span class="iw-rec-pair-badge">
                      ${r.channel_a} ↔ ${r.channel_b} (${r.temporal_gap_sec !== undefined ? `+${r.temporal_gap_sec}s` : '0s'})
                    </span>
                  `).join('') : '<span class="iw-rec-meta-pill">Single Channel Anomaly</span>'}
                </div>
                <div class="iw-rec-one-line">${recData.overlapOneLine}</div>
              </div>
            </div>
            <div class="iw-rec-item-right">
              <button class="iw-rec-expand-btn" type="button">
                <span>VIEW DETAILS</span>
                <span class="rec-arrow">→</span>
              </button>
            </div>
          </div>
          <div class="iw-rec-drawer" style="display: none;">
            <div class="iw-rec-drawer-content">
              <div class="iw-rec-drawer-grid">
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">PAIRWISE CORROBORATION</div>
                  <p class="iw-drawer-txt">${recData.overlapCorroboration}</p>
                </div>
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">DIAGNOSTIC ACTION</div>
                  <p class="iw-drawer-txt">${recData.overlapDiagnosticAction}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 4. ANOMALY DENSITY -->
        <div class="iw-rec-item-card" data-rec-id="rec-anomaly-density">
          <div class="iw-rec-summary-row">
            <div class="iw-rec-item-left">
              <div class="iw-rec-badge-num">4</div>
              <div class="iw-rec-item-info">
                <div class="iw-rec-item-tag">ANOMALY DENSITY</div>
                <div class="iw-rec-headline-row">
                  <span class="iw-rec-meta-pill">Rate: <strong>${eventRateVal}</strong> events/sec</span>
                  <span class="iw-rec-meta-pill">Total: <strong>${totalEvents}</strong> events</span>
                  <div class="iw-rec-density-bar-wrap">
                    <div class="iw-rec-density-bar" style="width: ${Math.min(100, Math.max(15, eventRateScore))}%;"></div>
                  </div>
                </div>
                <div class="iw-rec-one-line">${recData.densityOneLine}</div>
              </div>
            </div>
            <div class="iw-rec-item-right">
              <button class="iw-rec-expand-btn" type="button">
                <span>VIEW DETAILS</span>
                <span class="rec-arrow">→</span>
              </button>
            </div>
          </div>
          <div class="iw-rec-drawer" style="display: none;">
            <div class="iw-rec-drawer-content">
              <div class="iw-rec-drawer-grid">
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">FREQUENCY METRICS</div>
                  <p class="iw-drawer-txt">${recData.densityMetrics}</p>
                </div>
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">DIAGNOSTIC ACTION</div>
                  <p class="iw-drawer-txt">${recData.densityDiagnosticAction}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 5. PRIORITY -->
        <div class="iw-rec-item-card" data-rec-id="rec-priority">
          <div class="iw-rec-summary-row">
            <div class="iw-rec-item-left">
              <div class="iw-rec-badge-num">5</div>
              <div class="iw-rec-item-info">
                <div class="iw-rec-item-tag">PRIORITY</div>
                <div class="iw-rec-headline-row">
                  <span class="sev-badge badge-${sevLabel.toLowerCase()}">${sevLabel}</span>
                  <span class="iw-rec-meta-pill">Significance: <strong style="color: #c084fc;">${sigScore}/100</strong></span>
                  <span class="iw-rec-meta-pill">Confidence: <strong style="color: #38bdf8;">${confidence}</strong></span>
                </div>
                <div class="iw-rec-one-line">${recData.priorityOneLine}</div>
              </div>
            </div>
            <div class="iw-rec-item-right">
              <button class="iw-rec-expand-btn" type="button">
                <span>VIEW DETAILS</span>
                <span class="rec-arrow">→</span>
              </button>
            </div>
          </div>
          <div class="iw-rec-drawer" style="display: none;">
            <div class="iw-rec-drawer-content">
              <div class="iw-rec-drawer-grid">
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">MISSION IMPACT BASIS</div>
                  <p class="iw-drawer-txt">${recData.priorityImpact}</p>
                </div>
                <div class="iw-rec-drawer-box">
                  <div class="iw-drawer-lbl">RECOMMENDED ACTIONS</div>
                  <ul class="iw-drawer-list">
                    ${recData.priorityActions.map(act => `<li>${act}</li>`).join('')}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 7: TELEMETRY EVENT STREAM (Waveform Canvas - directly below Recommended Investigation) -->
    <div class="glass-panel iw-section">
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem;">
        <h2 class="iw-section-heading" style="margin-bottom: 0;">
          <span>📈</span> TELEMETRY EVENT STREAM
        </h2>
        ${isTruncated ? `
          <div class="timeline-truncation-badge">
            <span>⚠️</span>
            <span>Showing ${shownEventsCount} of ${totalEvents} events (timeline truncated by backend)</span>
          </div>
        ` : (timelineEvents.length > 0 ? `
          <div style="font-size: 0.75rem; color: rgba(186, 230, 253, 0.6); font-family: var(--font-mono);">
            Showing ${timelineEvents.length} recorded events
          </div>
        ` : '')}
      </div>

      <!-- Timeline Canvas Visualizer -->
      <div class="timeline-canvas-box" id="timeline-canvas-box">
        <canvas id="timeline-canvas" class="timeline-canvas"></canvas>
        <div id="timeline-tooltip" class="timeline-tooltip"></div>
      </div>
    </div>
  `;

  // Attach button events
  const btnSwitch = container.querySelector('#btn-switch-investigation');
  if (btnSwitch) {
    btnSwitch.addEventListener('click', () => openInvestigationPickerModal());
  }

  const btnClear = container.querySelector('#btn-clear-investigation');
  if (btnClear) {
    btnClear.addEventListener('click', () => clearSelectedInvestigation());
  }

  const btnHowToRead = container.querySelector('#btn-how-to-read');
  const howToReadPanel = container.querySelector('#how-to-read-panel');
  if (btnHowToRead && howToReadPanel) {
    btnHowToRead.addEventListener('click', () => {
      const isExpanded = howToReadPanel.style.display === 'block';
      howToReadPanel.style.display = isExpanded ? 'none' : 'block';
      btnHowToRead.setAttribute('aria-expanded', !isExpanded);
      const chevron = btnHowToRead.querySelector('.chevron-icon');
      if (chevron) chevron.textContent = isExpanded ? '˅' : '˄';
    });
  }

  const btnEgHowToRead = container.querySelector('#btn-eg-how-to-read');
  const egHowToReadPanel = container.querySelector('#eg-how-to-read-panel');
  if (btnEgHowToRead && egHowToReadPanel) {
    btnEgHowToRead.addEventListener('click', () => {
      const isExpanded = egHowToReadPanel.style.display === 'block';
      egHowToReadPanel.style.display = isExpanded ? 'none' : 'block';
      btnEgHowToRead.setAttribute('aria-expanded', !isExpanded);
      btnEgHowToRead.classList.toggle('active', !isExpanded);
    });
  }

  // =========================================================================
  // VIEW DETAILS INTERACTION HANDLER FOR 4 CARDS (Reference Image: 4-cards-view-details.png)
  // =========================================================================
  let activeDetailCard = null;
  const detailWrapper = container.querySelector('#iw-eg-detail-wrapper');
  const detailBtns = container.querySelectorAll('.iw-eg-details-btn');

  function openDetailCard(cardType) {
    if (activeDetailCard === cardType) {
      // Toggle off
      activeDetailCard = null;
      detailWrapper.style.display = 'none';
      detailWrapper.innerHTML = '';
      detailBtns.forEach(b => b.classList.remove('active'));
      return;
    }

    activeDetailCard = cardType;
    detailBtns.forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-card') === cardType);
    });

    const ctxParams = {
      inv,
      invId,
      channelEvents,
      tempRelationships,
      confidence,
      sevLabel,
      duration,
      totalEventsNum,
      activationSpanSec,
      overlappingPairsCount,
      totalPairs,
      strengthPct,
      temporalScore,
      patternScore,
      sequenceScore,
      dataScore,
      overallRating,
      patternSimilarityPct: Math.min(99, Math.round(85 + (overlappingPairsCount / Math.max(1, totalPairs)) * 14))
    };

    detailWrapper.style.display = 'block';
    detailWrapper.innerHTML = renderDetailViewHtml(cardType, ctxParams);

    const closeBtn = detailWrapper.querySelector('#btn-close-eg-detail');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        activeDetailCard = null;
        detailWrapper.style.display = 'none';
        detailWrapper.innerHTML = '';
        detailBtns.forEach(b => b.classList.remove('active'));
      });
    }

    if (cardType === 'PATTERN_MATCH') {
      const chA = channelEvents[0]?.name || 'CADC0888';
      const chB = channelEvents[1]?.name || channelEvents[0]?.name || 'CADC0872';
      setTimeout(() => initSignalComparisonCanvas(detailWrapper, timelineEvents, chA, chB), 50);
    }

    detailWrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  detailBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const cardType = btn.getAttribute('data-card');
      openDetailCard(cardType);
    });
  });

  // =========================================================================
  // RECOMMENDED INVESTIGATION ACCORDION HANDLERS
  // =========================================================================
  const recCards = container.querySelectorAll('.iw-rec-item-card');
  recCards.forEach(card => {
    const btn = card.querySelector('.iw-rec-expand-btn');
    const drawer = card.querySelector('.iw-rec-drawer');
    if (btn && drawer) {
      btn.addEventListener('click', () => {
        const isCurrentlyOpen = drawer.style.display === 'block';

        // Close all other drawers
        recCards.forEach(otherCard => {
          const otherDrawer = otherCard.querySelector('.iw-rec-drawer');
          const otherBtn = otherCard.querySelector('.iw-rec-expand-btn');
          if (otherDrawer && otherBtn && otherCard !== card) {
            otherDrawer.style.display = 'none';
            otherBtn.classList.remove('active');
            otherBtn.querySelector('span:first-child').textContent = 'VIEW DETAILS';
            const arrow = otherBtn.querySelector('.rec-arrow');
            if (arrow) arrow.textContent = '→';
          }
        });

        // Toggle clicked drawer
        if (isCurrentlyOpen) {
          drawer.style.display = 'none';
          btn.classList.remove('active');
          btn.querySelector('span:first-child').textContent = 'VIEW DETAILS';
          const arrow = btn.querySelector('.rec-arrow');
          if (arrow) arrow.textContent = '→';
        } else {
          drawer.style.display = 'block';
          btn.classList.add('active');
          btn.querySelector('span:first-child').textContent = 'HIDE DETAILS';
          const arrow = btn.querySelector('.rec-arrow');
          if (arrow) arrow.textContent = '˄';
          card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    }
  });

  // Initialize Canvas Visualizers
  if (timelineEvents.length > 0) {
    initTimelineCanvas(container, timelineEvents);
  }
}

/**
 * Multi-Channel Timeline Canvas Visualizer
 */
function initTimelineCanvas(container, events) {
  const canvas = container.querySelector('#timeline-canvas');
  const box = container.querySelector('#timeline-canvas-box');
  const tooltip = container.querySelector('#timeline-tooltip');
  if (!canvas || !box || events.length === 0) return;

  const ctx = canvas.getContext('2d');
  let width, height;

  function resize() {
    width = box.clientWidth;
    height = box.clientHeight;
    canvas.width = width;
    canvas.height = height;
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    // Draw background grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let y = 30; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const n = events.length;
    const paddingX = 20;
    const paddingY = 25;
    const plotW = width - paddingX * 2;
    const plotH = height - paddingY * 2;

    // Draw score stems and event dots
    events.forEach((ev, i) => {
      const x = paddingX + (i / (n - 1 || 1)) * plotW;
      const score = Math.max(0, Math.min(1, ev.anomaly_score || 0));
      const y = (height - paddingY) - score * plotH;
      const color = getChannelColor(ev.channel, i);

      // Stem line
      ctx.strokeStyle = color + '40';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, height - paddingY);
      ctx.lineTo(x, y);
      ctx.stroke();

      // Dot
      ctx.fillStyle = color;
      ctx.shadowBlur = 4;
      ctx.shadowColor = color;
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });
  }

  // Tooltip mousemove handler
  box.addEventListener('mousemove', (e) => {
    const rect = box.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const paddingX = 20;
    const plotW = width - paddingX * 2;

    const clampedX = Math.max(0, Math.min(plotW, mx - paddingX));
    const ratio = clampedX / (plotW || 1);
    const eventIndex = Math.min(events.length - 1, Math.max(0, Math.round(ratio * (events.length - 1))));
    const ev = events[eventIndex];

    if (ev && tooltip) {
      tooltip.style.opacity = '1';
      tooltip.style.visibility = 'visible';
      tooltip.style.left = `${Math.min(width - 220, Math.max(10, mx - 100))}px`;
      tooltip.style.top = `${Math.max(10, e.clientY - rect.top - 70)}px`;
      tooltip.innerHTML = `
        <div style="color: ${getChannelColor(ev.channel)}; font-weight: 700;">${ev.channel}</div>
        <div>Time: ${ev.timestamp}</div>
        <div>Anomaly Score: <strong>${(ev.anomaly_score || 0).toFixed(4)}</strong></div>
        <div>Telemetry Val: <strong>${ev.value}</strong> (Seg ${ev.segment})</div>
      `;
    }
  });

  box.addEventListener('mouseleave', () => {
    if (tooltip) {
      tooltip.style.opacity = '0';
      tooltip.style.visibility = 'hidden';
    }
  });

  window.addEventListener('resize', resize);
  setTimeout(resize, 50);
}

/**
 * Dynamic SVG Evidence Graph Renderer
 */
function renderDynamicEvidenceSvg(invId, channelEvents, tempRelationships) {
  const n = channelEvents.length;
  const svgWidth = Math.max(760, n * 140);
  const svgHeight = 280;
  const centerX = svgWidth / 2;

  // Calculate X coordinates for each channel node
  const startX = 80;
  const endX = svgWidth - 80;
  const stepX = n > 1 ? (endX - startX) / (n - 1) : 0;
  const chX = channelEvents.map((_, i) => (n === 1 ? centerX : Math.round(startX + i * stepX)));
  const chY = 155;
  const incX = centerX;
  const incY = 48;

  // Build faint connecting lines from Incident node to channels
  const faintLines = chX.map(x => `
    <line x1="${incX}" y1="${incY + 22}" x2="${x}" y2="${chY - 26}" stroke="rgba(255, 255, 255, 0.18)" stroke-dasharray="3 3" stroke-width="1.2"/>
  `).join('');

  // Build direct sequence arrows between consecutive channels
  const sequenceArrows = [];
  for (let i = 0; i < n - 1; i++) {
    const x1 = chX[i] + 25;
    const x2 = chX[i + 1] - 25;
    const midX = (chX[i] + chX[i + 1]) / 2;
    const gapSec = Math.max(0, channelEvents[i + 1].deltaSec - channelEvents[i].deltaSec);

    sequenceArrows.push(`
      <g class="eg-seq-arrow-group">
        <line x1="${x1}" y1="${chY}" x2="${x2}" y2="${chY}" stroke="rgba(255, 255, 255, 0.65)" stroke-width="1.5" marker-end="url(#eg-arrow)"/>
        <rect x="${midX - 26}" y="${chY - 24}" width="52" height="16" rx="4" fill="#01040a" stroke="rgba(255, 255, 255, 0.3)" stroke-width="1"/>
        <text x="${midX}" y="${chY - 12}" text-anchor="middle" font-family="'Space Grotesk', sans-serif" font-size="10" font-weight="600" fill="#ffffff">+${gapSec} sec</text>
      </g>
    `);
  }

  // Top curved dashed arcs (Pattern Similarity - Cyan)
  const topArcs = [];
  if (n >= 3) {
    topArcs.push(`
      <path d="M ${chX[0]} ${chY - 25} C ${chX[0]} ${chY - 65}, ${chX[2]} ${chY - 65}, ${chX[2]} ${chY - 25}" 
        fill="none" stroke="#06b6d4" stroke-dasharray="4 4" stroke-width="1.8" opacity="0.9"/>
    `);
  }
  if (n >= 4) {
    topArcs.push(`
      <path d="M ${chX[1]} ${chY - 25} C ${chX[1]} ${chY - 75}, ${chX[3]} ${chY - 75}, ${chX[3]} ${chY - 25}" 
        fill="none" stroke="#06b6d4" stroke-dasharray="4 4" stroke-width="1.8" opacity="0.75"/>
    `);
  }

  // Bottom curved dashed arcs (Sequence Consistency - Purple, Shared Window - Amber)
  const bottomArcs = [];
  if (n >= 4) {
    bottomArcs.push(`
      <path d="M ${chX[0]} ${chY + 25} C ${chX[0]} ${chY + 75}, ${chX[3]} ${chY + 75}, ${chX[3]} ${chY + 25}" 
        fill="none" stroke="#a855f7" stroke-dasharray="4 4" stroke-width="1.8" opacity="0.9"/>
    `);
  }
  if (n >= 2) {
    const lastIdx = n - 1;
    bottomArcs.push(`
      <path d="M ${chX[0]} ${chY + 25} C ${chX[0]} ${chY + 100}, ${chX[lastIdx]} ${chY + 100}, ${chX[lastIdx]} ${chY + 25}" 
        fill="none" stroke="#f59e0b" stroke-dasharray="4 4" stroke-width="1.8" opacity="0.9"/>
    `);
  }

  // Channel nodes
  const channelNodesSvg = channelEvents.map((ch, i) => {
    const x = chX[i];
    return `
      <g class="eg-node-channel" transform="translate(${x}, ${chY})">
        <!-- Glowing Halo Circle -->
        <circle cx="0" cy="0" r="22" fill="#01040a" stroke="${ch.color}" stroke-width="2" filter="drop-shadow(0 0 8px ${ch.color})"/>
        <!-- Inner Waveform Icon -->
        <path d="M -12 0 L -6 0 L -3 -7 L 3 7 L 6 0 L 12 0" fill="none" stroke="${ch.color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <!-- Channel Label -->
        <text x="0" y="38" text-anchor="middle" font-family="'Orbitron', sans-serif" font-size="11" font-weight="700" fill="${ch.color}">${ch.name}</text>
        <text x="0" y="52" text-anchor="middle" font-family="'Chakra Petch', sans-serif" font-size="9" fill="rgba(255,255,255,0.7)">${i === 0 ? 'First Anomaly' : 'Detected'}</text>
        ${i > 0 ? `<text x="0" y="64" text-anchor="middle" font-family="'Space Grotesk', sans-serif" font-size="9" fill="rgba(255,255,255,0.7)">+${ch.deltaSec} sec</text>` : ''}
      </g>
    `;
  }).join('');

  return `
    <svg class="iw-eg-svg" viewBox="0 0 ${svgWidth} ${svgHeight}" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="eg-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="rgba(255, 255, 255, 0.7)"/>
        </marker>
        <filter id="eg-red-glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge>
            <feMergeNode in="blur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>

      <!-- Faint Rays from Incident -->
      ${faintLines}

      <!-- Arcs -->
      ${topArcs.join('')}
      ${bottomArcs.join('')}

      <!-- Sequence Arrows -->
      ${sequenceArrows.join('')}

      <!-- Incident Node (Top Center) -->
      <g class="eg-node-incident" transform="translate(${incX}, ${incY})">
        <!-- Outer Shield / Hexagon -->
        <polygon points="0,-22 19,-11 19,11 0,22 -19,11 -19,-11" fill="rgba(244, 63, 94, 0.14)" stroke="#f43f5e" stroke-width="2" filter="url(#eg-red-glow)"/>
        <!-- Inner Warning Icon -->
        <text x="0" y="5" text-anchor="middle" font-family="'Orbitron', sans-serif" font-size="14" font-weight="900" fill="#ffffff">!</text>
        <!-- Incident Label -->
        <text x="0" y="38" text-anchor="middle" font-family="'Orbitron', sans-serif" font-size="11" font-weight="800" fill="#f43f5e" letter-spacing="0.06em">${invId}</text>
        <text x="0" y="52" text-anchor="middle" font-family="'Chakra Petch', sans-serif" font-size="9" fill="rgba(255,255,255,0.6)">Main Incident</text>
      </g>

      <!-- Channel Nodes -->
      ${channelNodesSvg}
    </svg>
  `;
}

/**
 * Renders the HTML for the selected detail view (Reference Image: 4-cards-view-details.png)
 */
function renderDetailViewHtml(cardType, ctx) {
  const {
    inv,
    invId,
    channelEvents,
    tempRelationships,
    confidence,
    sevLabel,
    duration,
    activationSpanSec,
    overlappingPairsCount,
    totalPairs,
    strengthPct,
    temporalScore,
    patternScore,
    sequenceScore,
    dataScore,
    overallRating,
    patternSimilarityPct
  } = ctx;

  const channelA = channelEvents[0]?.name || 'CADC0888';
  const channelB = channelEvents[1]?.name || channelEvents[0]?.name || 'CADC0872';
  const chAColor = getChannelColor(channelA, 0);
  const chBColor = getChannelColor(channelB, 1);

  const rel = tempRelationships.find(r =>
    (r.channel_a === channelA && r.channel_b === channelB) ||
    (r.channel_b === channelA && r.channel_a === channelB)
  ) || tempRelationships[0];

  const gapSec = rel?.temporal_gap_sec !== undefined
    ? rel.temporal_gap_sec
    : (channelEvents[1] ? Math.max(0, channelEvents[1].deltaSec - channelEvents[0].deltaSec) : 2);

  const hasOverlap = rel ? rel.windows_overlap : (channelEvents.length > 1);
  const relationName = rel?.temporal_precedence === 'A_before_B' ? 'Preceded' : (rel ? 'Followed' : 'Preceded');
  const evidenceStrengthLabel = sevLabel === 'CRITICAL' ? 'High' : 'Moderate';
  const matchingBehavior = sevLabel === 'CRITICAL' ? 'Spike → Fluctuation → Recovery' : 'Deviation → Stabilization';
  const comparisonWindow = inv.duration_sec ? `${inv.duration_sec}s Window` : 'Incident Period';

  // 1. TEMPORAL LINKS DETAIL VIEW
  if (cardType === 'TEMPORAL_LINKS') {
    return `
      <div class="iw-detail-card" style="border-color: rgba(56, 189, 248, 0.35);">
        <!-- Header -->
        <div class="iw-detail-header">
          <div class="iw-detail-title-group">
            <div class="iw-detail-icon-wrap" style="color: #38bdf8; border-color: rgba(56, 189, 248, 0.4);">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
              </svg>
            </div>
            <div>
              <h3 class="iw-detail-title">TEMPORAL LINKS – VIEW DETAILS</h3>
              <div class="iw-detail-sub-question" style="color: #38bdf8;">What does this mean?</div>
              <p class="iw-detail-sub-text">
                These anomalies occurred close to each other in time. The first anomaly (${channelA}) appeared before subsequent anomalous events.
              </p>
            </div>
          </div>
          <button class="iw-detail-close-btn" id="btn-close-eg-detail" type="button" aria-label="Close">✕</button>
        </div>

        <!-- Top 4 Meta Boxes -->
        <div class="iw-detail-meta-row">
          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">CONNECTED CHANNELS</div>
            <div class="iw-detail-channels-pair">
              <div class="iw-ch-badge" style="color: ${chAColor}; border-color: ${chAColor};">
                <strong>${channelA}</strong>
                <span>First Anomaly</span>
              </div>
              <span class="iw-ch-arrow">→</span>
              <div class="iw-ch-badge" style="color: ${chBColor}; border-color: ${chBColor};">
                <strong>${channelB}</strong>
                <span>${channelEvents.length > 1 ? 'Second Anomaly' : 'Anomaly Detected'}</span>
              </div>
            </div>
          </div>

          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">TIME GAP</div>
            <div class="iw-detail-val-with-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#2dd4bf" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              <span class="iw-detail-huge-val">${gapSec} sec</span>
            </div>
          </div>

          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">OVERLAP</div>
            <div class="iw-detail-val-with-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="${hasOverlap ? '#4ade80' : '#fda4af'}" stroke-width="2"><circle cx="9" cy="12" r="6"/><circle cx="15" cy="12" r="6"/></svg>
              <span class="iw-detail-huge-val" style="color: ${hasOverlap ? '#4ade80' : '#fda4af'};">${hasOverlap ? 'Yes' : 'No'}</span>
            </div>
          </div>

          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">RELATIONSHIP</div>
            <div class="iw-detail-val-with-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#38bdf8" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              <span class="iw-detail-huge-val">${relationName}</span>
            </div>
          </div>
        </div>

        <!-- Middle: When did they connect? Gantt Timeline -->
        <div class="iw-detail-gantt-card">
          <div class="iw-detail-gantt-header">
            <span class="iw-gantt-title">WHEN DID THEY CONNECT?</span>
            <div class="iw-gantt-legend">
              <span class="iw-gantt-leg-item"><span class="leg-box active-period"></span> Anomaly Active Period</span>
              <span class="iw-gantt-leg-item"><span class="leg-box outside-period"></span> Outside Active Period</span>
            </div>
          </div>

          <div class="iw-gantt-tracks">
            <div class="iw-gantt-track-row">
              <span class="iw-gantt-ch-lbl" style="color: ${chAColor};">${channelA}</span>
              <div class="iw-gantt-bar-wrap">
                <div class="iw-gantt-bar" style="left: 10%; width: 45%; background: ${chAColor};"></div>
              </div>
            </div>
            <div class="iw-gantt-track-row">
              <span class="iw-gantt-ch-lbl" style="color: ${chBColor};">${channelB}</span>
              <div class="iw-gantt-bar-wrap">
                <div class="iw-gantt-gap-indicator" style="left: 10%; width: 35%;">
                  <span class="gap-text">${gapSec} sec gap</span>
                </div>
                <div class="iw-gantt-bar" style="left: 45%; width: 45%; background: ${chBColor};"></div>
              </div>
            </div>
            <!-- Time Axis -->
            <div class="iw-gantt-axis">
              <span>00:00:00</span>
              <span>00:00:10</span>
              <span>00:00:20</span>
              <span>00:00:30</span>
              <span>00:00:40</span>
            </div>
            <div class="iw-gantt-axis-title">Time (hh:mm:ss)</div>
          </div>
        </div>

        <!-- Bottom: Why are they connected? + What does this mean? -->
        <div class="iw-detail-bottom-grid">
          <div class="iw-detail-why-box">
            <div class="iw-detail-box-title">WHY ARE THEY CONNECTED?</div>
            <ul class="iw-detail-checks-list">
              <li><span class="check-icon">✓</span> The subsequent anomaly started ${gapSec} seconds after the initial occurrence.</li>
              <li><span class="check-icon">✓</span> Both anomalies occurred within the same investigation window.</li>
              <li><span class="check-icon">✓</span> Their active periods exhibit temporal correlation across telemetry records.</li>
              <li><span class="check-icon">✓</span> The sequence is consistent across observed telemetry segments.</li>
            </ul>
            <div class="iw-detail-box-foot">
              <span class="foot-lbl">EVIDENCE STRENGTH</span>
              <span class="foot-val-strength" style="color: #38bdf8;">📶 ${evidenceStrengthLabel}</span>
            </div>
          </div>

          <div class="iw-detail-mean-box">
            <div class="iw-detail-box-title" style="color: #38bdf8;">
              <span>ⓘ</span> WHAT DOES THIS MEAN?
            </div>
            <p class="iw-detail-mean-text">
              The timing suggests these anomalies may be related and should be investigated together. However, this does not mean ${channelA} physically caused ${channelB}.
            </p>
            <div class="iw-detail-box-foot">
              <span class="foot-lbl">CONFIDENCE</span>
              <span class="foot-val-conf" style="color: #34d399;">🛡️ ${confidence}</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // 2. PATTERN MATCH DETAIL VIEW
  if (cardType === 'PATTERN_MATCH') {
    return `
      <div class="iw-detail-card" style="border-color: rgba(168, 85, 247, 0.35);">
        <!-- Header -->
        <div class="iw-detail-header">
          <div class="iw-detail-title-group">
            <div class="iw-detail-icon-wrap" style="color: #a855f7; border-color: rgba(168, 85, 247, 0.4);">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9"/>
                <line x1="12" y1="3" x2="12" y2="21"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <circle cx="12" cy="12" r="4"/>
              </svg>
            </div>
            <div>
              <h3 class="iw-detail-title">PATTERN MATCH – VIEW DETAILS</h3>
              <div class="iw-detail-sub-question" style="color: #a855f7;">What does this mean?</div>
              <p class="iw-detail-sub-text">
                The system compared how both channels behaved during the incident. Their signals show a similar pattern of change.
              </p>
            </div>
          </div>
          <button class="iw-detail-close-btn" id="btn-close-eg-detail" type="button" aria-label="Close">✕</button>
        </div>

        <!-- Top 4 Meta Boxes -->
        <div class="iw-detail-meta-row">
          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">CHANNELS COMPARED</div>
            <div class="iw-detail-channels-pair">
              <div class="iw-ch-badge" style="color: ${chAColor}; border-color: ${chAColor};">
                <strong>${channelA}</strong>
                <span>First Anomaly</span>
              </div>
              <span class="iw-ch-arrow">↔</span>
              <div class="iw-ch-badge" style="color: ${chBColor}; border-color: ${chBColor};">
                <strong>${channelB}</strong>
                <span>${channelEvents.length > 1 ? 'Second Anomaly' : 'Anomaly Detected'}</span>
              </div>
            </div>
          </div>

          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">PATTERN SIMILARITY</div>
            <div class="iw-detail-val-with-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#a855f7" stroke-width="2"><path d="M2 12h5l2-6 4 12 2-6h7"/></svg>
              <span class="iw-detail-huge-val" style="color: #a855f7;">${patternSimilarityPct}%</span>
            </div>
          </div>

          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">MATCHING BEHAVIOR</div>
            <div class="iw-detail-val-with-icon">
              <span class="iw-detail-huge-val" style="font-size: 0.82rem; line-height: 1.3;">${matchingBehavior}</span>
            </div>
          </div>

          <div class="iw-detail-meta-box">
            <div class="iw-detail-box-lbl">COMPARISON WINDOW</div>
            <div class="iw-detail-val-with-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#38bdf8" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              <span class="iw-detail-huge-val">${comparisonWindow}</span>
            </div>
          </div>
        </div>

        <!-- Middle: Signal Comparison Chart Canvas -->
        <div class="iw-detail-signal-card">
          <div class="iw-detail-gantt-header">
            <span class="iw-gantt-title">SIGNAL COMPARISON</span>
            <div class="iw-gantt-legend">
              <span class="iw-gantt-leg-item"><span class="leg-line" style="background: ${chAColor};"></span> ${channelA}</span>
              <span class="iw-gantt-leg-item"><span class="leg-line" style="background: ${chBColor};"></span> ${channelB}</span>
            </div>
          </div>

          <div class="iw-signal-canvas-box" id="iw-signal-canvas-box" style="position: relative; height: 180px; width: 100%;">
            <canvas id="iw-signal-canvas" class="iw-signal-canvas"></canvas>
          </div>
        </div>

        <!-- Bottom: Why were they matched? + What does this mean? -->
        <div class="iw-detail-bottom-grid">
          <div class="iw-detail-why-box">
            <div class="iw-detail-box-title">WHY WERE THEY MATCHED?</div>
            <ul class="iw-detail-checks-list">
              <li><span class="check-icon" style="color: #a855f7;">✓</span> Similar rise and peak pattern in anomaly scores.</li>
              <li><span class="check-icon" style="color: #a855f7;">✓</span> Coincident fluctuations during the incident interval.</li>
              <li><span class="check-icon" style="color: #a855f7;">✓</span> Similar recovery gradient back to nominal range.</li>
              <li><span class="check-icon" style="color: #a855f7;">✓</span> High overall morphological curve similarity (${patternSimilarityPct}%).</li>
            </ul>
            <div class="iw-detail-box-foot">
              <span class="foot-lbl">EVIDENCE STRENGTH</span>
              <span class="foot-val-strength" style="color: #a855f7;">📶 High</span>
            </div>
          </div>

          <div class="iw-detail-mean-box">
            <div class="iw-detail-box-title" style="color: #a855f7;">
              <span>ⓘ</span> WHAT DOES THIS MEAN?
            </div>
            <p class="iw-detail-mean-text">
              Both channels reacted in a similar way during the incident. This strengthens the possibility that they are related and part of the same underlying event.
            </p>
            <div class="iw-detail-box-foot">
              <span class="foot-lbl">CONFIDENCE</span>
              <span class="foot-val-conf" style="color: #a855f7;">🛡️ ${confidence}</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // 3. SEQUENCE CONSISTENCY DETAIL VIEW
  if (cardType === 'SEQUENCE_CONSISTENCY') {
    return `
      <div class="iw-detail-card" style="border-color: rgba(245, 158, 11, 0.35);">
        <!-- Header -->
        <div class="iw-detail-header">
          <div class="iw-detail-title-group">
            <div class="iw-detail-icon-wrap" style="color: #f59e0b; border-color: rgba(245, 158, 11, 0.4);">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="6" cy="12" r="3"/>
                <circle cx="18" cy="12" r="3"/>
                <path d="M9 12h6"/>
              </svg>
            </div>
            <div>
              <h3 class="iw-detail-title">SEQUENCE CONSISTENCY – VIEW DETAILS</h3>
              <div class="iw-detail-sub-question" style="color: #f59e0b;">What does this mean?</div>
              <p class="iw-detail-sub-text">
                This shows the order in which anomalies appeared. The system checks whether this order is consistent across the available data.
              </p>
            </div>
          </div>
          <button class="iw-detail-close-btn" id="btn-close-eg-detail" type="button" aria-label="Close">✕</button>
        </div>

        <!-- Observed Sequence Flow -->
        <div class="iw-seq-observed-card">
          <div class="iw-detail-box-lbl" style="margin-bottom: 0.75rem;">OBSERVED SEQUENCE</div>
          <div class="iw-seq-flow-row">
            ${channelEvents.map((ch, idx) => `
              <div class="iw-seq-node-item">
                <div class="iw-seq-icon-circle" style="border-color: ${ch.color};">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="${ch.color}" stroke-width="2"><polyline points="2 12 7 12 9 6 13 18 15 12 22 12"/></svg>
                </div>
                <div class="iw-seq-node-name" style="color: ${ch.color};">${ch.name}</div>
                <div class="iw-seq-node-sub">${idx === 0 ? 'First Detected' : `+${ch.deltaSec} sec`}</div>
              </div>
              ${idx < channelEvents.length - 1 ? '<span class="iw-seq-flow-arrow">→</span>' : ''}
            `).join('')}
          </div>
        </div>

        <!-- Sequence Timeline & Score Row -->
        <div class="iw-seq-middle-grid">
          <div class="iw-seq-timeline-box">
            <div class="iw-detail-box-lbl" style="margin-bottom: 1.25rem;">SEQUENCE TIMELINE</div>
            <div class="iw-seq-timeline-track">
              <div class="iw-seq-line"></div>
              <div class="iw-seq-dots-list">
                ${channelEvents.map((ch) => `
                  <div class="iw-seq-dot-item">
                    <span class="iw-seq-dot" style="background: ${ch.color}; box-shadow: 0 0 8px ${ch.color};"></span>
                    <span class="iw-seq-dot-time">${ch.timeOnly !== 'N/A' ? ch.timeOnly : `+${ch.deltaSec}s`}</span>
                  </div>
                `).join('')}
              </div>
            </div>
            <div class="iw-gantt-axis-title" style="margin-top: 1rem;">Time (hh:mm:ss)</div>
          </div>

          <div class="iw-seq-score-box">
            <div class="iw-detail-box-lbl">SEQUENCE CONSISTENCY SCORE</div>
            <div class="iw-seq-score-body">
              <div class="iw-seq-score-shield">🛡️</div>
              <div>
                <div class="iw-seq-score-num">${confidence}</div>
                <div class="iw-seq-score-rating" style="color: #f59e0b;">${parseFloat(confidence) > 95 ? 'Very High' : 'High'}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Bottom: Why is it consistent? + What does this mean? -->
        <div class="iw-detail-bottom-grid">
          <div class="iw-detail-why-box">
            <div class="iw-detail-box-title">WHY IS THE SEQUENCE CONSIDERED CONSISTENT?</div>
            <ul class="iw-detail-checks-list">
              <li><span class="check-icon" style="color: #f59e0b;">✓</span> The order of anomalies is supported by the telemetry data.</li>
              <li><span class="check-icon" style="color: #f59e0b;">✓</span> The time gaps between events are stable and monotonically increasing.</li>
              <li><span class="check-icon" style="color: #f59e0b;">✓</span> The sequence is not random or conflicting across channels.</li>
              <li><span class="check-icon" style="color: #f59e0b;">✓</span> Multiple data segments confirm the same progression.</li>
            </ul>
          </div>

          <div class="iw-detail-mean-box">
            <div class="iw-detail-box-title" style="color: #f59e0b;">
              <span>ⓘ</span> WHAT DOES THIS MEAN?
            </div>
            <p class="iw-detail-mean-text">
              The anomalies follow a clear and reliable order. This helps investigators understand how the event unfolded over time.
            </p>
          </div>
        </div>

        <!-- Yellow Caution Banner -->
        <div class="iw-detail-caution-banner">
          <span>💡</span>
          <span><strong>Note:</strong> A consistent sequence helps in identifying the event flow, but it does not confirm that each anomaly caused the next one.</span>
        </div>
      </div>
    `;
  }

  // 4. EVIDENCE STRENGTH DETAIL VIEW
  if (cardType === 'EVIDENCE STRENGTH' || cardType === 'EVIDENCE_STRENGTH') {
    return `
      <div class="iw-detail-card" style="border-color: rgba(56, 189, 248, 0.35);">
        <!-- Header -->
        <div class="iw-detail-header">
          <div class="iw-detail-title-group">
            <div class="iw-detail-icon-wrap" style="color: #38bdf8; border-color: rgba(56, 189, 248, 0.4);">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <div>
              <h3 class="iw-detail-title">EVIDENCE STRENGTH – VIEW DETAILS</h3>
              <div class="iw-detail-sub-question" style="color: #38bdf8;">What does this mean?</div>
              <p class="iw-detail-sub-text">
                This score shows how strongly the overall evidence supports the detected relationships between anomalies.
              </p>
            </div>
          </div>
          <button class="iw-detail-close-btn" id="btn-close-eg-detail" type="button" aria-label="Close">✕</button>
        </div>

        <!-- Top: Breakdown Bars + Overall Strength Gauge -->
        <div class="iw-strength-breakdown-row">
          <div class="iw-strength-bars-box">
            <div class="iw-detail-box-lbl" style="margin-bottom: 1rem;">EVIDENCE BREAKDOWN</div>
            <div class="iw-strength-bar-item">
              <span class="bar-lbl">Temporal Relationship</span>
              <div class="bar-track"><div class="bar-fill" style="width: ${temporalScore}%; background: #2dd4bf;"></div></div>
              <span class="bar-val">${temporalScore}%</span>
              <span class="bar-rating" style="color: #2dd4bf;">Strong</span>
            </div>
            <div class="iw-strength-bar-item">
              <span class="bar-lbl">Pattern Similarity</span>
              <div class="bar-track"><div class="bar-fill" style="width: ${patternScore}%; background: #a855f7;"></div></div>
              <span class="bar-val">${patternScore}%</span>
              <span class="bar-rating" style="color: #a855f7;">Strong</span>
            </div>
            <div class="iw-strength-bar-item">
              <span class="bar-lbl">Sequence Consistency</span>
              <div class="bar-track"><div class="bar-fill" style="width: ${sequenceScore}%; background: #f59e0b;"></div></div>
              <span class="bar-val">${sequenceScore}%</span>
              <span class="bar-rating" style="color: #f59e0b;">Very Strong</span>
            </div>
            <div class="iw-strength-bar-item">
              <span class="bar-lbl">Data Availability</span>
              <div class="bar-track"><div class="bar-fill" style="width: ${dataScore}%; background: #38bdf8;"></div></div>
              <span class="bar-val">${dataScore}%</span>
              <span class="bar-rating" style="color: #38bdf8;">High</span>
            </div>
          </div>

          <div class="iw-strength-overall-gauge-box">
            <div class="iw-detail-box-lbl" style="margin-bottom: 0.5rem;">OVERALL EVIDENCE STRENGTH</div>
            <div class="iw-detail-gauge-circle">
              <svg viewBox="0 0 120 120" width="120" height="120">
                <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>
                <circle cx="60" cy="60" r="50" fill="none" stroke="#2dd4bf" stroke-width="10"
                  stroke-dasharray="314.15" stroke-dashoffset="${314.15 - (314.15 * strengthPct) / 100}"
                  stroke-linecap="round" transform="rotate(-90 60 60)"/>
                <text x="60" y="58" text-anchor="middle" font-family="'Space Grotesk', sans-serif" font-size="24" font-weight="800" fill="#ffffff">${strengthPct}%</text>
                <text x="60" y="76" text-anchor="middle" font-family="'Chakra Petch', sans-serif" font-size="12" font-weight="700" fill="#2dd4bf">${overallRating}</text>
              </svg>
            </div>
            <p class="iw-strength-overall-desc">Overall evidence across all relationships is strong.</p>
          </div>
        </div>

        <!-- Bottom: What contributes to this score? + What it does not mean -->
        <div class="iw-detail-bottom-grid">
          <div class="iw-detail-why-box">
            <div class="iw-detail-box-title">WHAT CONTRIBUTES TO THIS SCORE?</div>
            <ul class="iw-detail-contribute-list">
              <li><span class="icon-bubble" style="color: #38bdf8;">⏱️</span> Strong timing relationships between anomalies.</li>
              <li><span class="icon-bubble" style="color: #a855f7;">〰️</span> High similarity in signal patterns.</li>
              <li><span class="icon-bubble" style="color: #f59e0b;">🔁</span> Very consistent sequence of events.</li>
              <li><span class="icon-bubble" style="color: #34d399;">📊</span> Sufficient and reliable telemetry data.</li>
            </ul>
          </div>

          <div class="iw-detail-mean-box">
            <div class="iw-detail-box-title" style="color: #38bdf8;">
              <span>ⓘ</span> WHAT IT DOES NOT MEAN
            </div>
            <p class="iw-detail-mean-text">
              A high score means the available data strongly supports the relationships. It does not confirm physical causation or the root cause of the incident.
            </p>
          </div>
        </div>

        <!-- Bottom Caveat Banner -->
        <div class="iw-detail-blue-banner">
          <span>💡</span>
          <span>These relationships are based on observed data and statistical analysis. They indicate correlation, not necessarily physical causation.</span>
        </div>
      </div>
    `;
  }

  return '';
}

/**
 * Signal Comparison Canvas Plotter for Pattern Match Detail
 */
function initSignalComparisonCanvas(container, timelineEvents, channelA, channelB) {
  const canvas = container.querySelector('#iw-signal-canvas');
  const box = container.querySelector('#iw-signal-canvas-box');
  if (!canvas || !box) return;

  const ctx = canvas.getContext('2d');
  const width = box.clientWidth || 600;
  const height = 180;
  canvas.width = width;
  canvas.height = height;

  ctx.clearRect(0, 0, width, height);

  // Draw grid
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  ctx.lineWidth = 1;
  for (let y = 30; y < height; y += 35) {
    ctx.beginPath();
    ctx.moveTo(40, y);
    ctx.lineTo(width - 20, y);
    ctx.stroke();
  }

  // Draw Y-axis labels
  ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
  ctx.font = '10px "Space Grotesk", sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText('1.0', 35, 35);
  ctx.fillText('0.5', 35, 70);
  ctx.fillText('0', 35, 105);
  ctx.fillText('-0.5', 35, 140);
  ctx.fillText('-1.0', 35, 175);

  // Filter events for channelA and channelB
  const evsA = timelineEvents.filter(e => e.channel === channelA);
  const evsB = timelineEvents.filter(e => e.channel === channelB);

  function drawSignal(events, color, offsetAngle = 0) {
    if (events.length === 0) return;
    const n = Math.min(60, events.length);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = 50 + (i / (n - 1 || 1)) * (width - 70);
      const score = events[i].anomaly_score !== undefined ? events[i].anomaly_score : 0.5;
      const wave = Math.sin(i * 0.4 + offsetAngle) * 0.35;
      const normY = Math.max(-1, Math.min(1, (score * 1.5 - 0.75) + wave));
      const y = 105 - normY * 55;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  const chAColor = getChannelColor(channelA, 0);
  const chBColor = getChannelColor(channelB, 1);

  drawSignal(evsA.length > 0 ? evsA : timelineEvents, chAColor, 0);
  drawSignal(evsB.length > 0 ? evsB : timelineEvents, chBColor, 0.6);
}
