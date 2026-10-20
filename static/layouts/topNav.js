/* ============================================================
   PM Tools Hub — Header ngang kiểu Webfolio (thay sidebar + topbar cũ).
   Logo | Trang chủ · Công cụ ▾ (danh sách module) | trạng thái máy chủ · nút cam
   ============================================================ */

import { renderStatusBadge } from '../components/statusBadge.js';
import { router } from '../js/router.js';
import { moduleRegistry } from '../js/moduleRegistry.js';
import { eventBus } from '../stores/eventBus.js';
import { moduleIcon, svgIcon } from '../components/icons.js';
import { authStore } from '../stores/authStore.js';

export function renderTopNav(containerEl) {
  const modules = moduleRegistry.getAllModules().filter((m) => m.id !== 'catalog' && !m.hidden);

  containerEl.innerHTML = `
    <header class="hn" id="hn">
      <a class="hn-logo" href="/" data-link>
        <img src="/assets/logo.webp?v=2.5.9" alt="" />
        <b>PM Tools <span>Hub</span></b>
      </a>
      <nav class="hn-links">
        <a href="/" data-link data-nav="/">Trang chủ</a>
        <div class="hn-drop" id="hnDrop">
          <button type="button" aria-haspopup="true">Công cụ ${svgIcon('chevron', 14, 2.2)}</button>
          <div class="hn-menu" role="menu">
            ${modules.map((m) => `
              <a href="${m.route}" data-link data-nav="${m.route}" role="menuitem">
                <span class="ic">${moduleIcon(m, 18)}</span>
                <span><b>${m.name}</b><small>${m.category}</small></span>
              </a>`).join('')}
          </div>
        </div>
        <a href="/SpaceT" data-link data-nav="/SpaceT" class="hide-sm">SpaceT</a>
        <a href="/admin" data-link data-nav="/admin" id="hnAdmin" class="hide-sm" style="display:none">Quản trị</a>
      </nav>
      <div class="hn-right">
        <div id="statusBadgeMount"></div>
        <a class="hn-user" id="hnUser" href="/login" data-link>Đăng nhập</a>
        <a class="hn-cta" href="/" data-link>${svgIcon('grid', 16, 2)}<span>Tất cả công cụ</span></a>
        <a class="gh-ava" href="https://github.com/buitienthanhdev" target="_blank" rel="noopener" title="GitHub · buitienthanhdev"><span class="gh-ring"></span><img src="https://github.com/buitienthanhdev.png?size=96" alt="buitienthanhdev" /></a>
      </div>
    </header>
  `;

  const header = containerEl.querySelector('#hn');
  const drop = containerEl.querySelector('#hnDrop');

  renderStatusBadge(containerEl.querySelector('#statusBadgeMount'));

  // Người dùng hiện tại: tên + liên kết Quản trị cho admin
  const userEl = containerEl.querySelector('#hnUser');
  const adminEl = containerEl.querySelector('#hnAdmin');
  const paintUser = (u) => {
    userEl.textContent = u ? (u.status === 'active' ? (u.name || u.email) : 'Chờ duyệt') : 'Đăng nhập';
    userEl.classList.toggle('on', !!u);
    adminEl.style.display = authStore.isAdmin() ? '' : 'none';
  };
  eventBus.on('auth:changed', paintUser);
  paintUser(authStore.user);

  // Menu "Công cụ": mở bằng di chuột hoặc bấm (điện thoại)
  // (di chuột vào rồi bấm ngay thì giữ mở, không đóng lại)
  let openedAt = 0;
  const open = () => {
    if (!drop.classList.contains('open')) openedAt = Date.now();
    drop.classList.add('open');
  };
  drop.querySelector('button').addEventListener('click', (e) => {
    e.stopPropagation();
    if (drop.classList.contains('open') && Date.now() - openedAt > 400) drop.classList.remove('open');
    else open();
  });
  drop.addEventListener('mouseenter', open);
  drop.addEventListener('mouseleave', () => drop.classList.remove('open'));
  document.addEventListener('click', () => drop.classList.remove('open'));

  // Đánh dấu mục đang mở
  const markActive = (route) => {
    containerEl.querySelectorAll('[data-nav]').forEach((a) => {
      a.classList.toggle('on', a.dataset.nav.toLowerCase() === String(route || '/').toLowerCase());
    });
  };
  eventBus.on('route:changed', (route) => {
    markActive(route);
    drop.classList.remove('open');
    header.classList.remove('is-solid');
  });
  markActive(router.getCurrentRoute());

  // Header nền tối khi cuộn khỏi phần đầu trang
  requestAnimationFrame(() => {
    const scroller = document.getElementById('mainWorkspaceViewport');
    if (!scroller) return;
    scroller.addEventListener('scroll', () => {
      header.classList.toggle('is-solid', scroller.scrollTop > 40);
    }, { passive: true });
  });
}

// Liên kết nội bộ <a data-link> đi qua router thay vì tải lại trang
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[data-link]');
  if (!a || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
  e.preventDefault();
  router.navigate(a.dataset.link || a.getAttribute('href'));
});
