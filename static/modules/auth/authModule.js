/* Trang đăng nhập / đăng ký / tài khoản (route /login). */

import { authStore } from '../../stores/authStore.js';
import { eventBus } from '../../stores/eventBus.js';
import { router } from '../../js/router.js';
import { pageHero, panelHead, svgIcon } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });

const MODULE_NAMES = {
  whisper: 'Whisper Speech AI', voxcpm: 'VoxCPM Voice AI', image: 'Nét Ảnh AI', genreport: 'Báo cáo tiến độ',
  legal: 'AI Tư vấn pháp luật', spacet: 'SpaceT', reviewingcv: 'Reviewing CV', accounting: 'Kế toán AI', video: 'Video Workspace',
};

export const authModule = {
  id: 'login',
  name: 'Tài khoản',
  route: '/login',
  icon: '👤',
  category: 'Platform',
  description: 'Đăng nhập và quản lý tài khoản',
  status: 'active',
  hidden: true,

  _tab: 'login',

  async render(el) {
    await authStore.refresh();
    const u = authStore.user;

    if (u) return this._account(el, u);

    el.innerHTML = `
      ${pageHero(this, {
        title: 'Đăng nhập <span class="thin">để dùng</span> công cụ AI',
        sub: 'Tài khoản mới cần được quản trị viên duyệt và cấp quyền từng công cụ trước khi sử dụng.',
        word: 'Login',
        meta: ['Bảo mật', 'Admin cấp quyền', 'Dữ liệu riêng tư'],
      })}
      <div class="mp-body" style="max-width:560px;">
        <div class="mp-panel">
          <div class="au-tabs">
            <button type="button" data-tab="login" class="${this._tab === 'login' ? 'on' : ''}">Đăng nhập</button>
            <button type="button" data-tab="register" class="${this._tab === 'register' ? 'on' : ''}">Đăng ký</button>
          </div>
          <form id="au-form" autocomplete="on"></form>
        </div>
      </div>`;

    const form = el.querySelector('#au-form');
    const draw = () => {
      const reg = this._tab === 'register';
      form.innerHTML = `
        ${reg ? `<div class="form-group"><label class="form-label">Họ tên</label><input class="form-input" name="name" autocomplete="name" placeholder="Nguyễn Văn A" /></div>` : ''}
        <div class="form-group"><label class="form-label">${reg ? 'Email' : 'Email / Tên đăng nhập'}</label><input class="form-input" type="${reg ? 'email' : 'text'}" name="email" autocomplete="${reg ? 'email' : 'username'}" required placeholder="${reg ? 'ban@example.com' : 'Email hoặc tên đăng nhập'}" /></div>
        <div class="form-group"><label class="form-label">Mật khẩu</label><input class="form-input" type="password" name="password" required minlength="${reg ? 8 : 1}" autocomplete="${reg ? 'new-password' : 'current-password'}" placeholder="${reg ? 'Tối thiểu 8 ký tự' : ''}" /></div>
        ${reg && authStore.needsAdminSetup ? `<div class="form-group"><label class="form-label">Mã cài đặt admin <span style="text-transform:none;letter-spacing:0;color:var(--text-dim)">(chỉ dùng cho email quản trị lần đầu)</span></label><input class="form-input" name="setup_code" autocomplete="off" /></div>` : ''}
        <div id="au-err" class="mp-error" style="display:none;margin-bottom:16px;"></div>
        <button class="btn btn-primary btn-block btn-lg" type="submit">${reg ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
        ${reg ? '<div class="mp-hint" style="margin-top:14px;">' + svgIcon('bulb', 15, 2) + '<span>Sau khi đăng ký, quản trị viên sẽ duyệt và cấp quyền cho bạn.</span></div>' : ''}`;
    };
    draw();

    el.querySelectorAll('[data-tab]').forEach((b) => {
      b.onclick = () => {
        this._tab = b.dataset.tab;
        el.querySelectorAll('[data-tab]').forEach((x) => x.classList.toggle('on', x === b));
        draw();
      };
    });

    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(form));
      const err = form.querySelector('#au-err');
      const btn = form.querySelector('button[type=submit]');
      err.style.display = 'none';
      btn.disabled = true;
      try {
        if (this._tab === 'register') await authStore.register(fd);
        else await authStore.login(fd.email, fd.password);
        const next = sessionStorage.getItem('pm_next');
        sessionStorage.removeItem('pm_next');
        toast('Đăng nhập thành công', 'success');
        router.navigate(authStore.isActive() ? (next || '/') : '/login');
      } catch (ex) {
        err.textContent = ex.message;
        err.style.display = 'flex';
        btn.disabled = false;
      }
    };
  },

  _account(el, u) {
    const pending = u.status !== 'active';
    el.innerHTML = `
      ${pageHero(this, {
        title: pending ? 'Tài khoản <span class="thin">đang chờ</span> duyệt' : `Xin chào, <span class="thin">${esc(u.name || u.email)}</span>`,
        sub: pending
          ? 'Quản trị viên sẽ duyệt tài khoản và cấp quyền công cụ cho bạn. Bạn có thể quay lại trang này sau.'
          : 'Đây là các công cụ bạn được phép sử dụng.',
        word: 'Account',
        meta: [u.role === 'admin' ? 'Quản trị viên' : 'Thành viên', esc(u.email)],
      })}
      <div class="mp-body" style="max-width:900px;">
        <div class="mp-panel">
          ${panelHead('01', 'Quyền', 'truy cập')}
          ${pending
            ? `<div class="mp-empty"><div class="mp-drop-ic">${svgIcon('lock', 22)}</div>Chưa có quyền nào. Vui lòng chờ quản trị viên duyệt.</div>`
            : `<div class="au-mods">${u.modules.map((m) => `<a class="au-mod" href="#" data-go="${m}">${esc(MODULE_NAMES[m] || m)}</a>`).join('') || '<span style="color:var(--text-dim)">Chưa được cấp công cụ nào.</span>'}</div>`}
          ${u.role === 'admin' ? `<div style="margin-top:22px;"><button class="btn btn-primary" id="au-admin">${svgIcon('grid', 16, 2)} Mở trang quản trị</button></div>` : ''}
        </div>
        <div class="mp-panel">
          ${panelHead('02', 'Đổi', 'mật khẩu')}
          <form id="au-pw" style="max-width:420px;">
            <div class="form-group"><label class="form-label">Mật khẩu cũ</label><input class="form-input" type="password" name="old" required autocomplete="current-password" /></div>
            <div class="form-group"><label class="form-label">Mật khẩu mới</label><input class="form-input" type="password" name="new" required minlength="8" autocomplete="new-password" /></div>
            <button class="btn btn-secondary" type="submit">Cập nhật mật khẩu</button>
          </form>
        </div>
        <div><button class="btn btn-secondary" id="au-out">Đăng xuất</button></div>
      </div>`;

    el.querySelectorAll('[data-go]').forEach((a) => {
      a.onclick = (e) => {
        e.preventDefault();
        const mod = window.moduleRegistry?.getModuleById(a.dataset.go);
        router.navigate(mod ? mod.route : '/');
      };
    });
    el.querySelector('#au-admin')?.addEventListener('click', () => router.navigate('/admin'));
    el.querySelector('#au-out').onclick = async () => {
      await authStore.logout();
      router.navigate('/');
    };
    el.querySelector('#au-pw').onsubmit = async (e) => {
      e.preventDefault();
      const f = e.target;
      try {
        await authStore.changePassword(f.old.value, f.new.value);
        f.reset();
        toast('Đã đổi mật khẩu', 'success');
      } catch (ex) {
        toast(ex.message, 'error');
      }
    };
  },

  unmount() {},
};
