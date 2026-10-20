/* ============================================================
   Enterprise AI Dashboard Platform — Global Application Store
   ============================================================ */

import { eventBus } from './eventBus.js';

class GlobalStore {
  constructor() {
    this.state = {
      theme: 'dark', // giao diện Webfolio chỉ có nền tối
      activeRoute: 'catalog',
      systemHealth: {
        status: 'connecting',
        device: 'CPU',
        torchVersion: '2.13.0',
        cudaAvailable: false
      },
      user: {
        name: 'AI Master',
        role: 'Administrator',
        avatar: 'AI'
      },
      sidebarCollapsed: localStorage.getItem('pm_sidebar_collapsed') === 'true'
    };

    // Apply saved theme on boot
    document.documentElement.setAttribute('data-theme', this.state.theme);
  }

  getState() {
    return this.state;
  }

  setTheme(theme) {
    this.state.theme = theme;
    localStorage.setItem('pm_theme_v2', theme);
    document.documentElement.setAttribute('data-theme', theme);
    eventBus.emit('theme:changed', theme);
  }

  toggleTheme() {
    const nextTheme = this.state.theme === 'dark' ? 'light' : 'dark';
    this.setTheme(nextTheme);
  }

  toggleSidebar() {
    this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
    localStorage.setItem('pm_sidebar_collapsed', this.state.sidebarCollapsed);
    eventBus.emit('sidebar:toggle', this.state.sidebarCollapsed);
  }

  setSystemHealth(health) {
    this.state.systemHealth = { ...this.state.systemHealth, ...health };
    eventBus.emit('health:updated', this.state.systemHealth);
  }

  setActiveRoute(routeId) {
    this.state.activeRoute = routeId;
    eventBus.emit('route:changed', routeId);
  }
}

export const globalStore = new GlobalStore();
