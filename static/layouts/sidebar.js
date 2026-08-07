/* ============================================================
   Enterprise AI Dashboard Platform — Left Sidebar Navigation Component
   ============================================================ */

import { moduleRegistry } from '../js/moduleRegistry.js';
import { router } from '../js/router.js';
import { globalStore } from '../stores/globalStore.js';
import { eventBus } from '../stores/eventBus.js';

export function renderSidebar(containerEl) {
  const modules = moduleRegistry.getAllModules();
  
  // Group modules by category
  const categories = {};
  modules.forEach(mod => {
    const cat = mod.category || 'General';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(mod);
  });

  let navHTML = '';
  for (const [catName, modGroup] of Object.entries(categories)) {
    navHTML += `
      <div class="nav-section">
        <div class="nav-section-label">${catName}</div>
        <ul class="nav-list">
    `;

    modGroup.forEach(mod => {
      navHTML += `
        <li>
          <button class="nav-item-btn" data-route="${mod.route}" id="nav-btn-${mod.id}">
            <span class="nav-icon">${mod.icon}</span>
            <span class="nav-text">${mod.name}</span>
          </button>
        </li>
      `;
    });

    navHTML += `
        </ul>
      </div>
    `;
  }

  containerEl.innerHTML = `
    <aside class="app-sidebar" id="appSidebar">
      <div class="sidebar-header">
        <a href="/" class="brand-logo" onclick="event.preventDefault(); window.router.navigate('/');">
          <div class="brand-logo-wrapper">
            <img src="/assets/logo.webp?v=2.5.9" alt="PM Tools" class="brand-img-logo" />
            <div class="brand-logo-glow"></div>
          </div>
          <div class="brand-name">
            <span class="brand-name-main">PM Tools <span class="brand-accent">Hub</span></span>
            <span class="brand-tagline">AI Workspace Platform</span>
          </div>
        </a>
        <button class="sidebar-toggle-btn" id="sidebarCollapseBtn" title="Toggle Sidebar">
          <span>◀</span>
        </button>
      </div>

      <nav class="sidebar-nav">
        ${navHTML}
      </nav>

      <div class="sidebar-footer">
        <div style="font-size:0.72rem; color:var(--text-dim); text-align:center; letter-spacing:0.03em;">
          PM Tools Hub v3.0 &nbsp;·&nbsp; CUDA GPU
        </div>
      </div>
    </aside>
  `;

  // Attach nav item click listeners
  containerEl.querySelectorAll('.nav-item-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const route = btn.getAttribute('data-route');
      if (route) {
        router.navigate(route);
      }
    });
  });

  // Sidebar Collapse Toggle
  const collapseBtn = containerEl.querySelector('#sidebarCollapseBtn');
  const sidebarEl = containerEl.querySelector('#appSidebar');
  if (collapseBtn && sidebarEl) {
    collapseBtn.addEventListener('click', () => {
      globalStore.toggleSidebar();
    });
  }

  // Handle active state highlights on route change
  const updateActiveState = (activePath) => {
    containerEl.querySelectorAll('.nav-item-btn').forEach(btn => {
      const route = btn.getAttribute('data-route');
      if (route === activePath || (activePath === '/' && route === '/')) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  };

  eventBus.on('route:changed', (activePath) => updateActiveState(activePath));
  updateActiveState(router.getCurrentRoute());
}
