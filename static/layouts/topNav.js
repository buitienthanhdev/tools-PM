/* ============================================================
   Enterprise AI Dashboard Platform — Top Navigation Bar Component
   ============================================================ */

import { globalStore } from '../stores/globalStore.js';
import { renderStatusBadge } from '../components/statusBadge.js';
import { router } from '../js/router.js';

export function renderTopNav(containerEl) {
  containerEl.innerHTML = `
    <header class="app-topnav">
      <div class="topbar-left">
        <button class="sidebar-toggle-btn" id="mobileMenuBtn" style="display:none;">
          <span>☰</span>
        </button>
        <div class="search-box">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input type="text" class="search-input" id="globalSearchInput" placeholder="Tìm kiếm AI Module hoặc câu lệnh (Ctrl + K)..." />
        </div>
      </div>
      
      <div class="topbar-right">
        <div id="statusBadgeMount"></div>

        <button class="btn btn-secondary" id="themeToggleBtn" style="padding:0.4rem 0.75rem;">
          <span id="themeIcon">🌙</span>
        </button>

        <div class="user-profile-btn">
          <div class="user-avatar">AI</div>
          <span class="user-name">AI Master</span>
        </div>
      </div>
    </header>
  `;

  // Mount Status Badge
  const statusMount = containerEl.querySelector('#statusBadgeMount');
  if (statusMount) {
    renderStatusBadge(statusMount);
  }

  // Theme Toggle Listener
  const themeBtn = containerEl.querySelector('#themeToggleBtn');
  const themeIcon = containerEl.querySelector('#themeIcon');
  if (themeBtn && themeIcon) {
    themeBtn.addEventListener('click', () => {
      globalStore.toggleTheme();
      const current = globalStore.getState().theme;
      themeIcon.textContent = current === 'dark' ? '🌙' : '☀️';
    });
  }

  // Global Search Filter Listener
  const searchInput = containerEl.querySelector('#globalSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      const currentRoute = router.getCurrentRoute();
      if (currentRoute !== '/' && currentRoute !== '/catalog') {
        router.navigate('/');
      }
      setTimeout(() => {
        const catalogSearch = document.getElementById('catalogSearchInput');
        if (catalogSearch) {
          catalogSearch.value = q;
          catalogSearch.dispatchEvent(new Event('input'));
        }
      }, 50);
    });
  }
}
