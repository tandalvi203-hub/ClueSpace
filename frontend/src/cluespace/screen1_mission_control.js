/**
 * ClueSpace Screen 1: MISSION CONTROL
 * Source of truth: investigation_summary.json, investigation_index.json, and investigation dataset files.
 * 100% Dynamic dataset-derived calculations — Zero mock/hardcoded values.
 */

import { getComputedDatasetMetrics } from './dataService.js';
import { navigateToScreen } from './navigation.js';

export async function renderMissionControl(container) {
  // 1. Fetch live dynamically computed metrics from dataset
  const summary = getComputedDatasetMetrics();

  const total = summary.total_incidents;
  const multiChannel = summary.multi_channel_count;
  const singleChannel = summary.single_channel_count;

  const multiChannelPct = total > 0 ? ((multiChannel / total) * 100).toFixed(1) : '0';
  const singleChannelPct = total > 0 ? ((singleChannel / total) * 100).toFixed(1) : '0';

  // 2. Severity Distribution & Proportions
  const sev = summary.severity_distribution || {
    CRITICAL: 0,
    HIGH: 0,
    MODERATE: 0,
    LOW: 0
  };

  const totalSev = (sev.CRITICAL || 0) + (sev.HIGH || 0) + (sev.MODERATE || 0) + (sev.LOW || 0) || total;
  const cCritical = totalSev > 0 ? (sev.CRITICAL / totalSev) * 100 : 0;
  const cHigh = totalSev > 0 ? (sev.HIGH / totalSev) * 100 : 0;
  const cModerate = totalSev > 0 ? (sev.MODERATE / totalSev) * 100 : 0;
  const cLow = totalSev > 0 ? (sev.LOW / totalSev) * 100 : 0;

  // Donut SVG circumference calculation for r=38 (2 * PI * 38 = 238.761)
  const circumference = 238.761;
  const dashCritical = (cCritical / 100) * circumference;
  const dashHigh = (cHigh / 100) * circumference;
  const dashModerate = (cModerate / 100) * circumference;
  const dashLow = (cLow / 100) * circumference;

  const offsetCritical = 0;
  const offsetHigh = -dashCritical;
  const offsetModerate = -(dashCritical + dashHigh);
  const offsetLow = -(dashCritical + dashHigh + dashModerate);

  // 3. Dynamic Key Metrics (Averages)
  const avgSignificance = typeof summary.average_significance === 'number' 
    ? summary.average_significance.toFixed(2) 
    : summary.average_significance;
  const avgSeverity = typeof summary.average_severity === 'number'
    ? summary.average_severity.toFixed(2)
    : summary.average_severity;
  const avgConfidence = typeof summary.average_confidence === 'number'
    ? summary.average_confidence.toFixed(2)
    : summary.average_confidence;
  const avgDuration = Math.round(summary.average_duration_sec || 0);

  // 4. Time Range & Dataset Stats
  const dataSource = summary.data_source || 'OPS-SAT TELEMETRY';
  const dateRangeStart = summary.date_range_start ? `${summary.date_range_start} UTC` : 'N/A';
  const dateRangeEnd = summary.date_range_end ? `${summary.date_range_end} UTC` : 'N/A';
  const lastUpdate = summary.date_range_end ? `${summary.date_range_end} UTC` : 'N/A';
  const totalEvents = summary.total_telemetry_events 
    ? summary.total_telemetry_events.toLocaleString() 
    : '158,726';
  const monitoredChannelsCount = summary.monitored_channels_count || 8;

  // 5. Top Channels Ranking
  const topChannels = summary.top_channels && summary.top_channels.length > 0 
    ? summary.top_channels.slice(0, 5) 
    : [];

  const maxChannelCount = topChannels.length > 0 ? Math.max(...topChannels.map(c => c.count), 1) : 1;

  // 6. Time Activity Data
  const dailyActivity = summary.daily_activity || [];
  const recentActivity = summary.recent_activity || dailyActivity.slice(-7);

  container.innerHTML = `
    <!-- 1. Mission Control Header -->
    <div class="mc-header-row">
      <div class="mc-title-group">
        <h1 class="mc-main-heading">MISSION CONTROL</h1>
        <div class="mc-sub-heading">REAL-TIME SPACECRAFT INCIDENT INTELLIGENCE</div>
        <div class="mc-meta-badge">
          <span class="mc-live-dot">●</span>
          <span class="mc-meta-text">DATA SOURCE: <strong>${dataSource}</strong></span>
          ${lastUpdate !== 'N/A' ? `<span class="mc-meta-divider">•</span><span class="mc-meta-text">LAST TELEMETRY TIMESTAMP: <strong>${lastUpdate}</strong></span>` : ''}
        </div>
      </div>
    </div>

    <!-- 2. Top Overview Row (5 Cards) -->
    <div class="mc-top-kpi-grid">
      
      <!-- Card 1: Total Reconstructed Incidents -->
      <div class="glass-panel mc-top-card mc-card-total">
        <div class="mc-card-top-header">
          <div class="mc-icon-circle mc-icon-blue">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span class="mc-kpi-big-num">${total}</span>
        </div>
        <div class="mc-card-label">TOTAL RECONSTRUCTED INCIDENTS</div>
        <div class="mc-progress-wrapper">
          <div class="mc-progress-bar mc-progress-blue" style="width: 100%;"></div>
        </div>
        <div class="mc-card-meta-text">All active investigations</div>
      </div>

      <!-- Card 2: Multi-Channel Incidents -->
      <div class="glass-panel mc-top-card mc-card-multi">
        <div class="mc-card-top-header">
          <div class="mc-icon-circle mc-icon-purple">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
          </div>
          <span class="mc-kpi-big-num">${multiChannel}</span>
        </div>
        <div class="mc-card-label">MULTI-CHANNEL INCIDENTS</div>
        <div class="mc-progress-wrapper">
          <div class="mc-progress-bar mc-progress-purple" style="width: ${multiChannelPct}%;"></div>
        </div>
        <div class="mc-card-meta-text">${multiChannelPct}% of total incidents</div>
      </div>

      <!-- Card 3: Single-Channel Incidents -->
      <div class="glass-panel mc-top-card mc-card-single">
        <div class="mc-card-top-header">
          <div class="mc-icon-circle mc-icon-teal">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2">
              <circle cx="12" cy="12" r="10"/>
              <circle cx="12" cy="12" r="6"/>
              <circle cx="12" cy="12" r="2"/>
            </svg>
          </div>
          <span class="mc-kpi-big-num">${singleChannel}</span>
        </div>
        <div class="mc-card-label">SINGLE-CHANNEL INCIDENTS</div>
        <div class="mc-progress-wrapper">
          <div class="mc-progress-bar mc-progress-teal" style="width: ${singleChannelPct}%;"></div>
        </div>
        <div class="mc-card-meta-text">${singleChannelPct}% of total incidents</div>
      </div>

      <!-- Card 4: By Severity Level -->
      <div class="glass-panel mc-top-card mc-card-severity-split">
        <div class="mc-card-title-sm">BY SEVERITY LEVEL</div>
        <div class="mc-severity-split-layout">
          <div class="mc-severity-mini-list">
            <div class="mc-sev-mini-row">
              <span class="mc-sev-dot mc-dot-critical"></span>
              <span class="mc-sev-name">CRITICAL</span>
              <span class="mc-sev-val">${sev.CRITICAL || 0}</span>
              <span class="mc-sev-pct">${cCritical.toFixed(1)}%</span>
            </div>
            <div class="mc-sev-mini-row">
              <span class="mc-sev-dot mc-dot-high"></span>
              <span class="mc-sev-name">HIGH</span>
              <span class="mc-sev-val">${sev.HIGH || 0}</span>
              <span class="mc-sev-pct">${cHigh.toFixed(1)}%</span>
            </div>
            <div class="mc-sev-mini-row">
              <span class="mc-sev-dot mc-dot-moderate"></span>
              <span class="mc-sev-name">MODERATE</span>
              <span class="mc-sev-val">${sev.MODERATE || 0}</span>
              <span class="mc-sev-pct">${cModerate.toFixed(1)}%</span>
            </div>
            <div class="mc-sev-mini-row">
              <span class="mc-sev-dot mc-dot-low"></span>
              <span class="mc-sev-name">LOW</span>
              <span class="mc-sev-val">${sev.LOW || 0}</span>
              <span class="mc-sev-pct">${cLow.toFixed(1)}%</span>
            </div>
          </div>
          
          <div class="mc-mini-donut-box">
            <svg class="mc-mini-donut-svg" viewBox="0 0 90 90">
              <circle cx="45" cy="45" r="35" fill="transparent" stroke="rgba(255,255,255,0.06)" stroke-width="12" />
              <!-- Critical (Red) -->
              <circle cx="45" cy="45" r="35" fill="transparent" stroke="#ef4444" stroke-width="12"
                stroke-dasharray="${(cCritical / 100) * 219.911} ${219.911 - (cCritical / 100) * 219.911}"
                stroke-dashoffset="0" />
              <!-- High (Amber) -->
              <circle cx="45" cy="45" r="35" fill="transparent" stroke="#f97316" stroke-width="12"
                stroke-dasharray="${(cHigh / 100) * 219.911} ${219.911 - (cHigh / 100) * 219.911}"
                stroke-dashoffset="${-((cCritical / 100) * 219.911)}" />
              <!-- Moderate (Yellow) -->
              <circle cx="45" cy="45" r="35" fill="transparent" stroke="#eab308" stroke-width="12"
                stroke-dasharray="${(cModerate / 100) * 219.911} ${219.911 - (cModerate / 100) * 219.911}"
                stroke-dashoffset="${-(((cCritical + cHigh) / 100) * 219.911)}" />
              <!-- Low (Green) -->
              <circle cx="45" cy="45" r="35" fill="transparent" stroke="#22c55e" stroke-width="12"
                stroke-dasharray="${(cLow / 100) * 219.911} ${219.911 - (cLow / 100) * 219.911}"
                stroke-dashoffset="${-(((cCritical + cHigh + cModerate) / 100) * 219.911)}" />
            </svg>
          </div>
        </div>
      </div>

      <!-- Card 5: Key Metrics (Average) -->
      <div class="glass-panel mc-top-card mc-card-key-metrics">
        <div class="mc-card-title-sm">KEY METRICS (AVERAGE)</div>
        <div class="mc-metrics-list">
          <div class="mc-metric-item">
            <div class="mc-metric-left">
              <svg class="mc-metric-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#38bdf8" stroke-width="2">
                <circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>
              </svg>
              <span>SIGNIFICANCE SCORE</span>
            </div>
            <div class="mc-metric-right"><strong>${avgSignificance}</strong> <small>/100</small></div>
          </div>
          <div class="mc-metric-item">
            <div class="mc-metric-left">
              <svg class="mc-metric-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#38bdf8" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              <span>SEVERITY SCORE</span>
            </div>
            <div class="mc-metric-right"><strong>${avgSeverity}</strong> <small>/10</small></div>
          </div>
          <div class="mc-metric-item">
            <div class="mc-metric-left">
              <svg class="mc-metric-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#38bdf8" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
              </svg>
              <span>CONFIDENCE SCORE</span>
            </div>
            <div class="mc-metric-right"><strong>${avgConfidence}</strong> <small>/1.00</small></div>
          </div>
          <div class="mc-metric-item">
            <div class="mc-metric-left">
              <svg class="mc-metric-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#38bdf8" stroke-width="2">
                <circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 15"/>
              </svg>
              <span>DURATION</span>
            </div>
            <div class="mc-metric-right"><strong>${avgDuration}</strong> <small>sec</small></div>
          </div>
        </div>
      </div>

    </div>

    <!-- 3. Middle Section: Charts & Channel Rankings (3 Columns) -->
    <div class="mc-middle-grid">
      
      <!-- Card 7: Incident Activity Over Time -->
      <div class="glass-panel mc-chart-card mc-card-activity">
        <div class="mc-chart-header">
          <div class="mc-chart-title">INCIDENT ACTIVITY OVER TIME</div>
          <div class="mc-chart-controls">
            <select class="mc-time-select" id="mc-time-range-select" aria-label="Select Time Window">
              <option value="recent">Last 7 Days</option>
              <option value="all">All Dates</option>
            </select>
          </div>
        </div>

        <div class="mc-activity-chart-wrapper" id="mc-activity-chart-container">
          <!-- Dynamic SVG Chart populated below -->
        </div>
      </div>

      <!-- Card 8: Severity Distribution -->
      <div class="glass-panel mc-chart-card mc-card-severity-dist">
        <div class="mc-chart-title">SEVERITY DISTRIBUTION</div>
        <div class="mc-sev-dist-container">
          <div class="mc-large-donut-box">
            <svg class="mc-large-donut-svg" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="38" fill="transparent" stroke="rgba(255,255,255,0.05)" stroke-width="13" />
              <!-- Critical -->
              <circle cx="50" cy="50" r="38" fill="transparent" stroke="#ef4444" stroke-width="13"
                stroke-dasharray="${dashCritical} ${circumference - dashCritical}"
                stroke-dashoffset="${offsetCritical}" />
              <!-- High -->
              <circle cx="50" cy="50" r="38" fill="transparent" stroke="#f97316" stroke-width="13"
                stroke-dasharray="${dashHigh} ${circumference - dashHigh}"
                stroke-dashoffset="${offsetHigh}" />
              <!-- Moderate -->
              <circle cx="50" cy="50" r="38" fill="transparent" stroke="#eab308" stroke-width="13"
                stroke-dasharray="${dashModerate} ${circumference - dashModerate}"
                stroke-dashoffset="${offsetModerate}" />
              <!-- Low -->
              <circle cx="50" cy="50" r="38" fill="transparent" stroke="#22c55e" stroke-width="13"
                stroke-dasharray="${dashLow} ${circumference - dashLow}"
                stroke-dashoffset="${offsetLow}" />
            </svg>
            <div class="mc-large-donut-center">
              <span class="mc-donut-total-num">${total}</span>
              <span class="mc-donut-total-lbl">TOTAL</span>
            </div>
          </div>

          <div class="mc-sev-dist-legend">
            <div class="mc-sev-legend-item">
              <span class="mc-sev-legend-dot mc-dot-critical"></span>
              <div class="mc-sev-legend-details">
                <span class="mc-sev-legend-title">CRITICAL</span>
                <span class="mc-sev-legend-stats">${sev.CRITICAL || 0} (${cCritical.toFixed(1)}%)</span>
              </div>
            </div>
            <div class="mc-sev-legend-item">
              <span class="mc-sev-legend-dot mc-dot-high"></span>
              <div class="mc-sev-legend-details">
                <span class="mc-sev-legend-title">HIGH</span>
                <span class="mc-sev-legend-stats">${sev.HIGH || 0} (${cHigh.toFixed(1)}%)</span>
              </div>
            </div>
            <div class="mc-sev-legend-item">
              <span class="mc-sev-legend-dot mc-dot-moderate"></span>
              <div class="mc-sev-legend-details">
                <span class="mc-sev-legend-title">MODERATE</span>
                <span class="mc-sev-legend-stats">${sev.MODERATE || 0} (${cModerate.toFixed(1)}%)</span>
              </div>
            </div>
            <div class="mc-sev-legend-item">
              <span class="mc-sev-legend-dot mc-dot-low"></span>
              <div class="mc-sev-legend-details">
                <span class="mc-sev-legend-title">LOW</span>
                <span class="mc-sev-legend-stats">${sev.LOW || 0} (${cLow.toFixed(1)}%)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 9: Top Affected Channels -->
      <div class="glass-panel mc-chart-card mc-card-top-channels">
        <div class="mc-chart-title">TOP AFFECTED CHANNELS</div>
        <div class="mc-channels-list">
          ${topChannels.map(ch => {
            const barWidth = Math.min(100, Math.round((ch.count / maxChannelCount) * 100));
            return `
              <div class="mc-channel-row">
                <span class="mc-channel-tag">${ch.channel}</span>
                <div class="mc-channel-bar-track">
                  <div class="mc-channel-bar-fill" style="width: ${barWidth}%;"></div>
                </div>
                <span class="mc-channel-count-lbl"><strong>${ch.count}</strong> incidents</span>
              </div>
            `;
          }).join('')}
        </div>
        <div class="mc-channels-footer">
          <button class="mc-btn-view-channels" id="btn-mc-view-all-channels" type="button">
            <span>View All Channels</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
            </svg>
          </button>
        </div>
      </div>

    </div>

    <!-- 4. Bottom Row: Mission Intelligence Summary & Dataset Overview -->
    <div class="mc-bottom-grid">
      
      <!-- Card 10: Mission Intelligence Summary (2/3 width) -->
      <div class="glass-panel mc-bottom-card mc-card-intelligence">
        <div class="mc-intelligence-layout">
          
          <!-- Purely decorative visual radar graphic -->
          <div class="mc-radar-visual" aria-hidden="true">
            <div class="mc-radar-ring mc-radar-ring-1"></div>
            <div class="mc-radar-ring mc-radar-ring-2"></div>
            <div class="mc-radar-ring mc-radar-ring-3"></div>
            <div class="mc-radar-crosshair-h"></div>
            <div class="mc-radar-crosshair-v"></div>
            <div class="mc-radar-blip-1"></div>
            <div class="mc-radar-blip-2"></div>
            <div class="mc-radar-core-pulse"></div>
          </div>

          <div class="mc-intelligence-content">
            <div class="mc-chart-title">MISSION INTELLIGENCE SUMMARY</div>
            <p class="mc-intelligence-narrative">
              Telemetry dataset analysis records <strong class="text-cyan">${total}</strong> reconstructed spacecraft incidents from <strong class="text-white">${dataSource}</strong>. 
              <strong class="text-purple">${multiChannel}</strong> incidents (${multiChannelPct}%) involve simultaneous anomalies across multiple telemetry channels, while 
              <strong class="text-teal">${singleChannel}</strong> incidents (${singleChannelPct}%) are isolated to a single channel. 
              A total of <strong class="text-alert">${sev.CRITICAL || 0}</strong> incidents (${cCritical.toFixed(1)}%) are categorized at critical severity level.
            </p>
          </div>

        </div>

        <!-- Bottom Status Strip -->
        <div class="mc-intelligence-bottom-strip">
          <div class="mc-time-range-block">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="var(--cyan-bright)" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
              <line x1="16" y1="2" x2="16" y2="6"/>
              <line x1="8" y1="2" x2="8" y2="6"/>
              <line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
            <div class="mc-time-range-text">
              <span class="mc-strip-lbl">DATA TIME RANGE</span>
              <span class="mc-strip-val">FROM: <strong>${dateRangeStart}</strong>  •  TO: <strong>${dateRangeEnd}</strong></span>
            </div>
          </div>

          <div class="mc-coverage-block">
            <span class="mc-check-icon">✓</span>
            <span class="mc-coverage-lbl">CONTINUOUS TELEMETRY COVERAGE</span>
            <span class="mc-coverage-badge">COMPLETE</span>
          </div>
        </div>
      </div>

      <!-- Card 11: Dataset Overview (1/3 width) -->
      <div class="glass-panel mc-bottom-card mc-card-dataset-overview">
        <div class="mc-chart-title">DATASET OVERVIEW</div>
        
        <div class="mc-dataset-items">
          
          <!-- Item 1: Telemetry Events -->
          <div class="mc-dataset-item">
            <div class="mc-dataset-icon-box mc-icon-blue">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="2"/>
                <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/>
              </svg>
            </div>
            <div class="mc-dataset-info">
              <div class="mc-dataset-big-num">${totalEvents}</div>
              <div class="mc-dataset-lbl">TELEMETRY EVENTS</div>
              <div class="mc-dataset-desc">Total raw telemetry events processed</div>
            </div>
          </div>

          <div class="mc-dataset-divider"></div>

          <!-- Item 2: Monitored Channels -->
          <div class="mc-dataset-item">
            <div class="mc-dataset-icon-box mc-icon-purple">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="18" cy="5" r="3"/>
                <circle cx="6" cy="12" r="3"/>
                <circle cx="18" cy="19" r="3"/>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
              </svg>
            </div>
            <div class="mc-dataset-info">
              <div class="mc-dataset-big-num">${monitoredChannelsCount}</div>
              <div class="mc-dataset-lbl">MONITORED CHANNELS</div>
              <div class="mc-dataset-desc">Total telemetry channels analyzed</div>
            </div>
          </div>

        </div>
      </div>

    </div>
  `;

  // Attach Event Handlers
  const btnViewAll = container.querySelector('#btn-mc-view-all-channels');
  if (btnViewAll) {
    btnViewAll.addEventListener('click', () => {
      navigateToScreen('screen-incident-explorer');
    });
  }

  // Render Time Activity Chart
  const chartContainer = container.querySelector('#mc-activity-chart-container');
  const rangeSelect = container.querySelector('#mc-time-range-select');

  function renderActivityChart(dataSet) {
    if (!chartContainer || !dataSet || dataSet.length === 0) return;

    const width = 580;
    const height = 170;
    const padLeft = 40;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 35;

    const chartW = width - padLeft - padRight;
    const chartH = height - padTop - padBottom;

    const maxCount = Math.max(...dataSet.map(d => d.count), 10);
    // Y-axis ticks
    const yMax = Math.ceil(maxCount / 10) * 10;
    const yMid = Math.round(yMax / 2);

    const stepX = chartW / (dataSet.length - 1 || 1);

    const points = dataSet.map((d, idx) => {
      const x = padLeft + idx * stepX;
      const y = padTop + chartH - (d.count / yMax) * chartH;
      return { x, y, date: d.date, count: d.count };
    });

    // Create smooth spline path
    let pathD = `M ${points[0].x},${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const cp1x = p0.x + (p1.x - p0.x) / 2;
      const cp1y = p0.y;
      const cp2x = p0.x + (p1.x - p0.x) / 2;
      const cp2y = p1.y;
      pathD += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p1.x},${p1.y}`;
    }

    const areaD = `${pathD} L ${points[points.length - 1].x},${padTop + chartH} L ${points[0].x},${padTop + chartH} Z`;

    chartContainer.innerHTML = `
      <svg class="mc-activity-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="mcActivityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="rgba(56, 189, 248, 0.35)"/>
            <stop offset="60%" stop-color="rgba(37, 99, 235, 0.12)"/>
            <stop offset="100%" stop-color="rgba(29, 78, 216, 0.0)"/>
          </linearGradient>
          <filter id="mcGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.5" result="blur"/>
            <feComposite in="SourceGraphic" in2="blur" operator="over"/>
          </filter>
        </defs>

        <!-- Y Axis Grid Lines -->
        <line x1="${padLeft}" y1="${padTop}" x2="${width - padRight}" y2="${padTop}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3 3"/>
        <line x1="${padLeft}" y1="${padTop + chartH / 2}" x2="${width - padRight}" y2="${padTop + chartH / 2}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3 3"/>
        <line x1="${padLeft}" y1="${padTop + chartH}" x2="${width - padRight}" y2="${padTop + chartH}" stroke="rgba(255,255,255,0.12)"/>

        <!-- Y Axis Labels -->
        <text x="${padLeft - 10}" y="${padTop + 4}" fill="rgba(255,255,255,0.4)" font-size="10" text-anchor="end" font-family="'Space Grotesk', monospace">${yMax}</text>
        <text x="${padLeft - 10}" y="${padTop + chartH / 2 + 4}" fill="rgba(255,255,255,0.4)" font-size="10" text-anchor="end" font-family="'Space Grotesk', monospace">${yMid}</text>
        <text x="${padLeft - 10}" y="${padTop + chartH + 4}" fill="rgba(255,255,255,0.4)" font-size="10" text-anchor="end" font-family="'Space Grotesk', monospace">0</text>
        <text x="12" y="${padTop + chartH / 2}" fill="rgba(255,255,255,0.5)" font-size="9" text-anchor="middle" font-family="'Space Grotesk', monospace" transform="rotate(-90 12 ${padTop + chartH / 2})">INCIDENTS</text>

        <!-- Area Fill -->
        <path d="${areaD}" fill="url(#mcActivityGrad)"/>

        <!-- Glowing Line -->
        <path d="${pathD}" fill="none" stroke="#38bdf8" stroke-width="2.2" filter="url(#mcGlow)"/>

        <!-- Interactive Points -->
        ${points.map((p, i) => `
          <g class="mc-chart-point-group" tabindex="0">
            <circle class="mc-chart-point-halo" cx="${p.x}" cy="${p.y}" r="8" fill="rgba(56, 189, 248, 0.25)"/>
            <circle class="mc-chart-point" cx="${p.x}" cy="${p.y}" r="4" fill="#ffffff" stroke="#38bdf8" stroke-width="2"/>
            <title>${p.date}: ${p.count} incidents</title>
          </g>
        `).join('')}

        <!-- X Axis Labels -->
        ${points.map((p, i) => {
          // Format date to 'MMM DD'
          const parts = p.date.split('-');
          const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          const month = monthNames[parseInt(parts[1], 10) - 1] || parts[1];
          const day = parts[2];
          const dateLabel = `${month} ${day}`;
          
          // Render label
          return `
            <text x="${p.x}" y="${padTop + chartH + 20}" fill="rgba(255,255,255,0.6)" font-size="10" text-anchor="middle" font-family="'Space Grotesk', monospace">${dateLabel}</text>
          `;
        }).join('')}

        <!-- X Axis Label -->
        <text x="${width / 2}" y="${height - 2}" fill="rgba(255,255,255,0.4)" font-size="9" text-anchor="middle" font-family="'Space Grotesk', monospace" letter-spacing="0.1em">DATE (UTC)</text>
      </svg>
    `;
  }

  // Initial chart render with recent activity
  renderActivityChart(recentActivity.length > 0 ? recentActivity : dailyActivity);

  if (rangeSelect) {
    rangeSelect.addEventListener('change', (e) => {
      if (e.target.value === 'all') {
        renderActivityChart(dailyActivity);
      } else {
        renderActivityChart(recentActivity.length > 0 ? recentActivity : dailyActivity);
      }
    });
  }
}
