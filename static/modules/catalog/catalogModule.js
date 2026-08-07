/* ============================================================
   Enterprise AI Dashboard Platform — Catalog Overview Module
   ============================================================ */

import { moduleRegistry } from '../../js/moduleRegistry.js';
import { router } from '../../js/router.js';

export const catalogModule = {
  id: 'catalog',
  name: 'Trang chủ Hub',
  route: '/',
  icon: '🏠',
  category: 'Platform',
  description: 'Trung tâm tổng hợp & điều phối các công cụ AI',
  status: 'active',

  render(containerEl) {
    const modules = moduleRegistry.getAllModules().filter(m => m.id !== 'catalog');

    containerEl.innerHTML = `
      <div class="workspace-page-header">
        <div class="page-title-group">
          <h1>⚡ Monalimeow AI Platform Catalog</h1>
          <p>Chọn công cụ AI bên dưới để bắt đầu làm việc ngay lập tức.</p>
        </div>
        <div style="width:280px;">
          <input type="text" class="form-input" id="catalogSearchInput" placeholder="Tìm nhanh module công cụ..." />
        </div>
      </div>

      <div class="module-grid" id="catalogModuleGrid">
        ${modules.map(mod => `
          <div class="module-card" data-search="${mod.name.toLowerCase()} ${mod.description.toLowerCase()}">
            <div>
              <div class="module-card-header">
                <div class="module-icon-box">${mod.icon}</div>
                <span class="badge-tag ${mod.status === 'active' ? 'badge-active' : 'badge-soon'}">
                  ${mod.status === 'active' ? 'Hoạt động' : 'Sắp có'}
                </span>
              </div>
              <div class="module-card-body">
                <h3>${mod.name}</h3>
                <p>${mod.description}</p>
              </div>
            </div>
            <div class="module-card-footer">
              <span style="font-size:0.75rem; color:var(--text-dim); font-weight:600;">${mod.category}</span>
              <button class="btn ${mod.status === 'active' ? 'btn-primary' : 'btn-secondary'}" data-route="${mod.route}">
                ${mod.status === 'active' ? 'Khởi Chạy ➔' : 'Xem Preview'}
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // Attach card click routing
    containerEl.querySelectorAll('button[data-route]').forEach(btn => {
      btn.addEventListener('click', () => {
        const route = btn.getAttribute('data-route');
        if (route) router.navigate(route);
      });
    });

    // Catalog search filter
    const searchInput = containerEl.querySelector('#catalogSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        containerEl.querySelectorAll('.module-card').forEach(card => {
          const searchData = card.getAttribute('data-search') || '';
          if (searchData.includes(query)) {
            card.style.display = 'flex';
          } else {
            card.style.display = 'none';
          }
        });
      });
    }
  },

  unmount(containerEl) {
    containerEl.innerHTML = '';
  }
};
