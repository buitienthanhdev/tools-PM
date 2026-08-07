/* ============================================================
   Enterprise AI Dashboard Platform — Shared API Client
   ============================================================ */

import { eventBus } from '../stores/eventBus.js';

export async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(endpoint, options);
    
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const message = errData.error || errData.message || `HTTP Error ${res.status}`;
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
