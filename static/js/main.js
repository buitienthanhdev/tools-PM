/**
 * PM Tools Hub — Main Bootstrapper
 * Static imports preserve singleton instances (moduleRegistry, eventBus, etc.)
 */

import { moduleRegistry } from './moduleRegistry.js';
import { router }         from './router.js';
import { globalStore }    from '../stores/globalStore.js';
import { eventBus }       from '../stores/eventBus.js';
import { jobTracker }     from '../services/jobTracker.js';
import { ToastContainer } from '../components/toast.js';
import { renderTopNav }   from '../layouts/topNav.js';
import { renderSidebar }  from '../layouts/sidebar.js';
import { renderWorkspaceContainer } from '../layouts/workspace.js';

import { catalogModule } from '../modules/catalog/catalogModule.js';
import { whisperModule } from '../modules/whisper/whisperModule.js';
import { voxcpmModule }  from '../modules/voxcpm/voxcpmModule.js';
import { imageModule }   from '../modules/image/imageModule.js';
import { genreportModule } from '../modules/genreport/genreportModule.js';
import { legalModule } from '../modules/legal/legalModule.js';
import { spacetModule } from '../modules/spacet/spacetModule.js';
import { reviewingcvModule } from '../modules/reviewingcv/reviewingcvModule.js';
import { accountingModule } from '../modules/accounting/accountingModule.js';
import { videoModule } from '../modules/video/videoModule.js';
import { authModule } from '../modules/auth/authModule.js';
import { adminModule } from '../modules/auth/adminModule.js';
import { authStore } from '../stores/authStore.js';

async function boot() {
  console.log('[PM Tools Hub] Booting platform...');

  // 1. Toast system
  new ToastContainer();

  // 2. Register modules into the SHARED registry singleton
  moduleRegistry.register(catalogModule);
  moduleRegistry.register(whisperModule);
  moduleRegistry.register(voxcpmModule);
  moduleRegistry.register(imageModule);
  moduleRegistry.register(genreportModule);
  moduleRegistry.register(legalModule);
  moduleRegistry.register(spacetModule);
  moduleRegistry.register(reviewingcvModule);
  moduleRegistry.register(authModule);
  moduleRegistry.register(adminModule);
  window.moduleRegistry = moduleRegistry;

  // Biết ai đang đăng nhập trước khi dựng trang
  await authStore.refresh();

  // Kế toán AI chỉ xuất hiện khi máy chủ đã bật module (features.accounting)
  if (authStore.features.accounting) moduleRegistry.register(accountingModule);
  // Video Workspace chỉ xuất hiện khi máy chủ đã bật module (features.video)
  if (authStore.features.video) moduleRegistry.register(videoModule);

  // 3. Render layout shell
  const sidebarMount   = document.getElementById('sidebarMount');
  const topNavMount    = document.getElementById('topNavMount');
  const workspaceMount = document.getElementById('workspaceMount');

  if (sidebarMount)   renderSidebar(sidebarMount);
  if (topNavMount)    renderTopNav(topNavMount);
  if (workspaceMount) renderWorkspaceContainer(workspaceMount);

  // 4. Init router — must come AFTER modules are registered
  const viewport = document.getElementById('workspaceContent');
  if (viewport) router.init(viewport);

  // 5. Global listener for completed background jobs
  window.addEventListener('monali:job_completed', (e) => {
    const job = e.detail;
    eventBus.emit('toast:show', {
      message: `🎉 ${job.title} đã hoàn thành! Click để xem kết quả.`,
      type: 'success',
      duration: 10000,
      onClick: () => router.navigate(job.route)
    });
  });

  // 6. Health polling
  async function checkHealth() {
    try {
      const r = await fetch('/api/health');
      if (r.ok) globalStore.setSystemHealth(await r.json());
    } catch { globalStore.setSystemHealth({ status: 'connecting', device: 'CPU' }); }
  }
  checkHealth();
  setInterval(checkHealth, 30000);

  console.log('[PM Tools Hub] Platform ready!');
}

document.addEventListener('DOMContentLoaded', boot);
