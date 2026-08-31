/**
 * ClueSpace Screen 4: WATSONX BRIEF
 * Source of truth: Member 3.pdf (Page 6-7)
 * Simplified interface for IBM watsonx AI Investigation Brief.
 */

export function renderWatsonxBrief(container) {
  container.innerHTML = `
    <!-- Screen Header -->
    <div class="screen-header-block">
      <h1 class="screen-main-heading">IBM watsonx</h1>
      <p class="screen-sub-prompt">AI INVESTIGATION BRIEF</p>
    </div>

    <!-- Interactive Generate Brief Interface -->
    <div class="glass-panel wx-brief-container">
      <h2 class="wx-title">IBM watsonx</h2>
      <p class="wx-subtitle">AI INVESTIGATION BRIEF</p>
      
      <button class="btn-generate-brief" id="btn-generate-brief">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
        <span>GENERATE BRIEF</span>
      </button>

      <div class="wx-generation-status" id="wx-generation-status">
        Ready to generate AI investigation brief for active incident.
      </div>
    </div>
  `;

  const btn = container.querySelector('#btn-generate-brief');
  const status = container.querySelector('#wx-generation-status');
  if (btn && status) {
    btn.addEventListener('click', () => {
      status.innerHTML = `
        <span style="color: var(--blue-electric, #38bdf8);">[ Brief Generation Pipeline Ready ]</span><br>
        UI → Python API → IBM watsonx → AI-generated investigation brief → UI
      `;
    });
  }
}
