/* Trạng thái đăng nhập + tiện ích gọi API tài khoản. */

import { eventBus } from './eventBus.js';

async function api(path, body, method = 'POST') {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || `HTTP ${res.status}`), { code: data.code, status: res.status });
  return data;
}

class AuthStore {
  constructor() {
    this.user = null;
    this.loaded = false;
    this.modules = [];
    this.needsAdminSetup = false;
    this.features = {};
  }

  async refresh() {
    try {
      const d = await (await fetch('/api/auth/me')).json();
      this.user = d.user;
      this.modules = d.modules || [];
      this.needsAdminSetup = !!d.needs_admin_setup;
      this.features = d.features || {};
    } catch {
      this.user = null;
    }
    this.loaded = true;
    eventBus.emit('auth:changed', this.user);
    return this.user;
  }

  isActive() { return !!this.user && this.user.status === 'active'; }
  isAdmin() { return this.isActive() && this.user.role === 'admin'; }
  can(moduleId) { return this.isActive() && (this.user.role === 'admin' || this.user.modules.includes(moduleId)); }

  async login(email, password) {
    const d = await api('/api/auth/login', { email, password });
    this.user = d.user; eventBus.emit('auth:changed', this.user); return d.user;
  }

  async register(payload) {
    const d = await api('/api/auth/register', payload);
    this.user = d.user; eventBus.emit('auth:changed', this.user); return d.user;
  }

  async logout() {
    await api('/api/auth/logout', {});
    this.user = null; eventBus.emit('auth:changed', null);
  }

  changePassword(old_password, new_password) { return api('/api/auth/password', { old_password, new_password }); }
  adminUsers() { return api('/api/admin/users', null, 'GET'); }
  adminUpdate(email, patch) { return api(`/api/admin/users/${encodeURIComponent(email)}`, patch); }
  adminDelete(email) { return api(`/api/admin/users/${encodeURIComponent(email)}`, null, 'DELETE'); }
}

export const authStore = new AuthStore();
window.authStore = authStore;

// Mọi API trả 401 (hết phiên) → làm mới trạng thái và đưa về trang đăng nhập.
const _fetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const res = await _fetch(...args);
  try {
    const url = String(typeof args[0] === 'string' ? args[0] : args[0]?.url || '');
    if (res.status === 401 && url.startsWith('/api/') && !url.startsWith('/api/auth/')) {
      if (authStore.user) { authStore.user = null; eventBus.emit('auth:changed', null); }
      eventBus.emit('auth:expired');
    }
  } catch { /* bỏ qua */ }
  return res;
};
