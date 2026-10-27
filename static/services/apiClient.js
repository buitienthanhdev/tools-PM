/* ============================================================
   Enterprise AI Dashboard Platform — Shared API Client
   ============================================================ */

import { eventBus } from '../stores/eventBus.js';

// Server đang khởi động lại / Cloudflare tạm 502-504 → GET tự thử lại vài lần thay vì báo lỗi ngay.
// Không thử lại POST/PUT/DELETE để không gửi trùng tác vụ.
const RETRY_STATUS = new Set([502, 503, 504, 520, 521, 522, 523, 524]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchWithRetry(endpoint, options) {
  const method = (options.method || 'GET').toUpperCase();
  const tries = method === 'GET' || method === 'HEAD' ? 4 : 1;
  for (let i = 1; ; i++) {
    try {
      const res = await fetch(endpoint, options);
      if (i < tries && RETRY_STATUS.has(res.status)) { await sleep(1500 * i); continue; }
      return res;
    } catch (err) {
      if (err.name === 'AbortError' || i >= tries) throw err;
      await sleep(1500 * i);
    }
  }
}

export async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetchWithRetry(endpoint, options);
    
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const message = errData.error || errData.message || (RETRY_STATUS.has(res.status) ? 'Máy chủ đang bận hoặc khởi động lại, vui lòng thử lại sau ít giây' : `HTTP Error ${res.status}`);
      eventBus.emit('toast:show', { message: `❌ ${message}`, type: 'error' });
      throw new Error(message);
    }
    
    return await res.json();
  } catch (err) {
    if (err.name !== 'AbortError') {
      console.error(`[API Error] ${endpoint}:`, err.message);
    }
    throw err;
  }
}
