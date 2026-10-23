/**
 * Accounting AI (/accounting) — Agent Workspace + Financial Operations Console.
 * Luồng chính: kéo thả chứng từ → nhập yêu cầu tiếng Việt → theo dõi AI thực thi → xem/tải kết quả.
 * Backend: modules/accounting (API /api/accounting/*). Quyền do máy chủ quyết định; UI chỉ ẩn/hiện nút.
 */

import { svgIcon } from '../../components/icons.js';
import { pageHero, panelHead } from '../../components/pageHero.js';
import { authStore } from '../../stores/authStore.js';
import { eventBus } from '../../stores/eventBus.js';
import { api, ApiError, bytes, date, esc, money, status, TERMINAL, uploadFiles, when } from './api.js';
import { Inspector } from './inspector.js';

const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });

const SUGGESTIONS = [
  'Kiểm tra tất cả chứng từ, phân loại theo nhà cung cấp, phát hiện trùng lặp và xuất báo cáo Excel',
  'Đối soát sao kê ngân hàng với sổ tiền gửi, tìm các khoản chưa khớp',
  'Lọc các hoá đơn trên 20 triệu',
  'Kiểm tra file Excel có công thức sai không',
  'So sánh thu chi theo tháng và tạo dashboard Excel',
  'Tự động định khoản các hoá đơn',
  'Lập bảng công nợ phải thu, phải trả và tuổi nợ',
];

const QUICK = [
  ['file', 'Kiểm tra hoá đơn', 'XML/PDF/ảnh: trường bắt buộc, thuế GTGT, trùng lặp, tổng hợp theo nhà cung cấp',
    'Kiểm tra tất cả hoá đơn, phát hiện trùng lặp, tổng hợp theo nhà cung cấp và xuất báo cáo Excel'],
  ['refresh', 'Đối soát ngân hàng', 'Sao kê ↔ sổ tiền gửi: khớp, mơ hồ, chưa khớp, chênh lệch',
    'Đối soát sao kê ngân hàng với sổ tiền gửi, tìm khoản chưa khớp và tạo báo cáo sai lệch'],
  ['calendar', 'Thu chi theo tháng', 'Gộp sổ quỹ và bảng doanh thu, so sánh theo tháng, có biểu đồ',
    'So sánh thu chi và doanh thu theo tháng, tạo dashboard Excel'],
  ['sliders', 'Kiểm tra công thức Excel', '#REF!, SUM bỏ sót dòng, tổng nhập tay, giá trị lưu sai', 'Kiểm tra file Excel có công thức sai không'],
  ['book', 'Đề xuất định khoản', 'Nợ/Có từ hoá đơn đã kiểm tra — chỉ đề xuất, ghi sổ cần phê duyệt', 'Tự động định khoản các hoá đơn'],
  ['alert', 'Công nợ & tuổi nợ', 'Phải thu/phải trả theo đối tượng, trừ khoản đã thanh toán khớp',
    'Lập bảng công nợ phải thu, phải trả và tuổi nợ'],
  ['grid', 'Thống kê danh sách', 'Danh sách bất kỳ: số dòng, giá trị khác nhau, phân bố theo cột',
    'Thống kê danh sách này: có bao nhiêu dòng, phân bố theo từng cột'],
];

const NAV = [
  ['overview', 'Tổng quan', 'grid'], ['workspace', 'Phiên làm việc', 'spark'], ['files', 'Chứng từ', 'file'], ['reports', 'Báo cáo', 'grid'],
  ['reviews', 'Kiểm duyệt', 'alert'], ['approvals', 'Phê duyệt', 'check'], ['ledger', 'Sổ sách', 'book'],
  ['rules', 'Quy tắc & tài khoản', 'sliders'], ['audit', 'Nhật ký kiểm toán', 'lock'], ['settings', 'Cài đặt', 'refresh'],
];
const CLASS_VN = {
  READ_ONLY: 'Chỉ đọc', TRANSFORM: 'Xử lý', GENERATE_ARTIFACT: 'Tạo báo cáo', PROPOSE_ACCOUNTING_ENTRY: 'Đề xuất bút toán',
  WRITE_INTERNAL_DRAFT: 'Ghi nháp', COMMIT_ACCOUNTING: 'Ghi sổ (cần phê duyệt)', EXTERNAL_ACTION: 'Hành động ngoài',
};
const REVIEW_VN = {
  invoice_check: 'Kiểm tra hoá đơn', missing_data: 'Thiếu thông tin', journal_proposal: 'Đề xuất định khoản', agent_request: 'Yêu cầu của AI',
  recon_ambiguous: 'Đối soát mơ hồ', recon_potential_match: 'Đối soát: có thể khớp', recon_conflicted: 'Đối soát mâu thuẫn',
  dup_invoice_duplicate: 'Hoá đơn trùng', dup_invoice_key_conflict: 'Xung đột số hoá đơn', dup_invoice_suspected: 'Nghi trùng hoá đơn',
  dup_row_duplicate: 'Dòng sao kê trùng', dup_suspected_double_payment: 'Nghi chi trùng', dup_file_duplicate: 'Trùng file',
};

