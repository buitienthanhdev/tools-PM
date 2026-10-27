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
import { authModule } from '../modules/auth/authModule.js';
import { authStore } from '../stores/authStore.js';

// Công cụ chỉ tải mã khi mở lần đầu (lazy) — trang chủ không phải tải ~500KB JS của mọi công cụ.
// Metadata ở đây phải khớp với object export trong từng file module.
function lazyModule(meta, load) {
  let real = null;
  let pending = null;
  const stub = {
    ...meta,
    async render(el) {
      if (!real) {
        el.innerHTML = '<div class="lazy-loading"><span class="spinner"></span></div>';
        try {
          real = await (pending ||= load());
        } catch (err) {
          pending = null;
          throw err;
        }
        if (router.currentModule !== stub) return; // người dùng đã chuyển trang trong lúc tải
      }
      return real.render(el);
    },
    unmount(el) {
      real?.unmount?.(el);
    },
    preload() {
      if (!real && !pending) pending = load().then((m) => (real = m), (err) => { pending = null; throw err; });
      return pending;
    },
  };
  return stub;
}

const whisperModule = lazyModule(
  { id: 'whisper', name: 'Whisper Speech AI', route: '/Whisper', icon: '🎙️', category: 'Speech AI', status: 'active',
    description: 'Bóc băng âm thanh, dịch thuật và xuất phụ đề tự động bằng mô hình OpenAI Whisper GPU.' },
  () => import('../modules/whisper/whisperModule.js').then((m) => m.whisperModule));
const voxcpmModule = lazyModule(
  { id: 'voxcpm', name: 'VoxCPM Voice AI', route: '/VoxCPM', icon: '🔊', category: 'Speech AI', status: 'active',
    description: 'VoxCPM2 (2B) — 30 ngôn ngữ, Voice Design & Cloning, 48kHz WAV. Chạy trực tiếp trong trang.' },
  () => import('../modules/voxcpm/voxcpmModule.js').then((m) => m.voxcpmModule));
const imageModule = lazyModule(
  { id: 'image', name: 'Image Workspace', route: '/Image', icon: '🖼️', category: 'Vision AI', status: 'active',
    description: 'Chỉnh sửa và nâng cấp ảnh bằng AI theo dự án: ảnh nguồn bên trái, kết quả bên phải.' },
  () => import('../modules/image/imageModule.js').then((m) => m.imageModule));
const genreportModule = lazyModule(
  { id: 'genreport', name: 'Báo Cáo Tiến Độ (GenReport)', route: '/genreport', icon: '📄', category: 'Automation AI', status: 'active',
    description: 'Tự động sinh báo cáo tiến độ kỹ thuật chuyên sâu bằng AI local (Ollama) và xuất file Word (.docx) chuẩn doanh nghiệp.' },
  () => import('../modules/genreport/genreportModule.js').then((m) => m.genreportModule));
const legalModule = lazyModule(
  { id: 'legal', name: 'AI Tư vấn pháp luật', route: '/legal', icon: '⚖️', category: 'Legal AI', status: 'active',
    description: 'Hỏi đáp pháp luật bằng AI — trả lời có căn cứ điều luật, thân thiện và đầy đủ.' },
  () => import('../modules/legal/legalModule.js').then((m) => m.legalModule));
const spacetModule = lazyModule(
  { id: 'spacet', name: 'SpaceT', route: '/SpaceT', icon: '🌐', category: 'Geospatial', status: 'active',
    description: "Quả địa cầu 3D thời gian thực: máy bay, vệ tinh, động đất, thời tiết (God's Eye View)." },
  () => import('../modules/spacet/spacetModule.js').then((m) => m.spacetModule));
const reviewingcvModule = lazyModule(
  { id: 'reviewingcv', name: 'Reviewing CV', route: '/reviewingCV', icon: '📄', category: 'Career AI', status: 'active',
    description: 'Chấm CV theo tin tuyển dụng: điểm phù hợp, ATS, đề xuất sửa từng dòng (bộ quy tắc ai-job-search).' },
  () => import('../modules/reviewingcv/reviewingcvModule.js').then((m) => m.reviewingcvModule));
const accountingModule = lazyModule(
  { id: 'accounting', name: 'Kế toán AI', route: '/accounting', icon: '🧾', category: 'Finance AI', status: 'active',
    description: 'Kéo thả chứng từ, ra lệnh bằng tiếng Việt: AI đọc hoá đơn, sao kê, Excel, đối soát, định khoản đề xuất và xuất báo cáo có kiểm chứng.' },
  () => import('../modules/accounting/accountingModule.js').then((m) => m.accountingModule));
const videoModule = lazyModule(
  { id: 'video', name: 'Video Workspace', route: '/video', icon: '🎬', category: 'Video AI', status: 'active',
    description: 'Tăng độ phân giải, khử nhiễu, phục hồi video nén và nội suy fps bằng REAL-Video-Enhancer trên GPU riêng; có xử lý thử và so sánh trước/sau.' },
  () => import('../modules/video/videoModule.js').then((m) => m.videoModule));
const adminModule = lazyModule(
  { id: 'admin', name: 'Quản trị', route: '/admin', icon: '🛡️', category: 'Platform', status: 'active', hidden: true,
    description: 'Dashboard theo dõi, quản lý tài khoản và quyền truy cập' },
  () => import('../modules/auth/adminModule.js').then((m) => m.adminModule));

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

  // Lưới an toàn: server khởi động lại vẫn mở được trang (static/sw.js)
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  }

  // 6. Health polling
  async function checkHealth() {
    try {
      const r = await fetch('/api/health');
      if (r.ok) globalStore.setSystemHealth(await r.json());
    } catch { globalStore.setSystemHealth({ status: 'connecting', device: 'CPU' }); }
  }
  checkHealth();
  setInterval(() => { if (!document.hidden) checkHealth(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) checkHealth(); });

  // Rê chuột / chạm vào link công cụ → tải sẵn mã của công cụ đó để mở tức thì
  const warm = (e) => {
    const a = e.target.closest?.('a[href], [data-route]');
    const path = a && (a.getAttribute('data-route') || a.getAttribute('href'));
    if (path && path.startsWith('/')) moduleRegistry.getModuleByRoute(path)?.preload?.().catch(() => {});
  };
  document.addEventListener('pointerover', warm, { passive: true });
  document.addEventListener('touchstart', warm, { passive: true });

  console.log('[PM Tools Hub] Platform ready!');
}

document.addEventListener('DOMContentLoaded', boot);
