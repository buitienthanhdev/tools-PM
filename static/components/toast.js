/* ============================================================
   MonaliMeow AI Platform — Interactive Toast Notification System
   ============================================================ */

import { eventBus } from '../stores/eventBus.js';

export class ToastContainer {
  constructor() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);

    eventBus.on('toast:show', (payload) => this.show(payload));
  }

  show({ message, type = 'info', duration = 4000, onClick = null }) {
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'toast-error' : ''}`;
    if (onClick) {
      toast.style.cursor = 'pointer';
    }

    toast.innerHTML = `<span>${message}</span>`;

    if (onClick) {
      toast.addEventListener('click', () => {
        try { onClick(); } catch (e) {}
        toast.remove();
      });
    }

    this.container.appendChild(toast);

    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
      }
    }, duration);
  }
}
