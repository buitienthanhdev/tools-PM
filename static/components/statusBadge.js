/* ============================================================
   MonaliMeow AI Platform — Live AI Engine Status & Progress Badge
   Displays live backend job progress, % complete, and active status.
   ============================================================ */

import { globalStore } from '../stores/globalStore.js';
import { eventBus } from '../stores/eventBus.js';
import { jobTracker } from '../services/jobTracker.js';

export function renderStatusBadge(containerEl) {
  let activeJob = null;

  const render = () => {
    const health = globalStore.getState().systemHealth || { status: 'ok', device: 'CUDA' };
    const isOk = health.status === 'ok';

    if (activeJob && (activeJob.status === 'processing' || activeJob.status === 'queued')) {
      // Active Job Running State
      const pct = activeJob.progress || 10;
      const msg = activeJob.message || 'Đang xử lý...';
      const icon = activeJob.module === 'whisper' ? '🎙️' : '🔊';

      containerEl.innerHTML = `
        <div class="status-pill status-pill-running" id="liveJobPill" style="cursor:pointer;" title="Bấm để mở giao diện tác vụ đang chạy">
          <span class="status-dot status-dot-active"></span>
          <div style="display:flex; flex-direction:column; line-height:1.2; text-align:left;">
            <div style="font-size:0.75rem; font-weight:800; color:var(--primary); display:flex; align-items:center; gap:0.35rem;">
              <span>${icon} ${activeJob.title}</span>
              <span class="pct-badge">${pct}%</span>
            </div>
            <div style="font-size:0.68rem; color:var(--text-main); font-weight:500; text-overflow:ellipsis; overflow:hidden; max-width:260px; white-space:nowrap;">
              ${msg}
            </div>
          </div>
        </div>
      `;

      const pill = containerEl.querySelector('#liveJobPill');
      if (pill) {
        pill.onclick = () => {
          if (window.router) window.router.navigate(activeJob.route);
        };
      }
    } else {
      // System Idle / Ready State
      const text = isOk ? `System Ready · ${health.device.toUpperCase()} GPU` : 'Connecting to AI Engine...';
      containerEl.innerHTML = `
        <div class="status-pill">
          <span class="status-dot" style="${isOk ? '' : 'background-color: var(--amber); box-shadow: 0 0 8px var(--amber);'}"></span>
          <span style="font-size:0.78rem; font-weight:600;">${text}</span>
        </div>
      `;
    }
  };

  // Subscribe to system health updates
  eventBus.on('health:updated', render);

  // Subscribe to background jobTracker updates
  jobTracker.subscribe(job => {
    if (job.status === 'processing' || job.status === 'queued') {
      activeJob = job;
    } else if (activeJob && activeJob.id === job.id) {
      activeJob = null;
    }
    render();
  });

  render();
}
