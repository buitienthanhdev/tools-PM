/* Trang quản trị (route /admin): duyệt tài khoản, cấp quyền công cụ, xem tình trạng hệ thống. */

import { authStore } from '../../stores/authStore.js';
import { eventBus } from '../../stores/eventBus.js';
import { pageHero, panelHead, svgIcon } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });

const MODULE_NAMES = {
  whisper: 'Whisper', voxcpm: 'VoxCPM', image: 'Nét Ảnh', genreport: 'Báo cáo', legal: 'Pháp luật', spacet: 'SpaceT', reviewingcv: 'Reviewing CV',
};
const STATUS = { pending: ['Chờ duyệt', 'warn'], active: ['Hoạt động', 'ok'], disabled: ['Đã khoá', 'bad'] };
const fmt = (t) => (t ? new Date(t * 1000).toLocaleString('vi-VN') : '—');

export const adminModule = {
  id: 'admin',
  name: 'Quản trị',
  route: '/admin',
  icon: '🛡️',
  category: 'Platform',
  description: 'Quản lý tài khoản và quyền truy cập',
  status: 'active',
  hidden: true,

  _timer: null,

  async render(el) {
    this.unmount();
    el.innerHTML = `
      ${pageHero(this, {
        title: 'Quản lý <span class="thin">tài khoản & quyền</span>',
        sub: 'Duyệt người đăng ký, cấp quyền từng công cụ, khoá hoặc xoá tài khoản và theo dõi tình trạng máy chủ.',
        word: 'Admin',
        meta: ['Chỉ quản trị viên'],
      })}
      <div class="mp-body">
        <div class="mp-panel">
          ${panelHead('01', 'Tình trạng', 'hệ thống', '<button class="btn btn-secondary btn-sm" id="ad-refresh-health">Làm mới</button>')}
          <div id="ad-health" class="ad-health"><span style="color:var(--text-dim)">Đang kiểm tra…</span></div>
        </div>
        <div class="mp-panel">
          ${panelHead('02', 'Tài khoản', 'người dùng')}
          <div id="ad-users" style="overflow-x:auto;"><span style="color:var(--text-dim)">Đang tải…</span></div>
        </div>
      </div>`;

    const $ = (s) => el.querySelector(s);

    const loadHealth = async () => {
      try {
        const d = await (await fetch('/api/health/tools')).json();
        const g = d.gpu;
        $('#ad-health').innerHTML =
          `<div class="ad-gpu">GPU: <b>${g.busy ? `đang chạy ${esc(g.owner)} (${g.running_seconds}s)` : 'rảnh'}</b>${g.waiting ? ` · ${g.waiting} tác vụ đang chờ` : ''}</div>` +
          Object.entries(d.tools).map(([k, v]) => `
            <div class="ad-tool"><span class="ad-dot ${v.ok ? 'ok' : 'bad'}"></span><b>${esc(MODULE_NAMES[k] || k)}</b><small>${esc(v.detail)}</small></div>`).join('');
      } catch (e) {
        $('#ad-health').textContent = 'Không đọc được tình trạng: ' + e.message;
      }
    };

    const loadUsers = async () => {
      try {
        const { users, modules } = await authStore.adminUsers();
        $('#ad-users').innerHTML = `
          <table class="mp-table">
            <thead><tr><th>Tài khoản</th><th>Trạng thái</th><th>Công cụ được dùng</th><th>Đăng nhập gần nhất</th><th style="width:260px">Thao tác</th></tr></thead>
            <tbody>${users.map((u) => {
              const [label, tone] = STATUS[u.status] || [u.status, 'muted'];
              const admin = u.role === 'admin';
              return `<tr data-email="${esc(u.email)}">
                <td><b>${esc(u.name || '')}</b><br><small style="color:var(--text-dim)">${esc(u.email)}${admin ? ' · admin' : ''}</small></td>
                <td><span class="badge-tag ${tone === 'ok' ? 'badge-active' : ''}" style="${tone === 'warn' ? 'color:#fbbf24;border-color:rgba(251,191,36,.35)' : tone === 'bad' ? 'color:#f87171;border-color:rgba(248,113,113,.35)' : ''}">${label}</span></td>
                <td>${admin ? '<small style="color:var(--text-dim)">Tất cả</small>' : `<div class="ad-mods">${modules.map((m) => `<label class="ad-chip"><input type="checkbox" data-mod="${m}" ${u.modules.includes(m) ? 'checked' : ''}/><span>${esc(MODULE_NAMES[m] || m)}</span></label>`).join('')}</div>`}</td>
                <td><small>${fmt(u.last_login)}</small></td>
                <td>${admin ? '' : `<div class="ad-actions">
                  ${u.status !== 'active' ? '<button class="btn btn-primary btn-sm" data-act="approve">Duyệt</button>' : '<button class="btn btn-secondary btn-sm" data-act="disable">Khoá</button>'}
                  <button class="btn btn-secondary btn-sm" data-act="save">Lưu quyền</button>
                  <button class="btn btn-secondary btn-sm" data-act="reset">Đặt lại MK</button>
                  <button class="btn btn-secondary btn-sm" data-act="delete" style="color:#f87171">Xoá</button></div>`}</td>
              </tr>`;
            }).join('')}</tbody></table>`;
      } catch (e) {
        $('#ad-users').innerHTML = `<div class="mp-error">${esc(e.message)}</div>`;
      }
    };

    $('#ad-users').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-act]');
      if (!btn) return;
      const tr = btn.closest('tr');
      const email = tr.dataset.email;
      const mods = [...tr.querySelectorAll('[data-mod]:checked')].map((c) => c.dataset.mod);
      try {
        if (btn.dataset.act === 'approve') {
          await authStore.adminUpdate(email, { status: 'active', modules: mods });
          toast(mods.length ? 'Đã duyệt tài khoản' : 'Đã duyệt, nhưng chưa tích công cụ nào', mods.length ? 'success' : 'info');
        } else if (btn.dataset.act === 'disable') {
          await authStore.adminUpdate(email, { status: 'disabled' });
          toast('Đã khoá tài khoản', 'success');
        } else if (btn.dataset.act === 'save') {
          await authStore.adminUpdate(email, { modules: mods });
          toast('Đã lưu quyền', 'success');
        } else if (btn.dataset.act === 'reset') {
          const pw = prompt(`Mật khẩu mới cho ${email} (tối thiểu 8 ký tự):`);
          if (!pw) return;
          await authStore.adminUpdate(email, { new_password: pw });
          toast('Đã đặt lại mật khẩu', 'success');
        } else if (btn.dataset.act === 'delete') {
          if (!confirm(`Xoá hẳn tài khoản ${email}?`)) return;
          await authStore.adminDelete(email);
          toast('Đã xoá tài khoản', 'success');
        }
        loadUsers();
      } catch (ex) {
        toast(ex.message, 'error');
      }
    });
    $('#ad-refresh-health').onclick = loadHealth;

    loadHealth();
    loadUsers();
    this._timer = setInterval(() => { if (el.isConnected) loadHealth(); }, 15000);
  },

  unmount() {
    clearInterval(this._timer);
    this._timer = null;
  },
};
