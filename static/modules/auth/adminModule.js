/* Trang quản trị (route /admin): dashboard theo dõi toàn Hub (truy cập, người dùng, công cụ, bảo mật, lỗi, nhật ký,
   máy chủ) + duyệt tài khoản và cấp quyền công cụ. Số liệu lấy từ /api/admin/analytics/* (chỉ admin). */

import { authStore } from '../../stores/authStore.js';
import { eventBus } from '../../stores/eventBus.js';
import { pageHero } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });

const MODULE_NAMES = {
  whisper: 'Whisper', voxcpm: 'VoxCPM', image: 'Nét Ảnh', genreport: 'Báo cáo', legal: 'Pháp luật', spacet: 'SpaceT', reviewingcv: 'Reviewing CV',
  accounting: 'Kế toán AI', auth: 'Đăng nhập / tài khoản', admin: 'Quản trị', jobs: 'Tác vụ nền', export: 'Xuất file', uploads: 'File tải lên',
  catalog: 'Trang chủ', page: 'Trang khác', other: 'Khác',
};
const EVENT_NAMES = {
  login_ok: 'Đăng nhập', login_fail: 'Đăng nhập sai', login_blocked: 'Đăng nhập bị chặn (tài khoản khoá)', logout: 'Đăng xuất',
  register: 'Đăng ký', password_change: 'Đổi mật khẩu', admin_update: 'Admin sửa tài khoản', admin_delete: 'Admin xoá tài khoản',
  admin_export: 'Admin xuất nhật ký',
};
const STATUS = { pending: ['Chờ duyệt', 'warn'], active: ['Hoạt động', 'ok'], disabled: ['Đã khoá', 'bad'] };
const TABS = [
  ['overview', 'Tổng quan'], ['live', 'Trực tiếp'], ['users', 'Người dùng'], ['tools', 'Công cụ & API'],
  ['security', 'Bảo mật'], ['errors', 'Lỗi'], ['log', 'Nhật ký'], ['system', 'Hệ thống'],
];
const RANGES = [['1h', '1 giờ'], ['24h', '24 giờ'], ['7d', '7 ngày'], ['30d', '30 ngày'], ['90d', '90 ngày']];

const nf = new Intl.NumberFormat('vi-VN');
const n = (v) => (v == null ? '—' : nf.format(Math.round(v)));
const pct = (v) => (v == null ? '—' : `${(v * 100).toLocaleString('vi-VN', { maximumFractionDigits: 2 })}%`);
const ms = (v) => (v == null ? '—' : v >= 1000 ? `${(v / 1000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} s` : `${Math.round(v)} ms`);
const dur = (s) => (s == null ? '—' : s < 60 ? `${Math.round(s)} giây` : s < 3600 ? `${Math.floor(s / 60)} phút ${Math.round(s % 60)} giây` : `${Math.floor(s / 3600)} giờ ${Math.round((s % 3600) / 60)} phút`);
const bytes = (b) => (b == null ? '—' : b < 1024 ** 2 ? `${(b / 1024).toFixed(0)} KB` : b < 1024 ** 3 ? `${(b / 1024 ** 2).toFixed(1)} MB` : `${(b / 1024 ** 3).toFixed(1)} GB`);
const time = (t) => (t ? new Date(t * 1000).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—');
const ago = (t) => { if (!t) return '—'; const s = Date.now() / 1000 - t; return s < 60 ? `${Math.round(s)} giây trước` : s < 3600 ? `${Math.round(s / 60)} phút trước` : s < 86400 ? `${Math.round(s / 3600)} giờ trước` : `${Math.round(s / 86400)} ngày trước`; };
const mod = (m) => MODULE_NAMES[m] || m || '—';
const pill = (txt, tone = '') => `<span class="adm-pill ${tone}">${esc(txt)}</span>`;
const statusPill = (s) => pill(s, s >= 500 ? 'bad' : s >= 400 ? 'warn' : 'ok');

async function get(url) {
  const r = await fetch(url, { credentials: 'same-origin' });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `Lỗi ${r.status}`);
  return d;
}

// ── Biểu đồ SVG (đường / cột chồng) có tooltip ─────────────────
function niceMax(v) {
  // 4 khoảng chia bằng số tròn (1, 2, 5 × 10^k) — số đếm nên không có mốc lẻ
  const raw = Math.max(1, v / 4);
  const p = 10 ** Math.floor(Math.log10(raw));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p * 4;
}

