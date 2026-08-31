/**
 * ClueSpace Screen 2: INCIDENT EXPLORER
 * Source of truth: investigation_index.json
 * Strictly renders search by Incident ID, severity/channel filters, sorting,
 * and the incident table (ID, IMPACT, SEVERITY, CHANNELS, EVENTS) per Member 3.pdf.
 */

import { fetchInvestigationIndex } from './dataService.js';
import { navigateToInvestigationWorkspace } from './navigation.js';

let indexData = [];
let currentFilter = 'ALL';
let currentSort = 'severity'; // 'severity', 'significance', 'confidence'
let searchQuery = '';

export async function renderIncidentExplorer(container) {
  const data = await fetchInvestigationIndex();
  indexData = data.investigations || [];

  container.innerHTML = `
    <!-- Screen Header -->
    <div class="screen-header-block">
      <h1 class="screen-main-heading">INCIDENT EXPLORER</h1>
      <p class="screen-sub-prompt">Search, filter, and inspect spacecraft telemetry incidents</p>
    </div>

    <!-- Controls: Search, Filters, Sorting -->
    <div class="ie-controls-bar">
      
      <!-- Incident ID Search Only -->
      <div class="ie-search-box">
        <svg class="ie-search-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input 
          type="text" 
          id="ie-search-input" 
          class="ie-search-input" 
          placeholder="Search Incident ID (e.g. INV-988, 988)..." 
          value="${searchQuery}"
        />
      </div>

      <!-- Severity & Channel Filter Chips -->
      <div class="ie-filter-chips" id="ie-filter-chips">
        <button class="filter-chip ${currentFilter === 'ALL' ? 'active' : ''}" data-filter="ALL">ALL</button>
        <button class="filter-chip ${currentFilter === 'CRITICAL' ? 'active' : ''}" data-filter="CRITICAL">CRITICAL</button>
        <button class="filter-chip ${currentFilter === 'HIGH' ? 'active' : ''}" data-filter="HIGH">HIGH</button>
        <button class="filter-chip ${currentFilter === 'MODERATE' ? 'active' : ''}" data-filter="MODERATE">MODERATE</button>
        <button class="filter-chip ${currentFilter === 'LOW' ? 'active' : ''}" data-filter="LOW">LOW</button>
        <button class="filter-chip ${currentFilter === 'MULTI-CHANNEL' ? 'active' : ''}" data-filter="MULTI-CHANNEL">MULTI-CHANNEL</button>
        <button class="filter-chip ${currentFilter === 'SINGLE-CHANNEL' ? 'active' : ''}" data-filter="SINGLE-CHANNEL">SINGLE-CHANNEL</button>
      </div>

      <!-- Sorting strictly by: Severity, Significance, Confidence -->
      <div class="ie-sort-group">
        <span class="ie-sort-label">SORT BY:</span>
        <button class="sort-btn ${currentSort === 'severity' ? 'active' : ''}" data-sort="severity">SEVERITY</button>
        <button class="sort-btn ${currentSort === 'significance' ? 'active' : ''}" data-sort="significance">SIGNIFICANCE</button>
        <button class="sort-btn ${currentSort === 'confidence' ? 'active' : ''}" data-sort="confidence">CONFIDENCE</button>
      </div>

    </div>

    <!-- Transparent Glass Table Container per Member 3.pdf: ID, IMPACT, SEVERITY, CHANNELS, EVENTS -->
    <div class="glass-panel ie-glass-table-wrap">
      <div class="ie-table-container">
        <table class="ie-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>IMPACT</th>
              <th>SEVERITY</th>
              <th>CHANNELS</th>
              <th>EVENTS</th>
            </tr>
          </thead>
          <tbody id="ie-table-body">
            <!-- Rendered dynamically -->
          </tbody>
        </table>
      </div>
    </div>
  `;

  attachExplorerListeners(container);
  updateTableRows();
}

function attachExplorerListeners(container) {
  const searchInput = container.querySelector('#ie-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.trim().toUpperCase();
      updateTableRows();
    });
  }

  const filterChips = container.querySelectorAll('.filter-chip');
  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentFilter = chip.dataset.filter;
      updateTableRows();
    });
  });

  const sortBtns = container.querySelectorAll('.sort-btn');
  sortBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      sortBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentSort = btn.dataset.sort;
      updateTableRows();
    });
  });
}

function updateTableRows() {
  const tbody = document.getElementById('ie-table-body');
  if (!tbody) return;

  // 1. Filter
  let filtered = indexData.filter(item => {
    // Search by Incident ID
    if (searchQuery) {
      const matchId = (item.investigation_id || '').toUpperCase().includes(searchQuery) ||
                      String(item.spacecraft_incident_id || '').includes(searchQuery);
      if (!matchId) return false;
    }

    // Filter by Severity or Multi/Single Channel
    if (currentFilter === 'ALL') return true;
    if (currentFilter === 'CRITICAL') return item.severity_label === 'CRITICAL';
    if (currentFilter === 'HIGH') return item.severity_label === 'HIGH';
    if (currentFilter === 'MODERATE') return item.severity_label === 'MODERATE';
    if (currentFilter === 'LOW') return item.severity_label === 'LOW';
    if (currentFilter === 'MULTI-CHANNEL') return item.is_multi_channel === true;
    if (currentFilter === 'SINGLE-CHANNEL') return item.is_multi_channel === false;
    return true;
  });

  // 2. Sort strictly by Severity, Significance, or Confidence
  filtered.sort((a, b) => {
    if (currentSort === 'severity') {
      return (b.severity_score || 0) - (a.severity_score || 0);
    }
    if (currentSort === 'significance') {
      return (b.significance_score || 0) - (a.significance_score || 0);
    }
    if (currentSort === 'confidence') {
      return (b.investigation_confidence || 0) - (a.investigation_confidence || 0);
    }
    return 0;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 2.5rem; color: rgba(255,255,255,0.4);">
          No spacecraft incidents match query "${searchQuery}".
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    const sevClass = (item.severity_label || '').toLowerCase();
    const impactVal = typeof item.significance_score === 'number' ? item.significance_score.toFixed(2) : item.significance_score;
    const sevScore = typeof item.severity_score === 'number' ? item.severity_score.toFixed(2) : item.severity_score;

    return `
      <tr class="ie-row" data-id="${item.investigation_id}" title="Click to inspect ${item.investigation_id} in Investigation Workspace">
        <td><strong style="color: var(--blue-electric, #38bdf8);">${item.investigation_id}</strong></td>
        <td>${impactVal}</td>
        <td><span class="sev-badge badge-${sevClass}">${item.severity_label} (${sevScore})</span></td>
        <td>${item.n_channels_affected} channel${item.n_channels_affected > 1 ? 's' : ''}</td>
        <td>${(item.n_events_total || 0).toLocaleString()}</td>
      </tr>
    `;
  }).join('');

  // Row click opens the EXACT clicked investigation in the Investigation Workspace
  const rows = tbody.querySelectorAll('.ie-row');
  rows.forEach(row => {
    row.addEventListener('click', () => {
      const invId = row.dataset.id;
      if (invId) {
        navigateToInvestigationWorkspace(invId);
      }
    });
  });
}
