/* ============================================================
   MonaliMeow AI Platform — Client SPA Router
   ============================================================ */

import { moduleRegistry } from './moduleRegistry.js';
import { globalStore } from '../stores/globalStore.js';
import { authStore } from '../stores/authStore.js';
import { eventBus } from '../stores/eventBus.js';

class Router {
  constructor() {
    this.currentModule = null;
    this.workspaceEl = null;

    window.addEventListener('popstate', () => {
      this.handleRouteResolution(window.location.pathname);
    });
  }

  init(workspaceViewportEl) {
    this.workspaceEl = workspaceViewportEl;
    this.handleRouteResolution(window.location.pathname);
  }

  getCurrentRoute() {
    return window.location.pathname;
  }

  navigate(targetPath, pushHistory = true) {
    if (!targetPath) targetPath = '/';

    if (pushHistory && window.location.pathname !== targetPath) {
      history.pushState({ route: targetPath }, '', targetPath);
    }

    this.handleRouteResolution(targetPath);
  }

  handleRouteResolution(path) {
    let moduleObj = moduleRegistry.getModuleByRoute(path);

    if (!moduleObj) {
      console.warn(`[Router] No module found for route '${path}'. Defaulting to Catalog.`);
      moduleObj = moduleRegistry.getModuleById('catalog') || moduleRegistry.getAllModules()[0];
    }

    if (!moduleObj) {
      console.error('[Router] Critical: No modules registered in registry.');
      if (this.workspaceEl) {
        this.workspaceEl.innerHTML = `
          <div class="panel-card" style="padding:3rem; text-align:center;">
            <h2>⚠️ Hệ thống đang khởi tạo</h2>
            <p style="color:var(--text-dim); margin-top:0.5rem;">Chưa tìm thấy module. Vui lòng tải lại trang.</p>
          </div>
        `;
      }
      return;
    }

    // Chặn công cụ khi chưa đăng nhập / chưa được cấp quyền
    const OPEN = ['catalog', 'login'];
    if (!OPEN.includes(moduleObj.id) && authStore.loaded) {
      if (moduleObj.id === 'admin' ? !authStore.isAdmin() : !authStore.can(moduleObj.id)) {
        if (!authStore.user) sessionStorage.setItem('pm_next', path);
        else eventBus.emit('toast:show', { message: authStore.isActive() ? 'Bạn chưa được cấp quyền dùng công cụ này' : 'Tài khoản đang chờ admin duyệt', type: 'error' });
        if (window.location.pathname !== '/login') history.replaceState({ route: '/login' }, '', '/login');
        moduleObj = moduleRegistry.getModuleById('login');
      }
    }

    // Unmount previous active module if any
    if (this.currentModule && this.currentModule.unmount && this.workspaceEl) {
      try {
        this.currentModule.unmount(this.workspaceEl);
      } catch (err) {
        console.error(`[Router] Error unmounting module '${this.currentModule.name}':`, err);
      }
    }

    // Mount new target module
    this.currentModule = moduleObj;
    globalStore.setActiveRoute(moduleObj.route);

    if (this.workspaceEl) {
      this.workspaceEl.scrollTop = 0;
      try {
        moduleObj.render(this.workspaceEl);
      } catch (err) {
        console.error(`[Router] Error rendering module '${moduleObj.name}':`, err);
        this.workspaceEl.innerHTML = `
          <div class="panel-card" style="text-align:center; padding:3rem;">
            <h2>❌ Lỗi Tải Module</h2>
            <p style="color:var(--rose); margin-top:0.5rem;">${err.message}</p>
            <button class="btn btn-primary" style="margin-top:1.5rem;" onclick="window.router.navigate('/')">Về Trang Chủ</button>
          </div>
        `;
      }
    }
  }
}

export const router = new Router();
window.router = router;