function chart(el, data, series, { type = 'line', height = 220 } = {}) {
  const draw = () => {
    const W = Math.max(280, el.clientWidth);
    const H = height;
    const pad = { l: 44, r: 10, t: 10, b: 26 };
    const iw = W - pad.l - pad.r;
    const ih = H - pad.t - pad.b;
    const total = (d) => series.reduce((s, x) => s + (d[x.key] || 0), 0);
    const max = niceMax(Math.max(1, ...data.map((d) => (type === 'stack' ? total(d) : Math.max(...series.map((x) => d[x.key] || 0))))));
    const y = (v) => pad.t + ih - (v / max) * ih;
    const step = iw / Math.max(1, data.length);
    const x = (i) => pad.l + (type === 'line' ? (data.length === 1 ? iw / 2 : (i / (data.length - 1)) * iw) : i * step + step / 2);
    let svg = '';
    for (let k = 0; k <= 4; k++) {
      const v = (max / 4) * k;
      svg += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(${k ? '--grid' : '--axis'})" stroke-width="1"/>`;
      svg += `<text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end">${n(v)}</text>`;
    }
    const every = Math.ceil(data.length / Math.max(2, Math.floor(iw / 70)));
    data.forEach((d, i) => { if (i % every === 0) svg += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${esc(d.t)}</text>`; });
    if (type === 'line') {
      series.forEach((s) => {
        const pts = data.map((d, i) => `${x(i)},${y(d[s.key] || 0)}`).join(' ');
        svg += `<polyline points="${pts}" fill="none" stroke="var(${s.color})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
      });
    } else {
      const bw = Math.max(2, step - 2); // khe 2px giữa các cột
      data.forEach((d, i) => {
        let base = 0;
        series.forEach((s, si) => {
          const v = d[s.key] || 0;
          if (!v) return;
          const top = y(base + v);
          const bot = y(base) - (base ? 1 : 0); // khe 1px giữa các đoạn chồng
          const h = Math.max(1, bot - top);
          const x0 = x(i) - bw / 2;
          const isTop = series.slice(si + 1).every((t) => !(d[t.key] || 0));
          const r = isTop ? Math.min(4, bw / 2, h) : 0;
          svg += `<path d="M${x0},${top + h} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x0 + bw - r} Q${x0 + bw},${top} ${x0 + bw},${top + r} V${top + h} Z" fill="var(${s.color})"/>`;
          base += v;
        });
      });
    }
    svg += `<line class="xh" x1="0" x2="0" y1="${pad.t}" y2="${pad.t + ih}" stroke="var(--text-dim)" stroke-dasharray="3 3" visibility="hidden"/>`;
    svg += `<rect class="hit" x="${pad.l}" y="${pad.t}" width="${iw}" height="${ih}" fill="transparent"/>`;
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img">${svg}</svg><div class="adm-tip"></div>`;
    const tip = el.querySelector('.adm-tip');
    const xh = el.querySelector('.xh');
    const hit = el.querySelector('.hit');
    hit.addEventListener('mousemove', (e) => {
      const rect = el.querySelector('svg').getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * W;
      const i = type === 'line' ? Math.round(((px - pad.l) / iw) * (data.length - 1)) : Math.floor((px - pad.l) / step);
      const d = data[Math.max(0, Math.min(data.length - 1, i))];
      if (!d) return;
      const cx = x(data.indexOf(d));
      xh.setAttribute('x1', cx); xh.setAttribute('x2', cx); xh.setAttribute('visibility', 'visible');
      tip.innerHTML = `<b>${esc(d.t)}</b>${series.map((s) => `<div class="row"><span><i style="background:var(${s.color})"></i>${esc(s.label)}</span><span>${n(d[s.key] || 0)}</span></div>`).join('')}`;
      tip.style.display = 'block';
      const left = (cx / W) * rect.width;
      tip.style.left = `${Math.min(rect.width - tip.offsetWidth, Math.max(0, left + 12))}px`;
      tip.style.top = '8px';
    });
    hit.addEventListener('mouseleave', () => { tip.style.display = 'none'; xh.setAttribute('visibility', 'hidden'); });
  };
  draw();
  const ro = new ResizeObserver(() => draw());
  ro.observe(el);
  return ro;
}

const legend = (series) => `<div class="adm-legend">${series.map((s) => `<span><i style="background:var(${s.color})"></i>${esc(s.label)}</span>`).join('')}</div>`;

function barList(rows, label, value, { fmt = n, sub = null, click = null } = {}) {
  if (!rows?.length) return '<div class="adm-empty">Chưa có dữ liệu</div>';
  const max = Math.max(1, ...rows.map((r) => r[value] || 0));
  return `<div class="adm-bars">${rows.map((r, i) => `<div class="r" ${click ? `data-${click}="${esc(r[click] ?? '')}" style="cursor:pointer"` : ''} title="${esc(label(r))}">
    <span class="k">${esc(label(r))}</span><span class="v">${fmt(r[value])}${sub ? ` · ${sub(r)}` : ''}</span>
    <div class="t"><div style="width:${((r[value] || 0) / max) * 100}%"></div></div></div>`).join('')}</div>`;
}