export const accountingModule = {
  id: 'accounting',
  name: 'Kế toán AI',
  route: '/accounting',
  icon: '🧾',
  category: 'Finance AI',
  description: 'Kéo thả chứng từ, ra lệnh bằng tiếng Việt: AI đọc hoá đơn, sao kê, Excel, đối soát, định khoản đề xuất và xuất báo cáo có kiểm chứng.',
  status: 'active',

  s: null,

  unmount() {
    const s = this.s;
    if (!s) return;
    clearInterval(s.countTimer);
    Object.values(s.polls).forEach(clearTimeout);
    s.abort?.abort();
    s.viewport?.classList.remove('ac-full');
    this.s = null;
  },

  async render(el) {
    this.unmount();
    loadCss();
    const s = (this.s = { el, polls: {}, view: 'overview', conv: null, convs: [], tasks: {}, counts: {}, attach: [], uploading: null });
    s.viewport = el.closest('.workspace-container');
    el.innerHTML = '<div class="ac-empty" style="padding-top:160px"><p>Đang mở Kế toán AI…</p></div>';
    try {
      s.status = await api('/status');
    } catch (e) {
      el.innerHTML = `<div class="ac-empty"><h3>Không mở được Kế toán AI</h3><p>${esc(e.status === 404
        ? 'Module chưa được bật trên máy chủ.' : e.status === 403 ? 'Tài khoản của bạn chưa được admin cấp quyền dùng công cụ này.' : e.message)}</p></div>`;
      return;
    }
    s.orgs = s.status.orgs;
    let saved = null;
    try { saved = localStorage.getItem('ac_org'); } catch { /* chế độ riêng tư */ }
    s.org = (s.orgs.find((o) => o.id === saved) || s.orgs[0]).id;
    await this.go(s.view);
  },

  role(r) { return (this.s.orgs.find((o) => o.id === this.s.org)?.roles || []).includes(r); },
  can(perm) {
    const P = { upload: ['ADMIN', 'ACCOUNTANT'], run: ['ADMIN', 'ACCOUNTANT'], review: ['ADMIN', 'REVIEWER', 'ACCOUNTANT'],
      approve: ['APPROVER'], manage: ['ADMIN'], audit: ['ADMIN', 'AUDITOR'], commit: ['ADMIN', 'ACCOUNTANT'] };
    return P[perm].some((r) => this.role(r));
  },

  shell() {
    const s = this.s;
    s.viewport?.classList.add('ac-full');
    clearInterval(s.countTimer);
    s.el.innerHTML = `
    <div class="ac-shell no-inspector">
      <aside class="ac-nav">
        <div class="ac-org"><label for="ac-org">Tổ chức</label>
          <select id="ac-org">${s.orgs.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join('')}<option value="__new">+ Tạo tổ chức mới…</option></select>
          <div class="ac-org-meta" id="ac-orgmeta"></div></div>
        <div class="ac-new"><button class="btn btn-primary btn-sm" id="ac-newconv">${svgIcon('plus', 15, 2)} Phiên làm việc mới</button></div>
        <ul class="ac-navlist">${NAV.map(([id, label, icon]) => `<li><button data-view="${id}">${svgIcon(icon, 16, 2)}<span>${label}</span><span class="ac-badge muted" data-count="${id}" hidden></span></button></li>`).join('')}</ul>
        <div class="ac-convs"><h4>Gần đây</h4><div id="ac-convlist"></div></div>
      </aside>
      <section class="ac-main" id="ac-main"></section>
      <aside class="ac-insp" id="ac-insp"></aside>
      <div class="ac-backdrop" id="ac-backdrop"></div>
    </div>`;
    const shell = s.el.querySelector('.ac-shell');
    s.shellEl = shell;
    s.insp = new Inspector(shell, s.el.querySelector('#ac-insp'), { org: () => s.org, toast });
    const orgSel = s.el.querySelector('#ac-org');
    orgSel.value = s.org;
    orgSel.onchange = async () => {
      if (orgSel.value === '__new') {
        orgSel.value = s.org;
        return this.newOrg();
      }
      this.switchOrg(orgSel.value);
    };
    s.el.querySelector('#ac-newconv').onclick = () => { s.conv = null; s.attach = []; this.go('workspace'); this.closeNav(); };
    s.el.querySelectorAll('[data-view]').forEach((b) => (b.onclick = () => { this.go(b.dataset.view); this.closeNav(); }));
    s.el.querySelector('#ac-backdrop').onclick = () => { shell.classList.remove('nav-open'); s.insp.close(); };
    s.countTimer = setInterval(() => this.counts(), 20000);
  },

  closeNav() { this.s.shellEl?.classList.remove('nav-open'); },

  async switchOrg(id) {
    const s = this.s;
    s.org = id;
    try { localStorage.setItem('ac_org', s.org); } catch { /* bỏ qua */ }
    s.conv = null;
    s.insp?.close();
    if (s.shellEl && s.el.contains(s.shellEl)) {
      s.el.querySelector('#ac-org').innerHTML = `${s.orgs.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join('')}<option value="__new">+ Tạo tổ chức mới…</option>`;
      await this.loadOrg();
    } else {
      await this.go(s.view);
    }
  },

  async newOrg() {
    const name = prompt('Tên tổ chức (doanh nghiệp):');
    if (!name) return;
    const tax = prompt('Mã số thuế của tổ chức (để phân biệt hoá đơn mua vào / bán ra) — có thể bỏ trống:') || '';
    try {
      const r = await api('/orgs', { method: 'POST', body: { name, tax_id: tax } });
      this.s.orgs = r.orgs;
      this.s.shellEl = null;
      await this.switchOrg(r.org_id);
    } catch (e) { toast(e.message, 'error'); }
  },

  async loadOrg() {
    const s = this.s;
    s.el.querySelector('#ac-org').value = s.org;
    s.el.querySelector('[data-view="audit"]').parentElement.hidden = !this.can('audit');
    const org = s.orgs.find((o) => o.id === s.org);
    s.el.querySelector('#ac-orgmeta').innerHTML = org?.tax_id
      ? `<span class="ac-dot ok"></span>MST ${esc(org.tax_id)}`
      : '<button class="ac-linkbtn" data-set-tax type="button"><span class="ac-dot warn"></span>Chưa khai báo MST</button>';
    s.el.querySelector('[data-set-tax]')?.addEventListener('click', () => this.go('settings'));
    await Promise.all([this.loadConvs(), this.counts()]);
    this.go(s.view);
  },

  async loadConvs() {
    const s = this.s;
    try { s.convs = (await api(`/o/${s.org}/conversations`)).conversations; } catch { s.convs = []; }
    const list = s.el.querySelector('#ac-convlist');
    list.innerHTML = s.convs.length ? s.convs.slice(0, 40).map((c) => `<button class="ac-conv ${s.conv?.conversation.id === c.id ? 'active' : ''}" data-conv="${c.id}" title="${esc(c.title)}">${esc(c.title)}</button>`).join('')
      : '<div class="ac-note" style="padding:4px 8px">Chưa có phiên nào.</div>';
    list.querySelectorAll('[data-conv]').forEach((b) => (b.onclick = () => { this.openConv(b.dataset.conv); this.closeNav(); }));
  },

  async counts() {
    const s = this.s;
    if (!s) return;
    try {
      s.counts = await api(`/o/${s.org}/review-count`);
      for (const [view, n] of [['reviews', s.counts.reviews], ['approvals', s.counts.approvals]]) {
        const b = s.el.querySelector(`[data-count="${view}"]`);
        if (b) { b.hidden = !n; b.textContent = n; b.classList.toggle('muted', view === 'reviews'); }
      }
    } catch { /* bỏ qua */ }
  },

  async go(view) {
    const s = this.s;
    if (view === 'overview') return this.landing();
    if (!s.shellEl || !s.el.contains(s.shellEl)) {
      s.view = view;
      this.shell();
      await this.loadOrg();  // loadOrg → go(s.view) khi khung đã có
      return;
    }
    s.view = view;
    s.shellEl?.classList.remove('insp-wide');  // đổi màn hình: trả khung chính về độ rộng đủ dùng
    s.el.querySelectorAll('[data-view]').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
    const fn = { workspace: 'viewWorkspace', files: 'viewFiles', reports: 'viewReports', reviews: 'viewReviews', approvals: 'viewApprovals',
      ledger: 'viewLedger', rules: 'viewRules', audit: 'viewAudit', settings: 'viewSettings' }[view];
    this[fn]();
  },

  main(title, sub, actions, body) {
    const m = this.s.el.querySelector('#ac-main');
    m.innerHTML = `<div class="ac-top"><button class="ac-icon-btn ac-menu-btn" id="ac-menu" title="Menu">${svgIcon('grid', 16, 2)}</button>
      <h2>${esc(title)}</h2>${sub ? `<span class="ac-sub">${sub}</span>` : ''}<div class="ac-actions">${actions || ''}</div></div>${body}`;
    m.querySelector('#ac-menu').onclick = () => this.s.shellEl.classList.add('nav-open');
    return m;
  },

  // ════════════════════ Tổng quan (khuôn trang chung của Hub) ════════════════════
  async landing() {
    const s = this.s;
    s.view = 'overview';
    Object.values(s.polls).forEach(clearTimeout);
    s.polls = {};
    clearInterval(s.countTimer);
    s.shellEl = null;
    s.insp = null;
    s.viewport?.classList.remove('ac-full');
    if (s.viewport) s.viewport.scrollTop = 0;
    s.el.innerHTML = `<div class="ac-land-root">
      ${pageHero(this, {
        title: 'Kế toán <span class="thin">tự động</span> bằng AI',
        sub: 'Kéo thả hoá đơn, sao kê, sổ sách, Excel và ra lệnh bằng tiếng Việt. AI đọc, kiểm tra, đối soát và lập báo cáo truy vết tới từng chứng từ gốc — việc ghi sổ luôn cần người phê duyệt.',
        word: 'Ledger',
        meta: ['AI local · Ollama', 'Truy vết chứng từ gốc', 'Ghi sổ cần phê duyệt'],
      })}
      <div class="mp-body ac-landing" id="ac-land"><div class="mp-panel"><p class="ac-note">Đang tải…</p></div></div>
      <div class="ac-drop fixed" id="ac-land-drop"><div>${svgIcon('upload', 34, 1.6)}<b>Thả để bắt đầu một phiên làm việc mới</b></div></div>
    </div>`;
    const root = s.el.querySelector('.ac-land-root');
    root.querySelectorAll('[data-link]').forEach((a) => (a.onclick = (e) => { e.preventDefault(); window.router.navigate(a.dataset.link || a.getAttribute('href')); }));
    let d;
    try { d = await api(`/o/${s.org}/overview`); } catch (e) {
      s.el.querySelector('#ac-land').innerHTML = `<div class="mp-panel"><div class="ac-alert bad">${esc(e.message)}</div></div>`;
      return;
    }
    if (this.s !== s || s.view !== 'overview' || !s.el.contains(root)) return;
    const inv = d.invoices.by_status || {};
    const okN = (inv.VERIFIED || 0) + (inv.VALID_EXTRACTED || 0) + (inv.REVIEWED || 0);
    const warnN = (inv.NEEDS_REVIEW || 0) + (inv.NEEDS_EVIDENCE || 0);
    const badN = inv.CONFLICTED || 0;
    const seg = (n, cls, label) => (n ? `<i class="${cls}" style="flex:${n}" title="${label}: ${n}"></i>` : '');
    const num = (n) => Number(n || 0).toLocaleString('vi-VN');
    const tile = (label, value, sub, view) => `<button class="ac-kpi link" data-goview="${view}" type="button">
      <span class="ac-kpi-label">${label}</span><span class="ac-kpi-value">${num(value)}</span><span class="ac-kpi-sub">${sub}</span></button>`;
    const counts = { reviews: d.reviews_open, approvals: d.approvals_pending };
    const goto = NAV.filter(([id]) => id !== 'overview' && (id !== 'audit' || this.can('audit')));
    const orgSel = `<select class="ac-select" id="ac-land-org" title="Tổ chức">${s.orgs.map((o) => `<option value="${o.id}" ${o.id === s.org ? 'selected' : ''}>${esc(o.name)}</option>`).join('')}<option value="__new">+ Tạo tổ chức mới…</option></select>`;
    s.el.querySelector('#ac-land').innerHTML = `
      <div class="mp-panel">
        ${panelHead('01', 'Bắt đầu', 'phiên làm việc', `${orgSel}<button class="btn btn-primary btn-sm" id="ac-land-new">${svgIcon('plus', 14, 2)} Phiên làm việc mới</button>`)}
        ${!d.org.tax_id ? `<div class="ac-alert" style="margin-bottom:16px">Tổ chức chưa khai báo <b>mã số thuế</b> — hệ thống sẽ không phân biệt hoá đơn mua vào / bán ra.
          <button class="btn btn-secondary btn-xs" data-goview="settings" style="margin-left:6px">Khai báo</button></div>` : ''}
        <button class="ac-dropcard" data-ov-pick type="button"><span class="ac-dropcard-ic">${svgIcon('upload', 26, 1.8)}</span>
          <b>Kéo thả chứng từ vào đây hoặc bấm để chọn file</b>
          <span>Hoá đơn XML/PDF/ảnh · sao kê · sổ quỹ · Excel · CSV · DOCX · ZIP — tối đa ${s.status.limits.max_file_mb} MB/file</span>
          <span class="ac-fmt">${['XML', 'PDF', 'JPG/PNG', 'XLSX', 'CSV', 'DOCX', 'ZIP'].map((x) => `<i>${x}</i>`).join('')}</span></button>
        <input type="file" id="ac-ov-file" multiple hidden />
        <div class="ac-goto">${goto.map(([id, label, icon]) => `<button class="ac-goto-btn" data-goview="${id}" type="button">${svgIcon(icon, 15, 2)}<span>${label}</span>${counts[id] ? `<span class="ac-badge${id === 'reviews' ? ' muted' : ''}">${counts[id]}</span>` : ''}</button>`).join('')}</div>
      </div>
      <div class="mp-panel">
        ${panelHead('02', 'Tình hình', 'hiện tại')}
        <div class="ac-kpis">
          ${tile('Chứng từ', d.files, d.files_7d ? `+${num(d.files_7d)} trong 7 ngày` : 'bản gốc lưu bất biến', 'files')}
          <button class="ac-kpi link" data-goview="files" type="button"><span class="ac-kpi-label">Hoá đơn</span>
            <span class="ac-kpi-value">${num(d.invoices.total)}</span>
            ${d.invoices.total ? `<span class="ac-statbar" role="img" aria-label="${okN} đã kiểm tra, ${warnN} cần xem, ${badN} mâu thuẫn">${seg(okN, 'ok', 'Đã kiểm tra')}${seg(warnN, 'warn', 'Cần xem')}${seg(badN, 'bad', 'Mâu thuẫn')}</span>
            <span class="ac-legend"><span><span class="ac-dot ok"></span>${okN} đã kiểm tra</span><span><span class="ac-dot warn"></span>${warnN} cần xem</span>${badN ? `<span><span class="ac-dot bad"></span>${badN} mâu thuẫn</span>` : ''}</span>`
              : '<span class="ac-kpi-sub">chưa có hoá đơn</span>'}</button>
          ${tile('Chờ kiểm duyệt', d.reviews_open, d.reviews_open ? 'điểm AI không tự kết luận' : 'không có việc tồn', 'reviews')}
          ${tile('Chờ phê duyệt ghi sổ', d.approvals_pending, `${num(d.journal.posted)} bút toán đã ghi sổ`, 'approvals')}
          ${tile('Báo cáo', d.artifacts, `${num(d.tasks.week)} tác vụ trong 7 ngày${d.tasks.running ? ` · ${d.tasks.running} đang chạy` : ''}`, 'reports')}
        </div>
        <p class="ac-inventory">Dữ liệu đã nhận diện: <b>${num(d.bank_txns)}</b> giao dịch sao kê · <b>${num(d.ledger_entries)}</b> dòng sổ ·
          <b>${num(d.tables)}</b> bảng dữ liệu · <b>${num(d.journal.proposed)}</b> bút toán đề xuất</p>
      </div>
      <div class="mp-panel">
        ${panelHead('03', 'Bắt đầu', 'nhanh')}
        <p class="ac-note" style="margin:-12px 0 18px">Chọn nghiệp vụ → kéo thả file → gửi. Câu lệnh được điền sẵn, có thể sửa trước khi gửi.</p>
        <div class="ac-actions-grid">${QUICK.map((q, i) => `<button class="ac-action" data-quick="${i}" type="button">
          <span class="ac-action-ic">${svgIcon(q[0], 18, 2)}</span><b>${esc(q[1])}</b><span>${esc(q[2])}</span></button>`).join('')}</div>
      </div>
      <div class="mp-panel">
        ${panelHead('04', 'Hoạt động', 'gần đây')}
        <div class="ac-ov-cols">
          <div><div class="ac-section-title"><h3>Phiên làm việc</h3></div>
            ${d.recent_tasks.length ? `<div class="ac-list">${d.recent_tasks.map((t) => `<button class="ac-row" data-conv="${t.conversation_id || ''}" type="button">
              ${status(t.status)}<span class="t">${esc(t.command)}</span><span class="w">${when(t.created_at)}</span></button>`).join('')}</div>`
              : '<p class="ac-note">Chưa có phiên nào — chọn một nghiệp vụ ở trên để bắt đầu.</p>'}</div>
          <div><div class="ac-section-title"><h3>Báo cáo</h3></div>
            ${d.recent_artifacts.length ? `<div class="ac-list">${d.recent_artifacts.map((a) => `<button class="ac-row" data-art="${a.id}" type="button">
              <span class="ac-file-ic">${svgIcon(a.kind === 'pdf' ? 'file' : 'grid', 15, 2)}</span><span class="t">${esc(a.name)}</span><span class="w">v${a.version} · ${when(a.created_at)}</span></button>`).join('')}</div>`
              : '<p class="ac-note">Báo cáo Excel/PDF do AI tạo sẽ xuất hiện ở đây.</p>'}</div>
        </div>
      </div>`;
    const land = s.el.querySelector('#ac-land');
    land.querySelectorAll('[data-goview]').forEach((b) => (b.onclick = () => this.go(b.dataset.goview)));
    land.querySelectorAll('[data-quick]').forEach((b) => (b.onclick = () => this.startSession(QUICK[+b.dataset.quick][3])));
    land.querySelectorAll('[data-conv]').forEach((b) => (b.onclick = () => b.dataset.conv && this.openConv(b.dataset.conv)));
    land.querySelectorAll('[data-art]').forEach((b) => (b.onclick = async () => {
      await this.go('reports');
      this.s?.insp?.artifact(b.dataset.art, { wide: true });
    }));
    land.querySelector('#ac-land-new').onclick = () => this.startSession();
    const sel = land.querySelector('#ac-land-org');
    sel.onchange = () => {
      if (sel.value === '__new') { sel.value = s.org; this.newOrg(); return; }
      this.switchOrg(sel.value);
    };
    const fileIn = land.querySelector('#ac-ov-file');
    land.querySelector('[data-ov-pick]').onclick = () => fileIn.click();
    fileIn.onchange = () => { const f = [...fileIn.files]; fileIn.value = ''; this.startSession(null, f); };
    const drop = root.querySelector('#ac-land-drop');
    let depth = 0;
    root.addEventListener('dragenter', (e) => { if (e.dataTransfer?.types?.includes('Files')) { depth++; drop.classList.add('on'); e.preventDefault(); } });
    root.addEventListener('dragover', (e) => { if (e.dataTransfer?.types?.includes('Files')) e.preventDefault(); });
    root.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) drop.classList.remove('on'); });
    root.addEventListener('drop', (e) => {
      e.preventDefault(); depth = 0; drop.classList.remove('on');
      if (e.dataTransfer?.files?.length) this.startSession(null, [...e.dataTransfer.files]);
    });
  },

  /** Mở phiên mới (tuỳ chọn điền sẵn lệnh và/hoặc tải file ngay). */
  async startSession(command = null, files = null) {
    const s = this.s;
    s.conv = null;
    s.attach = [];
    s.prefill = command;
    await this.go('workspace');
    if (files?.length) this.addFiles(files);
  },

  // ════════════════════ Workspace (hội thoại) ════════════════════
  async openConv(id) {
    const s = this.s;
    try {
      s.conv = await api(`/o/${s.org}/conversations/${id}`);
    } catch (e) { toast(e.message, 'error'); return; }
    s.attach = [];
    s.view = 'workspace';
    await this.go('workspace');
    this.loadConvs();
  },

  viewWorkspace() {
    const s = this.s;
    const c = s.conv;
    const nFiles = c?.files.length || 0;
    const nArts = c?.artifacts.length || 0;
    const m = this.main(c ? c.conversation.title : 'Phiên làm việc mới', c ? `${nFiles} chứng từ · ${nArts} kết quả` : '',
      `${c && nFiles ? `<button class="btn btn-secondary btn-xs" id="ac-convfiles">${svgIcon('file', 14, 2)} Chứng từ (${nFiles})</button>` : ''}`,
      `<div class="ac-scroll" id="ac-scroll"><div class="ac-pad"><div class="ac-col" id="ac-feed"></div></div></div>
       <div class="ac-compose-wrap"><div class="ac-compose">
         <div class="ac-uploading" id="ac-upl" hidden></div>
         <div class="ac-attach" id="ac-attach"></div>
         <textarea id="ac-input" rows="2" placeholder="${this.can('run') ? 'Nhập yêu cầu bằng tiếng Việt, ví dụ: Kiểm tra tất cả hoá đơn, phát hiện trùng lặp và xuất báo cáo Excel' : 'Vai trò của bạn chỉ được xem'}"></textarea>
         <div class="ac-compose-bar">
           <button class="ac-icon-btn" id="ac-pick" title="Chọn file">${svgIcon('upload', 16, 2)}</button>
           <input type="file" id="ac-file" multiple hidden accept=".pdf,.xlsx,.xlsm,.xls,.csv,.tsv,.txt,.xml,.json,.docx,.png,.jpg,.jpeg,.tif,.tiff,.zip" />
           <span class="hint">Kéo thả PDF, ảnh, Excel, CSV, XML hoá đơn, ZIP… · Enter để gửi, Shift+Enter xuống dòng</span>
           <button class="ac-send send" id="ac-send" title="Gửi">${svgIcon('send', 17, 2)}</button>
         </div></div></div>
       <div class="ac-drop" id="ac-drop"><div>${svgIcon('upload', 34, 1.6)}<b>Thả chứng từ vào đây</b><span class="ac-note">Bản gốc được lưu bất biến, quét an toàn trước khi xử lý</span></div></div>`);
    m.querySelector('#ac-convfiles')?.addEventListener('click', () => this.convFiles());
    this.renderFeed();
    this.renderAttach();
    this.bindCompose(m);
    if (s.prefill) {
      const i = m.querySelector('#ac-input');
      i.value = s.prefill;
      autosize(i);
      i.focus();
      s.prefill = null;
    }
  },

  convFiles() {
    const s = this.s;
    const files = s.conv.files;
    const body = s.insp.frame('Chứng từ của phiên', '', `<div class="ac-table-wrap"><table class="ac-table">
      <tr><th>File</th><th>Loại</th><th>Đọc</th></tr>${files.map((f) => `<tr class="click" data-f="${f.id}"><td>${esc(f.name)}</td><td>${esc(f.kind)}</td>
      <td>${f.extraction ? status(f.extraction.status) : '<span class="ac-note">chưa đọc</span>'}</td></tr>`).join('')}</table></div>`);
    body.querySelectorAll('[data-f]').forEach((tr) => (tr.onclick = () => s.insp.file(tr.dataset.f)));
  },

  renderFeed() {
    const s = this.s;
    const feed = s.el.querySelector('#ac-feed');
    if (!feed) return;
    const c = s.conv;
    const org = s.orgs.find((o) => o.id === s.org);
    const taxNote = !org?.tax_id ? `<div class="ac-alert" style="margin-bottom:6px">Tổ chức chưa khai báo <b>mã số thuế</b> — hệ thống sẽ không phân biệt được hoá đơn mua vào / bán ra.
      <button class="btn btn-secondary btn-xs" data-goto-settings style="margin-left:6px">Khai báo trong Cài đặt</button></div>` : '';
    if (!c || !c.messages.length) {
      const attached = s.conv?.files?.length || 0;
      feed.innerHTML = `${taxNote}<button class="ac-dropcard" data-pick type="button">
          <span class="ac-dropcard-ic">${svgIcon('upload', 26, 1.8)}</span>
          <b>${attached ? `Đã có ${attached} chứng từ — thêm file hoặc nhập yêu cầu bên dưới` : 'Kéo thả chứng từ vào đây hoặc bấm để chọn file'}</b>
          <span>Hoá đơn XML/PDF/ảnh · sao kê · sổ quỹ · Excel · CSV · DOCX · ZIP — tối đa ${s.status.limits.max_file_mb} MB/file</span>
          <span class="ac-fmt">${['XML', 'PDF', 'JPG/PNG', 'XLSX', 'CSV', 'DOCX', 'ZIP'].map((x) => `<i>${x}</i>`).join('')}</span>
        </button>
        <div class="ac-empty" style="padding-top:22px"><h3>Rồi ra lệnh bằng tiếng Việt</h3>
        <p>AI đọc dữ liệu, chọn công cụ tính toán chính xác, tự kiểm tra kết quả và trả về báo cáo truy vết được tới từng chứng từ gốc.
        Việc ghi sổ luôn cần người phê duyệt.</p>
        <div class="ac-chips">${SUGGESTIONS.map((t) => `<button class="ac-chip">${esc(t)}</button>`).join('')}</div></div>`;
      feed.querySelector('[data-goto-settings]')?.addEventListener('click', () => this.go('settings'));
      feed.querySelector('[data-pick]')?.addEventListener('click', () => s.el.querySelector('#ac-file')?.click());
      feed.querySelectorAll('.ac-chip').forEach((b) => (b.onclick = () => { const i = s.el.querySelector('#ac-input'); i.value = b.textContent; i.focus(); autosize(i); }));
      return;
    }
    feed.innerHTML = c.messages.map((msg) => {
      if (msg.role === 'user') {
        return `<div class="ac-msg user"><div class="who">${esc((msg.created_by || '?')[0].toUpperCase())}</div><div class="body"><div class="text">${esc(msg.content)}</div>
          <div class="meta">${when(msg.created_at)}</div></div></div>${msg.task_id ? `<div data-task="${msg.task_id}"></div>` : ''}`;
      }
      return `<div class="ac-msg assistant"><div class="who">AI</div><div class="body"><div class="text">${esc(msg.content)}</div>
        <div class="meta">${when(msg.created_at)}</div></div></div>`;
    }).join('');
    for (const t of c.tasks) this.pollTask(t.id, true);
    const sc = s.el.querySelector('#ac-scroll');
    sc.scrollTop = sc.scrollHeight;
  },

  async pollTask(taskId, first = false) {
    const s = this.s;
    if (!s) return;
    clearTimeout(s.polls[taskId]);
    let v;
    try { v = await api(`/o/${s.org}/tasks/${taskId}`); } catch { return; }
    if (!this.s || this.s !== s) return;
    const prev = s.tasks[taskId]?.task.status;
    s.tasks[taskId] = v;
    const slot = s.el.querySelector(`[data-task="${taskId}"]`);
    if (slot) this.renderTask(slot, v);
    const done = TERMINAL.includes(v.task.status);
    if (!done) s.polls[taskId] = setTimeout(() => this.pollTask(taskId), 1500);
    else if (!first && prev && prev !== v.task.status && s.conv) {
      s.conv = await api(`/o/${s.org}/conversations/${s.conv.conversation.id}`).catch(() => s.conv);
      this.renderFeed();
      this.counts();
      const t = s.el.querySelector('.ac-top h2');
      if (t) t.textContent = s.conv.conversation.title;
      const art = [...v.steps].reverse().find((x) => x.data?.artifact_id && x.data.kind === 'xlsx');
      if (art) s.insp.artifact(art.data.artifact_id);
    }
  },

  renderTask(slot, v) {
    const s = this.s;
    const t = v.task;
    const running = !TERMINAL.includes(t.status);
    const prog = [...v.events].reverse().find((e) => e.kind === 'progress');
    const lastInfo = [...v.events].reverse().find((e) => ['progress', 'info', 'step_start'].includes(e.kind));
    const warns = [...new Set(v.steps.flatMap((x) => x.warnings || []))];
    const planEv = v.events.find((e) => e.kind === 'plan');
    const arts = v.steps.filter((x) => x.data?.artifact_id);
    const icon = (st) => (st === 'COMPLETED' ? svgIcon('check', 12, 3) : st === 'FAILED' ? svgIcon('x', 12, 3) : st === 'NEEDS_INPUT' ? '?' : '');
    const elapsed = Math.max(0, Math.round((t.updated_at - t.created_at)));
    slot.innerHTML = `<div class="ac-task">
      <div class="ac-task-head">${status(t.status)}<b>${running ? 'AI đang thực hiện' : 'Kết quả thực hiện'}</b>
        <span class="ac-note">${planEv ? (planEv.data?.source === 'llm' ? 'kế hoạch do AI lập' : 'kế hoạch theo quy tắc') : ''}${elapsed ? ` · ${elapsed}s` : ''}</span>
        <div class="ac-actions">${running && this.can('run') ? '<button class="btn btn-danger btn-xs" data-cancel>Dừng</button>' : ''}</div></div>
      <ul class="ac-steps">${v.steps.map((x) => `<li class="ac-step ${x.status}" data-step="${x.seq}" style="cursor:pointer">
        <span class="ic">${icon(x.status)}</span><div><div class="goal">${esc(x.goal)}</div>${x.summary ? `<div class="sum">${esc(x.summary)}</div>` : x.error ? `<div class="sum" style="color:var(--rose)">${esc(x.error.message)}</div>` : ''}</div>
        <span class="tool" title="${esc(CLASS_VN[x.task_class] || x.task_class)}">${esc(x.tool)}</span></li>`).join('') || '<li class="ac-step RUNNING"><span class="ic"></span><div class="goal">Đang nhận việc…</div><span></span></li>'}</ul>
      ${running && lastInfo ? `<div class="ac-progress">${esc(lastInfo.message)}${prog?.data?.n ? `<div class="bar"><i style="width:${Math.round(100 * prog.data.i / prog.data.n)}%"></i></div>` : ''}</div>` : ''}
      ${warns.length ? `<div class="ac-warns">${warns.slice(0, 6).map((w) => `<div class="ac-warn">${svgIcon('alert', 13, 2)}<span>${esc(w)}</span></div>`).join('')}${warns.length > 6 ? `<div class="ac-note">+${warns.length - 6} cảnh báo khác trong báo cáo</div>` : ''}</div>` : ''}
      ${arts.length ? `<div class="ac-arts">${arts.map((x) => `<button class="ac-art" data-art="${x.data.artifact_id}">${svgIcon(x.data.kind === 'pdf' ? 'file' : 'grid', 15, 2)}
        <span>${esc(x.data.name)}</span>${x.data.verified !== false ? `<span class="ok" title="Đã tự xác minh">${svgIcon('check', 13, 3)}</span>` : ''}</button>`).join('')}</div>` : ''}
    </div>`;
    slot.querySelector('[data-cancel]')?.addEventListener('click', async () => {
      try { await api(`/o/${s.org}/tasks/${t.id}/cancel`, { method: 'POST' }); this.pollTask(t.id); } catch (e) { toast(e.message, 'error'); }
    });
    slot.querySelectorAll('[data-art]').forEach((b) => (b.onclick = () => s.insp.artifact(b.dataset.art)));
    slot.querySelectorAll('[data-step]').forEach((li) => (li.onclick = () => s.insp.step(t, v.steps.find((x) => x.seq === +li.dataset.step))));
  },

  renderAttach() {
    const s = this.s;
    const el = s.el.querySelector('#ac-attach');
    if (!el) return;
    el.innerHTML = s.attach.map((r) => {
      const cls = r.status === 'rejected' ? 'bad' : r.status === 'duplicate' ? 'dup' : '';
      const tip = r.error?.message || r.warnings?.join('; ') || r.kind || '';
      const kids = r.children?.length ? ` (+${r.children.length})` : '';
      return `<span class="ac-file-chip ${cls}" title="${esc(tip)}">${svgIcon(r.status === 'rejected' ? 'x' : 'file', 13, 2)}<span>${esc(r.name)}${kids}</span></span>`;
    }).join('');
  },

  bindCompose(m) {
    const s = this.s;
    const input = m.querySelector('#ac-input');
    const send = m.querySelector('#ac-send');
    const fileIn = m.querySelector('#ac-file');
    const drop = m.querySelector('#ac-drop');
    if (!this.can('run')) { input.disabled = true; send.disabled = true; }
    input.addEventListener('input', () => autosize(input));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); this.send(); }
    });
    send.onclick = () => this.send();
    m.querySelector('#ac-pick').onclick = () => fileIn.click();
    fileIn.onchange = () => { this.addFiles([...fileIn.files]); fileIn.value = ''; };
    let depth = 0;
    m.addEventListener('dragenter', (e) => { if (e.dataTransfer?.types?.includes('Files')) { depth++; drop.classList.add('on'); e.preventDefault(); } });
    m.addEventListener('dragover', (e) => { if (e.dataTransfer?.types?.includes('Files')) e.preventDefault(); });
    m.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) drop.classList.remove('on'); });
    m.addEventListener('drop', (e) => {
      e.preventDefault();
      depth = 0;
      drop.classList.remove('on');
      if (e.dataTransfer?.files?.length) this.addFiles([...e.dataTransfer.files]);
    });
  },

  async ensureConv(title) {
    const s = this.s;
    if (s.conv) return s.conv.conversation.id;
    const r = await api(`/o/${s.org}/conversations`, { method: 'POST', body: { title: title || 'Phiên làm việc mới' } });
    s.conv = { conversation: r.conversation, messages: [], tasks: [], artifacts: [], files: [] };
    this.loadConvs();
    return r.conversation.id;
  },

  async addFiles(files) {
    const s = this.s;
    if (!this.can('upload')) { toast('Vai trò của bạn không được tải chứng từ lên', 'error'); return; }
    if (!files.length || s.uploading) return;
    const max = s.status.limits.max_file_mb * 1024 * 1024;
    const tooBig = files.filter((f) => f.size > max);
    if (tooBig.length) toast(`${tooBig.length} file vượt ${s.status.limits.max_file_mb} MB — máy chủ sẽ từ chối`, 'error');
    const bar = s.el.querySelector('#ac-upl');
    try {
      const cid = await this.ensureConv();
      s.uploading = true;
      bar.hidden = false;
      const { results } = await uploadFiles(s.org, files, cid, (sent, total, done) => {
        bar.textContent = `Đang tải ${done}/${files.length} file · ${bytes(sent)} / ${bytes(total)}`;
      });
      s.attach.push(...results);
      const rej = results.filter((r) => r.status === 'rejected');
      const dup = results.filter((r) => r.status === 'duplicate');
      if (rej.length) toast(`${rej.length} file bị từ chối: ${rej.map((r) => `${r.name} (${r.error?.message})`).join('; ')}`.slice(0, 300), 'error');
      if (dup.length) toast(`${dup.length} file trùng hoàn toàn với file đã có — dùng lại bản cũ`, 'info');
      s.conv = await api(`/o/${s.org}/conversations/${cid}`);
      const t = s.el.querySelector('.ac-top .ac-sub');
      if (t) t.textContent = `${s.conv.files.length} chứng từ · ${s.conv.artifacts.length} kết quả`;
      if (!s.conv.messages.length) this.renderFeed();
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      s.uploading = null;
      if (bar) bar.hidden = true;
      this.renderAttach();
    }
  },

  async send() {
    const s = this.s;
    const input = s.el.querySelector('#ac-input');
    const text = input.value.trim();
    if (!text) return;
    if (s.uploading) { toast('Đợi tải file xong rồi gửi', 'info'); return; }
    const btn = s.el.querySelector('#ac-send');
    btn.disabled = true;
    try {
      const cid = await this.ensureConv(text.slice(0, 80));
      await api(`/o/${s.org}/conversations/${cid}/messages`, { method: 'POST', body: { content: text } });
      input.value = '';
      autosize(input);
      s.attach = [];
      this.renderAttach();
      s.conv = await api(`/o/${s.org}/conversations/${cid}`);
      this.renderFeed();
      this.loadConvs();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Không gửi được yêu cầu', 'error');
    } finally { btn.disabled = false; }
  },

  // ════════════════════ Chứng từ ════════════════════
  async viewFiles() {
    const s = this.s;
    const m = this.main('Chứng từ', 'bản gốc lưu bất biến theo SHA-256', '<input class="ac-input" id="ac-q" placeholder="Lọc theo tên…" />',
      '<div class="ac-scroll"><div class="ac-pad" id="ac-body"><div class="ac-note">Đang tải…</div></div></div>');
    const { files } = await api(`/o/${s.org}/files`).catch((e) => ({ files: [], err: e }));
    const body = m.querySelector('#ac-body');
    const draw = (q = '') => {
      const rows = files.filter((f) => f.name.toLowerCase().includes(q.toLowerCase()));
      body.innerHTML = rows.length ? `<div class="ac-table-wrap"><table class="ac-table"><tr><th>File</th><th>Định dạng</th><th class="num">Kích thước</th>
        <th>Quét</th><th>Trích xuất</th><th>Tải lên</th></tr>${rows.map((f) => `<tr class="click" data-f="${f.id}"><td>${esc(f.name)}${f.archive_path ? `<div class="ac-note">${esc(f.archive_path)}</div>` : ''}</td>
        <td>${esc(f.kind)}</td><td class="num">${bytes(f.size)}</td><td>${status(f.scan)}</td><td>${f.extraction ? status(f.extraction.status) : '<span class="ac-note">chưa đọc</span>'}</td>
        <td class="muted">${when(f.uploaded_at)}</td></tr>`).join('')}</table></div>` : '<div class="ac-empty"><p>Chưa có chứng từ. Kéo thả file vào Phiên làm việc để bắt đầu.</p></div>';
      body.querySelectorAll('[data-f]').forEach((tr) => (tr.onclick = () => s.insp.file(tr.dataset.f)));
    };
    m.querySelector('#ac-q').oninput = (e) => draw(e.target.value);
    draw();
  },

  // ════════════════════ Báo cáo ════════════════════
  async viewReports() {
    const s = this.s;
    const m = this.main('Báo cáo', 'mỗi lần sửa tạo phiên bản mới, phiên bản cũ được giữ nguyên', '',
      '<div class="ac-scroll"><div class="ac-pad" id="ac-body"><div class="ac-note">Đang tải…</div></div></div>');
    const { artifacts } = await api(`/o/${s.org}/artifacts`).catch(() => ({ artifacts: [] }));
    const groups = {};
    artifacts.forEach((a) => (groups[a.root_id] ||= []).push(a));
    const body = m.querySelector('#ac-body');
    const list = Object.values(groups).map((g) => g.sort((a, b) => b.version - a.version));
    body.innerHTML = list.length ? `<div class="ac-grid2">${list.map((g) => `<div class="ac-card"><h4>${esc(g[0].name)}</h4>
      <p>${esc(g[0].kind.toUpperCase())} · ${g.length} phiên bản · ${when(g[0].created_at)}</p>
      <div class="row"><button class="btn btn-secondary btn-xs" data-a="${g[0].id}">Xem</button>
      <a class="btn btn-primary btn-xs" href="/api/accounting/o/${s.org}/artifacts/${g[0].id}/download">${svgIcon('download', 13, 2)} Tải</a>
      ${g[0].conversation_id ? `<button class="btn btn-secondary btn-xs" data-c="${g[0].conversation_id}">Mở phiên</button>` : ''}</div></div>`).join('')}</div>`
      : '<div class="ac-empty"><p>Chưa có báo cáo nào.</p></div>';
    body.querySelectorAll('[data-a]').forEach((b) => (b.onclick = () => s.insp.artifact(b.dataset.a, { wide: true })));
    body.querySelectorAll('[data-c]').forEach((b) => (b.onclick = () => this.openConv(b.dataset.c)));
  },

  // ════════════════════ Kiểm duyệt ════════════════════
  async viewReviews() {
    const s = this.s;
    const m = this.main('Kiểm duyệt', 'những điểm hệ thống không tự kết luận', `<select class="ac-select" id="ac-st"><option value="OPEN">Đang mở</option><option value="RESOLVED">Đã xử lý</option><option value="DISMISSED">Bỏ qua</option></select>`,
      '<div class="ac-scroll"><div class="ac-pad"><div class="ac-col" id="ac-body"><div class="ac-note">Đang tải…</div></div></div></div>');
    const sel = m.querySelector('#ac-st');
    sel.value = s.reviewStatus || 'OPEN';
    sel.onchange = () => { s.reviewStatus = sel.value; this.viewReviews(); };
    const { items } = await api(`/o/${s.org}/reviews?status=${sel.value}`).catch(() => ({ items: [] }));
    const body = m.querySelector('#ac-body');
    if (!items.length) { body.innerHTML = '<div class="ac-empty"><p>Không có mục nào.</p></div>'; return; }
    const open = sel.value === 'OPEN';
    body.innerHTML = items.map((it) => {
      const d = it.detail || {};
      let extra = '';
      if (it.kind === 'missing_data' && d.choices && open) {
        extra = `<div class="row" style="margin-top:8px"><select class="ac-select" data-acct>${d.choices.map((c) => `<option value="${esc(c.code)}">${esc(c.code)} — ${esc(c.name)}</option>`).join('')}</select>
          <label class="ac-note"><input type="checkbox" data-rule /> Lưu thành quy tắc cho người bán này (cần người khác duyệt)</label>
          <button class="btn btn-primary btn-xs" data-answer="${esc(it.target_id)}">Định khoản</button></div>`;
      }
      const reasons = (d.reasons || (d.issues || []).map((x) => x.message) || []).slice(0, 5);
      return `<div class="ac-card" data-item="${it.id}"><div class="row"><span class="ac-status warn">${esc(REVIEW_VN[it.kind] || it.kind)}</span><span class="ac-note">${when(it.created_at)}</span></div>
        <h4 style="margin-top:8px">${esc(it.title)}</h4>${reasons.map((r) => `<p>• ${esc(r)}</p>`).join('')}${d.question && !it.title.includes(d.question.slice(0, 30)) ? `<p>${esc(d.question)}</p>` : ''}
        ${(d.evidence || []).slice(0, 4).map((e) => `<p class="ac-note">${esc([e.file, e.number || e.row, e.total ? money(e.total) : '', e.date].filter(Boolean).join(' · '))}</p>`).join('')}
        ${extra}
        ${open ? `<div class="row" style="margin-top:10px">
          ${it.target_type === 'invoice' ? `<button class="btn btn-secondary btn-xs" data-ev="${esc(it.target_id)}">Xem bằng chứng</button>` : ''}
          ${it.kind === 'journal_proposal' ? `<button class="btn btn-secondary btn-xs" data-goto="ledger">Xem bút toán</button>` : ''}
          ${it.kind !== 'missing_data' ? `<button class="btn btn-ok btn-xs" data-act="accept">${it.kind === 'invoice_check' ? 'Xác nhận đã kiểm tra' : 'Đã xem, chấp nhận'}</button>` : ''}
          <button class="btn btn-secondary btn-xs" data-act="dismiss">Bỏ qua</button></div>` : `<p class="ac-note">${esc(it.resolved_by || '')} · ${when(it.resolved_at)}</p>`}</div>`;
    }).join('');
    body.querySelectorAll('[data-ev]').forEach((b) => (b.onclick = () => s.insp.invoice(b.dataset.ev)));
    body.querySelectorAll('[data-goto]').forEach((b) => (b.onclick = () => this.go(b.dataset.goto)));
    body.querySelectorAll('[data-act]').forEach((b) => (b.onclick = async () => {
      const id = b.closest('[data-item]').dataset.item;
      const note = b.dataset.act === 'dismiss' ? prompt('Lý do bỏ qua (ghi vào nhật ký kiểm toán):') : '';
      if (note === null) return;
      try { await api(`/o/${s.org}/reviews/${id}`, { method: 'POST', body: { action: b.dataset.act, note } }); this.counts(); this.viewReviews(); } catch (e) { toast(e.message, 'error'); }
    }));
    body.querySelectorAll('[data-answer]').forEach((b) => (b.onclick = async () => {
      const card = b.closest('[data-item]');
      const acct = card.querySelector('[data-acct]').value;
      try {
        const r = await api(`/o/${s.org}/answers`, { method: 'POST', body: { answers: { [b.dataset.answer]: acct }, save_rule: card.querySelector('[data-rule]').checked } });
        toast(r.proposed.length ? `Đã đề xuất bút toán (chưa ghi sổ)${r.rule_ids.length ? ' và gửi quy tắc chờ duyệt' : ''}` : (r.skipped[0]?.reason || r.needs_input[0]?.question || 'Không tạo được đề xuất'), r.proposed.length ? 'success' : 'error');
        this.counts();
        this.viewReviews();
      } catch (e) { toast(e.message, 'error'); }
    }));
  },

  // ════════════════════ Phê duyệt ════════════════════
  async viewApprovals() {
    const s = this.s;
    const m = this.main('Phê duyệt ghi sổ', 'người phê duyệt phải khác người tạo và người yêu cầu', '',
      '<div class="ac-scroll"><div class="ac-pad"><div class="ac-col" id="ac-body"><div class="ac-note">Đang tải…</div></div></div></div>');
    const { approvals } = await api(`/o/${s.org}/approvals`).catch(() => ({ approvals: [] }));
    const body = m.querySelector('#ac-body');
    if (!approvals.length) { body.innerHTML = '<div class="ac-empty"><p>Không có yêu cầu nào chờ phê duyệt.</p></div>'; return; }
    body.innerHTML = approvals.map((a) => `<div class="ac-card" data-ap="${a.id}">
      <div class="row">${status(a.status)}<span class="ac-note">${esc(a.requested_by)} yêu cầu · ${when(a.requested_at)}</span></div>
      ${a.entry ? this.entryHtml(a.entry) : ''}
      <div class="row" style="margin-top:10px">${a.can_approve ? `<button class="btn btn-ok btn-xs" data-ok>Phê duyệt & ghi sổ</button><button class="btn btn-danger btn-xs" data-no>Từ chối</button>`
        : `<span class="ac-note">${this.can('approve') ? 'Bạn là người tạo/yêu cầu nên không được tự duyệt.' : 'Cần vai trò APPROVER để phê duyệt.'}</span>`}</div></div>`).join('');
    body.querySelectorAll('[data-ok]').forEach((b) => (b.onclick = async () => {
      if (!confirm('Ghi sổ bút toán này? Sau khi ghi sổ, chỉ sửa được bằng bút toán đảo.')) return;
      try { await api(`/o/${s.org}/approvals/${b.closest('[data-ap]').dataset.ap}/approve`, { method: 'POST' }); toast('Đã ghi sổ', 'success'); this.counts(); this.viewApprovals(); }
      catch (e) { toast(`${e.message}${e.data?.details?.length ? ': ' + e.data.details.join('; ') : ''}`, 'error'); }
    }));
    body.querySelectorAll('[data-no]').forEach((b) => (b.onclick = async () => {
      const reason = prompt('Lý do từ chối:');
      if (reason === null) return;
      try { await api(`/o/${s.org}/approvals/${b.closest('[data-ap]').dataset.ap}/reject`, { method: 'POST', body: { reason } }); this.counts(); this.viewApprovals(); }
      catch (e) { toast(e.message, 'error'); }
    }));
  },

  entryHtml(e) {
    return `<h4 style="margin-top:8px">${date(e.entry_date)} · ${esc(e.description)}</h4>
      <div class="ac-table-wrap"><table class="ac-table"><tr><th>TK</th><th class="num">Nợ</th><th class="num">Có</th><th>Diễn giải</th></tr>
      ${e.lines.map((l) => `<tr><td>${esc(l.account_code)}</td><td class="num">${l.debit !== '0' ? money(l.debit) : ''}</td><td class="num">${l.credit !== '0' ? money(l.credit) : ''}</td><td>${esc(l.memo || '')}</td></tr>`).join('')}
      </table></div>`;
  },

  // ════════════════════ Sổ sách ════════════════════
  async viewLedger() {
    const s = this.s;
    s.ledgerTab ||= 'entries';
    const m = this.main('Sổ sách', 'bút toán, cân đối phát sinh, kỳ kế toán', `<div class="ac-tabs">${[['entries', 'Bút toán'], ['tb', 'Cân đối phát sinh'], ['periods', 'Kỳ kế toán']].map(([k, l]) =>
      `<button class="ac-tab ${s.ledgerTab === k ? 'active' : ''}" data-lt="${k}">${l}</button>`).join('')}</div>`,
      '<div class="ac-scroll"><div class="ac-pad"><div class="ac-col" id="ac-body"><div class="ac-note">Đang tải…</div></div></div></div>');
    m.querySelectorAll('[data-lt]').forEach((b) => (b.onclick = () => { s.ledgerTab = b.dataset.lt; this.viewLedger(); }));
    const body = m.querySelector('#ac-body');
    if (s.ledgerTab === 'tb') {
      const tb = await api(`/o/${s.org}/ledger/trial-balance`);
      body.innerHTML = `<div class="row">${tb.balanced ? '<span class="ac-status ok">Cân đối</span>' : '<span class="ac-status bad">KHÔNG cân đối</span>'}<span class="ac-note">Chỉ gồm bút toán đã ghi sổ</span></div>
        <div class="ac-table-wrap"><table class="ac-table"><tr><th>TK</th><th>Tên</th><th class="num">Phát sinh Nợ</th><th class="num">Phát sinh Có</th><th class="num">Số dư (Nợ − Có)</th></tr>
        ${tb.rows.map((r) => `<tr><td>${esc(r.account)}</td><td>${esc(r.name)}</td><td class="num">${money(r.debit)}</td><td class="num">${money(r.credit)}</td><td class="num">${money(r.balance)}</td></tr>`).join('')}
        <tr class="tot"><td>Tổng</td><td></td><td class="num">${money(tb.total_debit)}</td><td class="num">${money(tb.total_credit)}</td><td></td></tr></table></div>`;
      return;
    }
    if (s.ledgerTab === 'periods') {
      const { periods } = await api(`/o/${s.org}/periods`);
      body.innerHTML = periods.length ? `<div class="ac-table-wrap"><table class="ac-table"><tr><th>Kỳ</th><th>Trạng thái</th><th></th></tr>${periods.map((p) =>
        `<tr><td>${date(p.start_date)} – ${date(p.end_date)}</td><td>${p.status === 'locked' ? `<span class="ac-status bad">Đã khoá</span> <span class="ac-note">${esc(p.locked_by || '')}</span>` : '<span class="ac-status ok">Mở</span>'}</td>
        <td>${p.status === 'open' && (this.can('manage') || this.can('approve')) ? `<button class="btn btn-danger btn-xs" data-lock="${p.id}">Khoá sổ</button>` : ''}</td></tr>`).join('')}</table></div>`
        : '<div class="ac-empty"><p>Kỳ kế toán được tạo khi có bút toán đầu tiên được ghi sổ.</p></div>';
      body.querySelectorAll('[data-lock]').forEach((b) => (b.onclick = async () => {
        if (!confirm('Khoá sổ kỳ này? Không thể ghi thêm bút toán vào kỳ đã khoá.')) return;
        try { await api(`/o/${s.org}/periods/${b.dataset.lock}/lock`, { method: 'POST' }); this.viewLedger(); } catch (e) { toast(e.message, 'error'); }
      }));
      return;
    }
    const { entries } = await api(`/o/${s.org}/journal`);
    body.innerHTML = entries.length ? entries.map((e) => `<div class="ac-card" data-e="${e.id}"><div class="row">${status(e.status)}<span class="ac-note">${esc(e.source)} · ${esc(e.created_by)} · ${when(e.created_at)}</span>
      ${e.pending_approval ? '<span class="ac-status warn">Chờ phê duyệt</span>' : ''}</div>${this.entryHtml(e)}
      <div class="row" style="margin-top:8px">
        ${e.status === 'PROPOSED' && !e.pending_approval && this.can('commit') ? '<button class="btn btn-primary btn-xs" data-req>Gửi yêu cầu ghi sổ</button>' : ''}
        ${e.status === 'POSTED' && this.can('commit') ? '<button class="btn btn-secondary btn-xs" data-rev>Tạo bút toán đảo</button>' : ''}
        ${e.source_refs.map((r) => (r.invoice_id ? `<button class="btn btn-secondary btn-xs" data-inv="${r.invoice_id}">Hoá đơn nguồn</button>` : '')).join('')}</div></div>`).join('')
      : '<div class="ac-empty"><p>Chưa có bút toán. Hãy yêu cầu AI "định khoản các hoá đơn" — AI chỉ tạo đề xuất, không tự ghi sổ.</p></div>';
    body.querySelectorAll('[data-req]').forEach((b) => (b.onclick = async () => {
      try { await api(`/o/${s.org}/journal/${b.closest('[data-e]').dataset.e}/request-post`, { method: 'POST' }); toast('Đã gửi yêu cầu ghi sổ', 'success'); this.counts(); this.viewLedger(); }
      catch (e) { toast(`${e.message}${e.data?.details?.length ? ': ' + e.data.details.join('; ') : ''}`, 'error'); }
    }));
    body.querySelectorAll('[data-rev]').forEach((b) => (b.onclick = async () => {
      const reason = prompt('Lý do đảo bút toán:');
      if (!reason) return;
      try { await api(`/o/${s.org}/journal/${b.closest('[data-e]').dataset.e}/reverse`, { method: 'POST', body: { reason } }); this.viewLedger(); } catch (e) { toast(e.message, 'error'); }
    }));
    body.querySelectorAll('[data-inv]').forEach((b) => (b.onclick = () => s.insp.invoice(b.dataset.inv)));
  },

  // ════════════════════ Quy tắc ════════════════════
  async viewRules() {
    const s = this.s;
    const m = this.main('Quy tắc & tài khoản', 'quy tắc nội bộ chỉ có hiệu lực khi được người khác duyệt', '',
      '<div class="ac-scroll"><div class="ac-pad"><div class="ac-col" id="ac-body"><div class="ac-note">Đang tải…</div></div></div></div>');
    const d = await api(`/o/${s.org}/rules`);
    const body = m.querySelector('#ac-body');
    body.innerHTML = `
      <div class="ac-section-title"><h3>Quy tắc hạch toán nội bộ</h3></div>
      ${d.rules.length ? `<div class="ac-table-wrap"><table class="ac-table"><tr><th>Điều kiện</th><th>TK</th><th>Trạng thái</th><th>Đề xuất</th><th>Duyệt</th><th></th></tr>
        ${d.rules.map((r) => `<tr><td>${esc(r.match_type)} = ${esc(r.match_value)}</td><td>${esc(r.account_code)}</td><td>${status(r.status)}</td><td class="muted">${esc(r.proposed_by)}</td>
        <td class="muted">${esc(r.decided_by || '')}</td><td>${r.status === 'PROPOSED' && (this.can('approve') || this.can('manage')) ? `<button class="btn btn-ok btn-xs" data-rule="${r.id}" data-ok="1">Duyệt</button> <button class="btn btn-danger btn-xs" data-rule="${r.id}" data-ok="0">Từ chối</button>` : ''}</td></tr>`).join('')}</table></div>`
        : '<p class="ac-note">Chưa có quy tắc. Quy tắc được đề xuất khi bạn trả lời câu hỏi "hạch toán vào tài khoản nào" và chọn lưu thành quy tắc.</p>'}
      <div class="ac-section-title"><h3>Căn cứ pháp lý đã cấu hình</h3><span>không tuyên bố tuân thủ khi chưa được chuyên gia xác nhận</span></div>
      <div class="ac-table-wrap"><table class="ac-table"><tr><th>Mã</th><th>Nội dung</th><th>Căn cứ</th><th>Hiệu lực từ</th><th>Mức triển khai</th></tr>
        ${d.legal_rules.map((r) => `<tr><td>${esc(r.rule_id)}</td><td>${esc(r.title)}</td><td>${esc(r.legal_source)} — ${esc(r.legal_reference)}</td><td>${date(r.effective_from)}</td>
        <td><span class="ac-status ${r.implementation_status === 'IMPLEMENTED' ? 'ok' : 'warn'}">${esc(r.implementation_status)}</span></td></tr>`).join('')}</table></div>
      <div class="ac-section-title"><h3>Hệ thống tài khoản</h3><span>${esc(d.accounts[0]?.regime || '')}</span></div>
      <div class="ac-alert">Danh mục khởi tạo theo TT 99/2025/TT-BTC (thay TT 200/2014 từ 01/01/2026). Phụ lục II chưa có trong kho văn bản của hệ thống nên danh mục được đánh dấu
        <b>chưa đối chiếu</b> — kế toán trưởng cần kiểm tra trước khi dùng cho báo cáo pháp định.</div>
      <div class="ac-table-wrap"><table class="ac-table"><tr><th>TK</th><th>Tên</th><th>Loại</th><th>Chi tiết</th></tr>
        ${d.accounts.map((a) => `<tr><td>${esc(a.code)}</td><td>${esc(a.name)}</td><td class="muted">${esc(a.acct_type)}</td><td>${a.postable ? '✓' : ''}</td></tr>`).join('')}</table></div>`;
    body.querySelectorAll('[data-rule]').forEach((b) => (b.onclick = async () => {
      try { await api(`/o/${s.org}/rules/${b.dataset.rule}/decide`, { method: 'POST', body: { approve: b.dataset.ok === '1' } }); this.viewRules(); } catch (e) { toast(e.message, 'error'); }
    }));
  },

  // ════════════════════ Nhật ký kiểm toán ════════════════════
  async viewAudit() {
    const s = this.s;
    const m = this.main('Nhật ký kiểm toán', 'chỉ thêm, nối chuỗi băm SHA-256', '<button class="btn btn-secondary btn-xs" id="ac-verify">Kiểm tra toàn vẹn</button>',
      '<div class="ac-scroll"><div class="ac-pad" id="ac-body"><div class="ac-note">Đang tải…</div></div></div>');
    m.querySelector('#ac-verify').onclick = async () => {
      try {
        const r = await api(`/o/${s.org}/audit/verify`);
        toast(r.ok ? `Chuỗi nhật ký toàn vẹn (${r.events} sự kiện)` : `PHÁT HIỆN SỬA ĐỔI tại sự kiện #${r.first_bad_seq}`, r.ok ? 'success' : 'error');
      } catch (e) { toast(e.message, 'error'); }
    };
    const body = m.querySelector('#ac-body');
    try {
      const { events } = await api(`/o/${s.org}/audit?limit=300`);
      body.innerHTML = `<div class="ac-table-wrap"><table class="ac-table"><tr><th>#</th><th>Thời gian</th><th>Người/agent</th><th>Hành động</th><th>Đối tượng</th><th>Chi tiết</th></tr>
        ${events.map((e) => `<tr><td class="muted">${e.seq}</td><td class="muted">${when(e.ts)}</td><td>${esc(e.actor)}</td><td>${esc(e.action)}</td><td class="muted">${esc(e.target_type || '')} ${esc((e.target_id || '').slice(0, 8))}</td>
        <td class="muted" style="max-width:420px;word-break:break-word">${esc(JSON.stringify(e.details)).slice(0, 300)}</td></tr>`).join('')}</table></div>`;
    } catch (e) { body.innerHTML = `<div class="ac-alert bad">${esc(e.message)}</div>`; }
  },

  // ════════════════════ Cài đặt ════════════════════
  async viewSettings() {
    const s = this.s;
    const m = this.main('Cài đặt', '', '', '<div class="ac-scroll"><div class="ac-pad"><div class="ac-col" id="ac-body"><div class="ac-note">Đang tải…</div></div></div></div>');
    const d = await api(`/o/${s.org}/settings`);
    const cap = s.status.capabilities;
    const manage = this.can('manage');
    const body = m.querySelector('#ac-body');
    body.innerHTML = `
      <div class="ac-card"><h4>Tổ chức</h4>
        <div class="row" style="margin-top:8px"><input class="ac-input" id="ac-oname" value="${esc(d.org.name)}" ${manage ? '' : 'disabled'} style="flex:1;min-width:220px" />
        <input class="ac-input" id="ac-otax" value="${esc(d.org.tax_id || '')}" placeholder="Mã số thuế" ${manage ? '' : 'disabled'} style="width:170px" />
        ${manage ? '<button class="btn btn-primary btn-xs" id="ac-osave">Lưu</button>' : ''}</div>
        <p class="ac-note">MST dùng để xác định hoá đơn mua vào / bán ra. Vai trò của bạn: ${d.roles.map(esc).join(', ')}</p></div>
      ${manage ? `<div class="ac-card"><h4>Thành viên & vai trò</h4>
        <div class="ac-table-wrap" style="margin-top:8px"><table class="ac-table"><tr><th>Email</th><th>Vai trò</th></tr>${d.members.map((u) => `<tr><td>${esc(u.email)}</td><td>${u.roles.map(esc).join(', ')}</td></tr>`).join('')}</table></div>
        <div class="row" style="margin-top:10px"><input class="ac-input" id="ac-memail" placeholder="email@congty.vn" style="flex:1;min-width:200px" />
          ${s.status.roles.map((r) => `<label class="ac-note"><input type="checkbox" value="${r}" data-role /> ${r}</label>`).join('')}
          <button class="btn btn-secondary btn-xs" id="ac-madd">Cập nhật</button></div>
        <p class="ac-note">Người được thêm cũng cần được admin Hub cấp quyền công cụ "Kế toán AI". Bỏ chọn hết vai trò để gỡ khỏi tổ chức.</p></div>` : ''}
      <div class="ac-card"><h4>Năng lực hệ thống</h4><dl class="ac-kv" style="margin-top:8px">
        <dt>AI lập kế hoạch</dt><dd>${cap.llm_planner ? `${esc(cap.planner_model)} — ${cap.llm.ok ? '<span class="ac-status ok">sẵn sàng</span>' : `<span class="ac-status warn">${esc(cap.llm.error)}</span>`}` : 'tắt (dùng quy tắc)'}</dd>
        <dt>Dữ liệu gửi AI</dt><dd>${cap.cloud_ai_allowed ? 'cho phép AI đám mây' : 'chỉ AI chạy trên máy chủ nội bộ; AI không nhận nội dung chứng từ, chỉ nhận tên file và số lượng'}</dd>
        <dt>OCR ảnh/scan</dt><dd>${cap.ocr ? 'EasyOCR (vi, en) trên GPU nội bộ' : 'không khả dụng'}</dd>
        <dt>Quét virus</dt><dd>${cap.antivirus ? 'Microsoft Defender' : 'không có trình quét — file được đánh dấu "chưa quét"'}</dd>
        <dt>Giới hạn</dt><dd>${s.status.limits.max_file_mb} MB/file · ${s.status.limits.max_files_per_upload} file/lần · ${s.status.limits.max_pdf_pages} trang PDF · ${s.status.limits.max_zip_members} file/ZIP</dd></dl></div>`;
    body.querySelector('#ac-osave')?.addEventListener('click', async () => {
      try {
        await api(`/o/${s.org}/settings`, { method: 'POST', body: { name: body.querySelector('#ac-oname').value, tax_id: body.querySelector('#ac-otax').value } });
        s.status = await api('/status');
        s.orgs = s.status.orgs;
        toast('Đã lưu', 'success');
        const sel = s.el.querySelector('#ac-org');
        sel.innerHTML = `${s.orgs.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join('')}<option value="__new">+ Tạo tổ chức mới…</option>`;
        sel.value = s.org;
      } catch (e) { toast(e.message, 'error'); }
    });
    body.querySelector('#ac-madd')?.addEventListener('click', async () => {
      const roles = [...body.querySelectorAll('[data-role]:checked')].map((x) => x.value);
      try { await api(`/o/${s.org}/members`, { method: 'POST', body: { email: body.querySelector('#ac-memail').value, roles } }); this.viewSettings(); } catch (e) { toast(e.message, 'error'); }
    });
  },
};

function autosize(t) {
  t.style.height = 'auto';
  t.style.height = `${Math.min(220, t.scrollHeight)}px`;
}

function loadCss() {
  if (document.getElementById('ac-css')) return;
  const l = document.createElement('link');
  l.id = 'ac-css';
  l.rel = 'stylesheet';
  l.href = '/styles/accounting.css?v=5';
  document.head.appendChild(l);
}