function table(cols, rows, { empty = 'Chưa có dữ liệu', rowAttr = null } = {}) {
  if (!rows?.length) return `<div class="adm-empty">${empty}</div>`;
  return `<div class="adm-table-wrap"><table class="adm-table"><thead><tr>${cols.map((c) => `<th class="${c.num ? 'num' : ''}">${esc(c.label)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr ${rowAttr ? rowAttr(r) : ''}>${cols.map((c) => `<td class="${c.num ? 'num' : ''} ${c.cls || ''}">${c.html ? c.html(r) : esc(c.get ? c.get(r) : r[c.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

const card = (title, sub, body, extra = '') => `<div class="adm-card" ${extra}><h3>${esc(title)}</h3>${sub ? `<div class="sub">${sub}</div>` : ''}${body}</div>`;

function kpi(label, value, cur, prev, goodWhenUp = true, hero = false) {
  let d = '<div class="d">&nbsp;</div>';
  if (prev != null && cur != null && typeof cur === 'number') {
    if (prev === 0 && cur === 0) d = '<div class="d">không đổi so với kỳ trước</div>';
    else if (prev === 0) d = `<div class="d ${goodWhenUp ? 'up-good' : 'up-bad'}">▲ mới (kỳ trước 0)</div>`;
    else {
      const ch = (cur - prev) / prev;
      const up = ch > 0;
      const cls = Math.abs(ch) < 0.005 ? '' : up === goodWhenUp ? (up ? 'up-good' : 'down-good') : (up ? 'up-bad' : 'down-bad');
      d = `<div class="d ${cls}">${up ? '▲' : ch < 0 ? '▼' : '•'} ${Math.abs(ch * 100).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}% so với kỳ trước</div>`;
    }
  }
  return `<div class="adm-kpi ${hero ? 'hero' : ''}"><div class="l">${label}</div><div class="v">${value}</div>${d}</div>`;
}

export const adminModule = {
  id: 'admin',
  name: 'Quản trị',
  route: '/admin',
  icon: '🛡️',
  category: 'Platform',
  description: 'Dashboard theo dõi, quản lý tài khoản và quyền truy cập',
  status: 'active',
  hidden: true,

  _timers: [],
  _observers: [],
  s: { tab: 'overview', range: '24h', user: null, log: { kind: 'requests', q: '', status: '' } },

  async render(el) {
    this.unmount();
    if (!document.querySelector('link[data-admin-css]')) {
      const l = document.createElement('link');
      l.rel = 'stylesheet'; l.href = '/styles/admin.css?v=3'; l.dataset.adminCss = '1';
      document.head.appendChild(l);
    }
    try { const t = sessionStorage.getItem('adm_tab'); if (t) this.s.tab = t; } catch { /* bỏ qua */ }
    el.innerHTML = `
      ${pageHero(this, {
        title: 'Bảng điều khiển <span class="thin">quản trị</span>',
        sub: 'Theo dõi truy cập, người dùng, công cụ, bảo mật, lỗi và máy chủ của toàn bộ Hub; duyệt tài khoản và cấp quyền.',
        word: 'Admin',
        meta: ['Chỉ quản trị viên', 'Dữ liệu giữ 90 ngày'],
      })}
      <div class="mp-body adm">
        <div class="adm-bar">
          <div class="adm-tabs" id="adm-tabs">${TABS.map(([k, v]) => `<button data-tab="${k}">${k === 'live' ? '<span class="adm-live-dot"></span>' : ''}${v}${k === 'live' ? ' <span class="n" id="adm-online">…</span>' : ''}</button>`).join('')}</div>
          <div class="adm-range" id="adm-range">${RANGES.map(([k, v]) => `<button data-r="${k}">${v}</button>`).join('')}</div>
        </div>
        <div id="adm-view"></div>
      </div>`;
    this.el = el;
    el.querySelector('#adm-tabs').onclick = (e) => { const b = e.target.closest('[data-tab]'); if (b) { this.s.user = null; this.show(b.dataset.tab); } };
    el.querySelector('#adm-range').onclick = (e) => { const b = e.target.closest('[data-r]'); if (b) { this.s.range = b.dataset.r; this.show(this.s.tab); } };
    this.show(this.s.tab);
    const tickOnline = () => get('/api/admin/analytics/live').then((d) => { const o = el.querySelector('#adm-online'); if (o) o.textContent = d.online.length; }).catch(() => {});
    tickOnline();
    this._timers.push(setInterval(() => { if (el.isConnected) tickOnline(); }, 20000));
  },

  async show(tab) {
    this.s.tab = tab;
    try { sessionStorage.setItem('adm_tab', tab); } catch { /* bỏ qua */ }
    this._observers.forEach((o) => o.disconnect());
    this._observers = [];
    clearInterval(this._viewTimer);
    this.el.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
    this.el.querySelectorAll('[data-r]').forEach((b) => b.classList.toggle('on', b.dataset.r === this.s.range));
    this.el.querySelector('#adm-range').style.visibility = ['live', 'system'].includes(tab) ? 'hidden' : 'visible';
    const v = this.el.querySelector('#adm-view');
    v.innerHTML = '<div class="adm-empty">Đang tải…</div>';
    try {
      if (this.s.user && tab === 'users') await this.viewUser(v, this.s.user);
      else await this[`view_${tab}`](v);
    } catch (e) {
      v.innerHTML = `<div class="mp-error">${esc(e.message)}</div>`;
    }
  },

  q() { return `range=${this.s.range}`; },

  // ── Tổng quan ──
  async view_overview(v) {
    const [o, t] = await Promise.all([get(`/api/admin/analytics/overview?${this.q()}`), get(`/api/admin/analytics/top?${this.q()}`)]);
    const k = o.kpis;
    const p = o.previous;
    v.innerHTML = `<div class="adm-grid">
      <div class="adm-kpis">
        ${kpi('<span class="adm-live-dot"></span> Đang online', n(o.online), null, null, true, true)}
        ${kpi('Khách truy cập', n(k.visitors), k.visitors, p.visitors)}
        ${kpi('Lượt xem trang', n(k.pageviews), k.pageviews, p.pageviews)}
        ${kpi('Người dùng đăng nhập', n(k.users), k.users, p.users)}
        ${kpi('Lượt dùng công cụ', n(k.actions), k.actions, p.actions)}
        ${kpi('Thời gian xem TB / trang', dur(k.avg_duration_s), k.avg_duration_s, p.avg_duration_s)}
        ${kpi('Yêu cầu API', n(k.requests), k.requests, p.requests)}
        ${kpi('Lỗi máy chủ (5xx)', `${n(k.errors_5xx)} <small style="font-size:13px;color:var(--text-dim)">${pct(k.error_rate)}</small>`, k.errors_5xx, p.errors_5xx, false)}
        ${kpi('Phản hồi P95', ms(k.p95_ms), k.p95_ms, p.p95_ms, false)}
        ${kpi('Đăng nhập sai', n(k.login_fails), k.login_fails, p.login_fails, false)}
        ${kpi('Đăng ký mới', n(k.registrations), k.registrations, p.registrations)}
        ${kpi('Yêu cầu từ bot', n(k.bot_requests), k.bot_requests, p.bot_requests, false)}
      </div>
      <div class="adm-2">
        ${card('Lượt xem trang và khách truy cập', 'Theo thời gian · rê chuột để xem từng mốc', `${legend(S_PV)}<div class="adm-chart" id="c-pv"></div>`)}
        ${card('Yêu cầu API', 'Thành công / lỗi phía người dùng (4xx) / lỗi máy chủ (5xx) — không tính bot', `${legend(S_REQ)}<div class="adm-chart" id="c-req"></div>`)}
      </div>
      <div class="adm-3">
        ${card('Trang được xem nhiều', 'lượt xem · khách', barList(t.pages.slice(0, 10), (r) => r.path, 'views', { sub: (r) => `${n(r.visitors)} khách` }))}
        ${card('Công cụ được dùng', 'thao tác (POST/PUT/DELETE) · người dùng', barList(t.modules.filter((m) => m.actions).slice(0, 10), (r) => mod(r.module), 'actions', { sub: (r) => `${n(r.users)} người` }))}
        ${card('Người dùng tích cực', 'yêu cầu · bấm để xem hành trình', barList(t.users.slice(0, 10), (r) => r.user, 'requests', { click: 'user' }))}
      </div>
      <div class="adm-3">
        ${card('Quốc gia', 'theo khách (header Cloudflare)', barList(t.countries, (r) => r.k, 'visitors'))}
        ${card('Trình duyệt', 'theo khách', barList(t.browsers, (r) => r.k, 'visitors'))}
        ${card('Thiết bị / hệ điều hành', 'theo khách', barList([...t.devices, ...t.os.map((x) => ({ ...x, k: `HĐH: ${x.k}` }))], (r) => r.k, 'visitors'))}
      </div>
      <div class="adm-2">
        ${card('Nguồn truy cập', 'trang giới thiệu bên ngoài (referrer)', barList(t.referrers, (r) => r.k, 'visitors'))}
        ${card('Độ phân giải màn hình', 'theo khách', barList(t.screens, (r) => r.k, 'visitors'))}
      </div></div>`;
    const data = o.series.map((d) => ({ ...d, ok: d.requests - d.e4 - d.e5 }));
    this._observers.push(chart(v.querySelector('#c-pv'), data, S_PV, { type: 'line' }));
    this._observers.push(chart(v.querySelector('#c-req'), data, S_REQ, { type: 'stack' }));
    v.querySelectorAll('[data-user]').forEach((b) => (b.onclick = () => this.openUser(b.dataset.user)));
  },

  // ── Trực tiếp ──
  async view_live(v) {
    const load = async () => {
      const d = await get('/api/admin/analytics/live');
      const o = this.el.querySelector('#adm-online');
      if (o) o.textContent = d.online.length;
      v.innerHTML = `<div class="adm-grid">
        ${card(`Đang online: ${d.online.length}`, 'hoạt động trong 5 phút gần nhất · tự cập nhật 10 giây', table([
          { label: 'Người dùng', html: (r) => (r.user ? `<a href="#" data-user="${esc(r.user)}">${esc(r.name || r.user)}</a><br><small>${esc(r.user)}</small>` : `<span style="color:var(--text-dim)">Khách (chưa đăng nhập)</span><br><small class="mono">${esc((r.vid || '').slice(0, 8))}</small>`) },
          { label: 'Đang ở trang', html: (r) => esc(r.path || '—') + (r.last_api ? `<br><small style="color:var(--text-dim)">API: ${esc(r.last_api)}</small>` : '') },
          { label: 'IP', cls: 'mono ip', get: (r) => r.ip },
          { label: 'Quốc gia', get: (r) => r.country || '—' },
          { label: 'Thiết bị', get: (r) => [r.browser, r.device].filter(Boolean).join(' · ') },
          { label: 'Lần cuối', get: (r) => ago(r.ts) },
        ], d.online, { empty: 'Không có ai online' }))}
        ${card('Lượt xem trang mới nhất', '30 lượt gần nhất', `<div class="adm-scroll">${table([
          { label: 'Thời điểm', get: (r) => time(r.ts) }, { label: 'Người dùng', html: (r) => (r.user ? `<a href="#" data-user="${esc(r.user)}">${esc(r.user)}</a>` : '<span style="color:var(--text-dim)">khách</span>') },
          { label: 'Trang', get: (r) => r.path }, { label: 'IP', cls: 'mono ip', get: (r) => r.ip }, { label: 'Quốc gia', get: (r) => r.country || '—' },
          { label: 'Thiết bị', get: (r) => `${r.browser} · ${r.device}` },
        ], d.recent_pageviews)}</div>`)}</div>`;
      v.querySelectorAll('[data-user]').forEach((b) => (b.onclick = (e) => { e.preventDefault(); this.openUser(b.dataset.user); }));
    };
    await load();
    this._viewTimer = setInterval(() => { if (this.el.isConnected && this.s.tab === 'live') load().catch(() => {}); }, 10000);
  },

  // ── Người dùng: tài khoản + hoạt động ──
  openUser(email) { this.s.user = email; this.show('users'); },

  async view_users(v) {
    const [{ users, modules }, t] = await Promise.all([authStore.adminUsers(), get(`/api/admin/analytics/top?${this.q()}`)]);
    const act = Object.fromEntries(t.users.map((u) => [u.user, u]));
    const pending = users.filter((u) => u.status === 'pending').length;
    v.innerHTML = `<div class="adm-grid">
      <div class="adm-kpis">
        ${kpi('Tổng tài khoản', n(users.length))}
        ${kpi('Chờ duyệt', n(pending), null, null, true, pending > 0)}
        ${kpi('Đang hoạt động', n(users.filter((u) => u.status === 'active').length))}
        ${kpi('Đã khoá', n(users.filter((u) => u.status === 'disabled').length))}
        ${kpi('Có hoạt động trong kỳ', n(t.users.length))}
      </div>
      ${card('Tài khoản & quyền công cụ', 'Bấm tên để xem toàn bộ hành trình của người dùng (trang đã xem, thao tác, thiết bị, IP, lỗi gặp phải)', `<div class="adm-table-wrap" id="adm-users"><table class="adm-table">
        <thead><tr><th>Tài khoản</th><th>Trạng thái</th><th>Công cụ được dùng</th><th class="num">Yêu cầu</th><th class="num">Thao tác</th><th class="num">Lượt xem</th><th class="num">Thời gian xem</th><th>Hoạt động cuối</th><th>Đăng nhập cuối</th><th style="min-width:240px">Thao tác quản trị</th></tr></thead>
        <tbody>${users.map((u) => {
          const [label, tone] = STATUS[u.status] || [u.status, ''];
          const admin = u.role === 'admin';
          const a = act[u.email] || {};
          return `<tr data-email="${esc(u.email)}">
            <td><a href="#" data-open="${esc(u.email)}"><b>${esc(u.name || '')}</b></a><br><small style="color:var(--text-dim)">${esc(u.email)}${admin ? ' · admin' : ''}</small></td>
            <td>${pill(label, tone)}</td>
            <td>${admin ? '<small style="color:var(--text-dim)">Tất cả</small>' : `<div class="ad-mods">${modules.map((m) => `<label class="ad-chip"><input type="checkbox" data-mod="${m}" ${u.modules.includes(m) ? 'checked' : ''}/><span>${esc(MODULE_NAMES[m] || m)}</span></label>`).join('')}</div>`}</td>
            <td class="num">${n(a.requests || 0)}</td><td class="num">${n(a.actions || 0)}</td><td class="num">${n(a.pageviews || 0)}</td>
            <td class="num">${a.time_s ? dur(a.time_s) : '—'}</td><td>${a.last_seen ? ago(a.last_seen) : '—'}</td><td><small>${time(u.last_login)}</small></td>
            <td>${admin ? '' : `<div class="ad-actions">
              ${u.status !== 'active' ? '<button class="btn btn-primary btn-sm" data-act="approve">Duyệt</button>' : '<button class="btn btn-secondary btn-sm" data-act="disable">Khoá</button>'}
              <button class="btn btn-secondary btn-sm" data-act="save">Lưu quyền</button>
              <button class="btn btn-secondary btn-sm" data-act="reset">Đặt lại MK</button>
              <button class="btn btn-secondary btn-sm" data-act="delete" style="color:#f87171">Xoá</button></div>`}</td></tr>`;
        }).join('')}</tbody></table></div>`)}
      ${card('Người dùng đã xoá / không còn tài khoản nhưng có hoạt động', '', table([
        { label: 'Email', html: (r) => `<a href="#" data-open="${esc(r.user)}">${esc(r.user)}</a>` }, { label: 'Yêu cầu', num: true, get: (r) => n(r.requests) },
        { label: 'Hoạt động cuối', get: (r) => ago(r.last_seen) }], t.users.filter((x) => !users.some((u) => u.email === x.user)), { empty: 'Không có' }))}
    </div>`;
    v.querySelectorAll('[data-open]').forEach((a) => (a.onclick = (e) => { e.preventDefault(); this.openUser(a.dataset.open); }));
    v.querySelector('#adm-users').addEventListener('click', async (e) => {
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
        this.show('users');
      } catch (ex) {
        toast(ex.message, 'error');
      }
    });
  },

  async viewUser(v, email) {
    const d = await get(`/api/admin/analytics/user?email=${encodeURIComponent(email)}&${this.q()}`);
    const p = d.profile;
    const s = d.stats;
    const TYPE = { page: ['Xem trang', 'info'], action: ['Thao tác', 'ok'], fail: ['Bị lỗi', 'bad'], event: ['Sự kiện', 'warn'], error: ['Lỗi', 'bad'] };
    v.innerHTML = `<button class="adm-back" id="adm-back">← Tất cả người dùng</button><div class="adm-grid">
      <div class="adm-card"><h3>${esc(p.name || p.email)} ${p.deleted ? pill('đã xoá', 'bad') : pill((STATUS[p.status] || [p.status])[0], (STATUS[p.status] || [])[1])}</h3>
        <dl class="adm-kv" style="margin-top:8px"><dt>Email</dt><dd>${esc(p.email)}</dd><dt>Vai trò</dt><dd>${esc(p.role || '—')}</dd>
        <dt>Công cụ được cấp</dt><dd>${(p.modules || []).map((m) => esc(mod(m))).join(', ') || '—'}</dd>
        <dt>Tạo lúc</dt><dd>${time(p.created)}</dd><dt>Đăng nhập cuối</dt><dd>${time(p.last_login)}</dd>
        <dt>Lần đầu / cuối trong kỳ</dt><dd>${time(s.first)} → ${time(s.last)}</dd></dl></div>
      <div class="adm-kpis">
        ${kpi('Lượt xem trang', n(s.pageviews))}${kpi('Thời gian xem', dur(s.time_s))}${kpi('Yêu cầu API', n(s.requests))}
        ${kpi('Thao tác', n(s.actions))}${kpi('Yêu cầu lỗi', n(s.errors))}${kpi('Số IP', n(s.ips))}${kpi('Số trình duyệt/thiết bị', n(s.devices))}
        ${kpi('Phản hồi TB', ms(s.avg_ms))}
      </div>
      <div class="adm-2">
        ${card('Công cụ đã dùng', 'thao tác · yêu cầu', barList(d.tools, (r) => mod(r.module), 'requests', { sub: (r) => `${n(r.actions)} thao tác` }))}
        ${card('Thiết bị và địa chỉ IP', '', table([{ label: 'IP', cls: 'mono ip', get: (r) => r.ip }, { label: 'Quốc gia', get: (r) => r.country || '—' },
          { label: 'Thiết bị', get: (r) => `${r.browser} · ${r.os} · ${r.device}` }, { label: 'Yêu cầu', num: true, get: (r) => n(r.n) },
          { label: 'Từ', get: (r) => time(r.first) }, { label: 'Đến', get: (r) => time(r.last) }], d.places))}
      </div>
      ${card(`Hành trình (${n(d.timeline.length)} sự kiện, mới nhất trước)`, 'Trang đã xem, mọi thao tác ghi dữ liệu, yêu cầu lỗi, sự kiện tài khoản và lỗi gặp phải',
        `<div class="adm-filters"><select id="tl-type"><option value="">Tất cả loại</option>${Object.entries(TYPE).map(([k, [l]]) => `<option value="${k}">${l}</option>`).join('')}</select><input id="tl-q" placeholder="Lọc theo nội dung…"/></div>
         <div class="adm-scroll"><div class="adm-tl" id="adm-tl"></div></div>`)}
    </div>`;
    const renderTl = () => {
      const ty = v.querySelector('#tl-type').value;
      const q = v.querySelector('#tl-q').value.toLowerCase();
      const rows = d.timeline.filter((e) => (!ty || e.type === ty) && (!q || `${e.what} ${e.info}`.toLowerCase().includes(q)));
      v.querySelector('#adm-tl').innerHTML = rows.length ? rows.map((e) => `<div class="e"><time>${time(e.ts)}</time><span>${pill(...(TYPE[e.type] || [e.type]))}</span>
        <div><div class="w">${esc(e.type === 'event' ? (EVENT_NAMES[e.what] || e.what) : e.what)}${e.module ? ` <small style="color:var(--text-dim)">(${esc(mod(e.module))})</small>` : ''}</div>
        <div class="i">${esc([e.info, e.ip && `IP ${e.ip}`, e.device, e.actor && e.actor !== email && `bởi ${e.actor}`].filter(Boolean).join(' · '))}</div></div></div>`).join('')
        : '<div class="adm-empty">Không có sự kiện</div>';
    };
    v.querySelector('#tl-type').onchange = renderTl;
    v.querySelector('#tl-q').oninput = renderTl;
    renderTl();
    v.querySelector('#adm-back').onclick = () => { this.s.user = null; this.show('users'); };
  },

  // ── Công cụ & API ──
  async view_tools(v) {
    const t = await get(`/api/admin/analytics/top?${this.q()}`);
    v.innerHTML = `<div class="adm-grid">
      ${card('Theo công cụ', 'thao tác = yêu cầu ghi (POST/PUT/DELETE); lỗi 4xx = phía người dùng, 5xx = máy chủ', table([
        { label: 'Công cụ', get: (r) => mod(r.module) }, { label: 'Thao tác', num: true, get: (r) => n(r.actions) }, { label: 'Yêu cầu', num: true, get: (r) => n(r.requests) },
        { label: 'Người dùng', num: true, get: (r) => n(r.users) }, { label: 'Lỗi 4xx', num: true, get: (r) => n(r.e4) },
        { label: 'Lỗi 5xx', num: true, html: (r) => (r.e5 ? pill(n(r.e5), 'bad') : '0') }, { label: 'Phản hồi TB', num: true, get: (r) => ms(r.avg_ms) }], t.modules))}
      ${card('Endpoint', '60 endpoint nhiều yêu cầu nhất (mã định danh trong đường dẫn được gom thành :id)', `<div class="adm-scroll">${table([
        { label: 'Phương thức', get: (r) => r.method }, { label: 'Đường dẫn', cls: 'mono', get: (r) => r.route }, { label: 'Công cụ', get: (r) => mod(r.module) },
        { label: 'Số lần', num: true, get: (r) => n(r.n) }, { label: 'TB', num: true, get: (r) => ms(r.avg_ms) }, { label: 'Lâu nhất', num: true, get: (r) => ms(r.max_ms) },
        { label: '4xx', num: true, get: (r) => n(r.e4) }, { label: '5xx', num: true, html: (r) => (r.e5 ? pill(n(r.e5), 'bad') : '0') }], t.endpoints)}</div>`)}
      ${card('Endpoint chậm nhất', 'trung bình, tối thiểu 3 lần gọi', table([
        { label: 'Đường dẫn', cls: 'mono', get: (r) => `${r.method} ${r.route}` }, { label: 'TB', num: true, get: (r) => ms(r.avg_ms) },
        { label: 'Lâu nhất', num: true, get: (r) => ms(r.max_ms) }, { label: 'Số lần', num: true, get: (r) => n(r.n) }], t.slow))}
    </div>`;
  },

  // ── Bảo mật ──
  async view_security(v) {
    const d = await get(`/api/admin/analytics/security?${this.q()}`);
    const ipLink = (ip) => `<a href="#" data-ip="${esc(ip)}" class="mono">${esc(ip)}</a>`;
    v.innerHTML = `<div class="adm-grid">
      <div class="adm-2">
        ${card('Đăng nhập sai theo IP', '5 lần sai liên tiếp → khoá 5 phút', table([{ label: 'IP', html: (r) => ipLink(r.ip) }, { label: 'Quốc gia', get: (r) => r.country || '—' },
          { label: 'Lần sai', num: true, html: (r) => pill(n(r.n), r.n >= 5 ? 'bad' : 'warn') }, { label: 'Số email thử', num: true, get: (r) => n(r.emails) }, { label: 'Lần cuối', get: (r) => ago(r.last) }], d.login_fail_by_ip, { empty: 'Không có lần đăng nhập sai' }))}
        ${card('Đăng nhập sai theo email', '', table([{ label: 'Email', get: (r) => r.email }, { label: 'Lần sai', num: true, get: (r) => n(r.n) },
          { label: 'Số IP', num: true, get: (r) => n(r.ips) }, { label: 'Lần cuối', get: (r) => ago(r.last) }], d.login_fail_by_email, { empty: 'Không có' }))}
      </div>
      <div class="adm-2">
        ${card('Bị từ chối (401/403/429)', 'chưa đăng nhập, không có quyền, vượt giới hạn tốc độ', table([{ label: 'IP', html: (r) => ipLink(r.ip) }, { label: 'Mã', html: (r) => statusPill(r.status) },
          { label: 'Số lần', num: true, get: (r) => n(r.n) }, { label: 'Đường dẫn', cls: 'clip', get: (r) => r.routes }, { label: 'Lần cuối', get: (r) => ago(r.last) }], d.denied, { empty: 'Không có' }))}
        ${card('Dò đường dẫn / quét lỗ hổng', 'đường dẫn không tồn tại (404) hoặc mẫu quen thuộc của máy quét (.php, .env, wp-admin…)', table([{ label: 'IP', html: (r) => ipLink(r.ip) }, { label: 'Quốc gia', get: (r) => r.country || '—' },
          { label: 'Số lần', num: true, get: (r) => n(r.n) }, { label: 'Đường dẫn', cls: 'clip mono', get: (r) => r.paths }, { label: 'Lần cuối', get: (r) => ago(r.last) }], d.scans_404, { empty: 'Không có' }))}
      </div>
      <div class="adm-2">
        ${card('Bot & công cụ tự động', 'nhận diện qua User-Agent', table([{ label: 'Bot', get: (r) => r.browser }, { label: 'IP', html: (r) => ipLink(r.ip) },
          { label: 'Yêu cầu', num: true, get: (r) => n(r.n) }, { label: 'Lần cuối', get: (r) => ago(r.last) }], d.bots, { empty: 'Không có' }))}
        ${card('Người dùng đăng nhập từ IP mới', 'IP chưa từng thấy với tài khoản này trong 90 ngày trước kỳ', table([{ label: 'Người dùng', html: (r) => `<a href="#" data-user="${esc(r.user)}">${esc(r.user)}</a>` },
          { label: 'IP', html: (r) => ipLink(r.ip) }, { label: 'Quốc gia', get: (r) => r.country || '—' }, { label: 'Lần đầu', get: (r) => time(r.first) }], d.new_user_ips, { empty: 'Không có' }))}
      </div>
      ${card('Sự kiện tài khoản & quản trị', 'đăng ký, đăng nhập sai/bị chặn, đổi mật khẩu, admin sửa/xoá tài khoản, xuất nhật ký', `<div class="adm-scroll">${table([
        { label: 'Thời điểm', get: (r) => time(r.ts) }, { label: 'Sự kiện', html: (r) => pill(EVENT_NAMES[r.kind] || r.kind, r.kind.includes('fail') || r.kind.includes('delete') || r.kind.includes('blocked') ? 'bad' : r.kind.startsWith('admin') ? 'warn' : 'info') },
        { label: 'Tài khoản', get: (r) => r.user || '—' }, { label: 'Người thực hiện', get: (r) => r.actor || '—' }, { label: 'IP', html: (r) => (r.ip ? ipLink(r.ip) : '—') },
        { label: 'Chi tiết', cls: 'clip mono', get: (r) => r.detail || '' }], d.events, { empty: 'Không có sự kiện' })}</div>`)}
    </div>`;
    v.querySelectorAll('[data-ip]').forEach((a) => (a.onclick = (e) => { e.preventDefault(); this.s.log = { kind: 'requests', q: a.dataset.ip, status: '' }; this.show('log'); }));
    v.querySelectorAll('[data-user]').forEach((a) => (a.onclick = (e) => { e.preventDefault(); this.openUser(a.dataset.user); }));
  },

  // ── Lỗi ──
  async view_errors(v) {
    const d = await get(`/api/admin/analytics/errors?${this.q()}`);
    v.innerHTML = `<div class="adm-grid">
      ${card('Lỗi được gom nhóm', 'máy chủ (Python) và trình duyệt (JavaScript); bấm để xem chi tiết lần gần nhất', d.groups.length ? `<div class="adm-scroll">${d.groups.map((g) => `
        <div style="padding:10px 0;border-bottom:1px solid var(--border-color)">
          <div>${pill(g.source === 'server' ? 'Máy chủ' : 'Trình duyệt', g.source === 'server' ? 'bad' : 'warn')} <b>${esc(g.kind)}</b> ${pill(`${n(g.n)} lần`)} ${pill(`${n(g.users)} người`)}
            <small style="color:var(--text-dim)">· ${ago(g.last)} · lần đầu ${time(g.first)}</small></div>
          <div style="margin:4px 0;color:var(--text-main);font-size:13px">${esc(g.message || '')}</div>
          <div class="mono" style="font-size:11.5px;color:var(--text-dim)">${esc(g.where_ || '')} · trang: ${esc(g.paths || '')}</div>
          ${g.sample?.stack ? `<details class="adm-stack"><summary>Chi tiết (người dùng: ${esc(g.sample.user || 'khách')}, IP ${esc(g.sample.ip || '?')}, ${esc(g.sample.browser || '')})</summary><pre>${esc(g.sample.stack)}</pre></details>` : ''}
        </div>`).join('')}</div>` : '<div class="adm-empty">Không có lỗi nào trong kỳ 🎉</div>')}
      ${card('Yêu cầu lỗi 5xx theo endpoint', '', table([{ label: 'Đường dẫn', cls: 'mono', get: (r) => `${r.method} ${r.route}` }, { label: 'Mã', html: (r) => statusPill(r.status) },
        { label: 'Số lần', num: true, get: (r) => n(r.n) }, { label: 'Loại lỗi', get: (r) => r.errors || '—' }, { label: 'Lần cuối', get: (r) => ago(r.last) }], d.http_5xx, { empty: 'Không có' }))}
    </div>`;
  },

  // ── Nhật ký thô ──
  async view_log(v) {
    const L = this.s.log;
    v.innerHTML = card('Nhật ký chi tiết', 'mọi yêu cầu API, lượt xem trang, sự kiện tài khoản, lỗi — mới nhất trước; không ghi nội dung/mật khẩu', `
      <div class="adm-filters">
        <select id="lg-kind">${[['requests', 'Yêu cầu API'], ['pageviews', 'Lượt xem trang'], ['events', 'Sự kiện tài khoản'], ['errors', 'Lỗi']].map(([k, l]) => `<option value="${k}" ${L.kind === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
        <input id="lg-q" placeholder="Tìm theo email, IP, đường dẫn, trình duyệt…" value="${esc(L.q)}"/>
        <select id="lg-status" ${L.kind !== 'requests' ? 'hidden' : ''}><option value="">Mọi mã</option>${['2xx', '3xx', '4xx', '5xx'].map((s) => `<option ${L.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select>
        <button class="btn btn-secondary btn-sm" id="lg-go">Lọc</button>
        <a class="btn btn-secondary btn-sm" id="lg-csv" href="#">Xuất CSV</a>
      </div>
      <div id="lg-body"><div class="adm-empty">Đang tải…</div></div>
      <div style="text-align:center;margin-top:10px"><button class="btn btn-secondary btn-sm" id="lg-more" hidden>Xem thêm</button></div>`);
    let before = null;
    let rows = [];
    const COLS = {
      requests: [{ label: 'Thời điểm', get: (r) => time(r.ts) }, { label: 'Người dùng', html: (r) => (r.user ? `<a href="#" data-user="${esc(r.user)}">${esc(r.user)}</a>` : '<span style="color:var(--text-dim)">khách</span>') },
        { label: 'Yêu cầu', cls: 'mono', get: (r) => `${r.method} ${r.path}` }, { label: 'Mã', html: (r) => statusPill(r.status) }, { label: 'Thời gian', num: true, get: (r) => ms(r.ms) },
        { label: 'Dung lượng', num: true, get: (r) => (r.bytes != null ? bytes(r.bytes) : '—') }, { label: 'IP', cls: 'mono ip', get: (r) => r.ip },
        { label: 'QG', get: (r) => r.country || '—' }, { label: 'Thiết bị', get: (r) => `${r.browser} · ${r.os} · ${r.device}` }, { label: 'Lỗi', get: (r) => r.error || '' }],
      pageviews: [{ label: 'Thời điểm', get: (r) => time(r.ts) }, { label: 'Người dùng', html: (r) => (r.user ? `<a href="#" data-user="${esc(r.user)}">${esc(r.user)}</a>` : `<small class="mono">khách ${esc((r.vid || '').slice(0, 8))}</small>`) },
        { label: 'Trang', get: (r) => r.path }, { label: 'Ở lại', num: true, get: (r) => (r.dur != null ? dur(r.dur) : '—') }, { label: 'Nguồn', get: (r) => r.ref || '—' },
        { label: 'IP', cls: 'mono ip', get: (r) => r.ip }, { label: 'QG', get: (r) => r.country || '—' }, { label: 'Thiết bị', get: (r) => `${r.browser} · ${r.os} · ${r.device} · ${r.screen || ''}` }],
      events: [{ label: 'Thời điểm', get: (r) => time(r.ts) }, { label: 'Sự kiện', get: (r) => EVENT_NAMES[r.kind] || r.kind }, { label: 'Tài khoản', get: (r) => r.user || '—' },
        { label: 'Người thực hiện', get: (r) => r.actor || '—' }, { label: 'IP', cls: 'mono ip', get: (r) => r.ip || '—' }, { label: 'Chi tiết', cls: 'mono', get: (r) => r.detail || '' }],
      errors: [{ label: 'Thời điểm', get: (r) => time(r.ts) }, { label: 'Nguồn', get: (r) => (r.source === 'server' ? 'Máy chủ' : 'Trình duyệt') }, { label: 'Loại', get: (r) => r.kind },
        { label: 'Thông điệp', get: (r) => r.message || '' }, { label: 'Vị trí', cls: 'mono', get: (r) => r.where_ || '' }, { label: 'Trang', get: (r) => r.path || '' },
        { label: 'Người dùng', get: (r) => r.user || 'khách' }, { label: 'IP', cls: 'mono ip', get: (r) => r.ip || '' }],
    };
    const params = (extra = '') => `kind=${L.kind}&${this.q()}&q=${encodeURIComponent(L.q)}&status=${L.status}${extra}`;
    const load = async (more = false) => {
      const d = await get(`/api/admin/analytics/log?${params(more && before ? `&before=${before}` : '')}`);
      rows = more ? rows.concat(d.rows) : d.rows;
      before = d.next_before;
      v.querySelector('#lg-body').innerHTML = `<div class="adm-scroll" style="max-height:640px">${table(COLS[L.kind], rows, { empty: 'Không có bản ghi khớp bộ lọc' })}</div>
        <div class="sub" style="margin-top:6px">${n(rows.length)} bản ghi đang hiển thị</div>`;
      v.querySelector('#lg-more').style.display = d.rows.length < 200 ? 'none' : '';
      v.querySelectorAll('#lg-body [data-user]').forEach((a) => (a.onclick = (e) => { e.preventDefault(); this.openUser(a.dataset.user); }));
    };
    const apply = () => {
      L.kind = v.querySelector('#lg-kind').value;
      L.q = v.querySelector('#lg-q').value.trim();
      L.status = L.kind === 'requests' ? v.querySelector('#lg-status').value : '';
      v.querySelector('#lg-status').hidden = L.kind !== 'requests';
      load();
    };
    v.querySelector('#lg-go').onclick = apply;
    v.querySelector('#lg-kind').onchange = apply;
    v.querySelector('#lg-q').onkeydown = (e) => { if (e.key === 'Enter') apply(); };
    v.querySelector('#lg-more').onclick = () => load(true);
    v.querySelector('#lg-csv').onclick = (e) => { e.preventDefault(); window.location.href = `/api/admin/analytics/export.csv?${params()}&limit=100000`; };
    await load();
  },

  // ── Hệ thống ──
  async view_system(v) {
    const meter = (p) => `<div class="adm-meter ${p >= 90 ? 'crit' : p >= 75 ? 'hot' : ''}"><div style="width:${Math.min(100, p)}%"></div></div>`;
    const load = async () => {
      const [s, h] = await Promise.all([get('/api/admin/analytics/system'), get('/api/health/tools').catch(() => null)]);
      const gpus = (s.gpu || []).filter((g) => !g.error);
      v.innerHTML = `<div class="adm-grid">
        <div class="adm-3">
          ${card('CPU', `${s.cpu_count} luồng`, `<div class="adm-kpi" style="border:0;padding:0"><div class="v">${s.cpu_percent.toFixed(0)}%</div></div>${meter(s.cpu_percent)}`)}
          ${card('Bộ nhớ RAM', `${bytes(s.memory.used)} / ${bytes(s.memory.total)}`, `<div class="adm-kpi" style="border:0;padding:0"><div class="v">${s.memory.percent.toFixed(0)}%</div></div>${meter(s.memory.percent)}`)}
          ${gpus.map((g) => card(`GPU · ${g.name}`, `${g.temp_c}°C${g.power_w != null ? ` · ${g.power_w.toFixed(0)} W` : ''}`, `
            <div class="sub" style="margin:0">Sử dụng ${g.util}%</div>${meter(g.util)}
            <div class="sub" style="margin:0">VRAM ${bytes(g.mem_used_mb * 1048576)} / ${bytes(g.mem_total_mb * 1048576)}</div>${meter((g.mem_used_mb / g.mem_total_mb) * 100)}`)).join('') || card('GPU', '', '<div class="adm-empty">Không đọc được nvidia-smi</div>')}
        </div>
        <div class="adm-3">
          ${card('Ổ đĩa', '', s.disks.map((d) => `<div class="sub" style="margin:8px 0 0">${esc(d.mount)} — ${bytes(d.used)} / ${bytes(d.total)} (${d.percent}%)</div>${meter(d.percent)}`).join(''))}
          ${card('Tiến trình máy chủ Hub', '', `<dl class="adm-kv"><dt>Thời gian chạy</dt><dd>${dur(s.process.uptime_s)}</dd><dt>RAM tiến trình</dt><dd>${bytes(s.process.rss)}</dd>
            <dt>Số luồng</dt><dd>${s.process.threads}</dd><dt>PID</dt><dd>${s.process.pid}</dd><dt>Máy khởi động</dt><dd>${time(s.boot_time)}</dd>
            <dt>Mạng (từ khi khởi động)</dt><dd>gửi ${bytes(s.net.sent)} · nhận ${bytes(s.net.recv)}</dd></dl>`)}
          ${card('Hàng đợi & dữ liệu', '', `<dl class="adm-kv"><dt>GPU</dt><dd>${s.gpu_queue.busy ? `đang chạy ${esc(s.gpu_queue.owner)} (${s.gpu_queue.running_seconds}s)` : 'rảnh'}${s.gpu_queue.waiting ? ` · ${s.gpu_queue.waiting} chờ` : ''}</dd>
            <dt>Tác vụ nền</dt><dd>${Object.entries(s.jobs).map(([k, c]) => `${esc(k)}: ${c}`).join(' · ') || 'không có'}</dd>
            ${Object.entries(s.sizes || {}).map(([k, b]) => `<dt>${esc(k)}</dt><dd>${bytes(b)}</dd>`).join('')}
            <dt>Nhật ký theo dõi</dt><dd>${bytes(s.analytics.db_bytes)} · giữ ${s.analytics.retention_days} ngày${s.analytics.queue ? ` · chờ ghi ${s.analytics.queue}` : ''}${s.analytics.dropped ? ` · <span style="color:#f87171">bỏ ${s.analytics.dropped} bản ghi (quá tải)</span>` : ''}</dd></dl>`)}
        </div>
        ${h ? card('Tình trạng công cụ', 'tự cập nhật 10 giây', `<div class="ad-health">${Object.entries(h.tools).map(([k, t]) => `<div class="ad-tool"><span class="ad-dot ${t.ok ? 'ok' : 'bad'}"></span><b>${esc(mod(k))}</b><small>${esc(t.detail)}</small></div>`).join('')}</div>`) : ''}
      </div>`;
    };
    await load();
    this._viewTimer = setInterval(() => { if (this.el.isConnected && this.s.tab === 'system') load().catch(() => {}); }, 10000);
  },

  unmount() {
    this._timers.forEach(clearInterval);
    this._timers = [];
    clearInterval(this._viewTimer);
    this._observers.forEach((o) => o.disconnect());
    this._observers = [];
  },
};

const S_PV = [{ key: 'pageviews', label: 'Lượt xem trang', color: '--viz-1' }, { key: 'visitors', label: 'Khách', color: '--viz-2' }];
const S_REQ = [{ key: 'ok', label: 'Thành công', color: '--viz-1' }, { key: 'e4', label: 'Lỗi 4xx', color: '--st-warn' }, { key: 'e5', label: 'Lỗi 5xx', color: '--st-crit' }];
