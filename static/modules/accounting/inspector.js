/* Panel phải: xem trước chứng từ, bằng chứng từng giá trị (trang PDF + vùng tô / XPath / ô Excel), báo cáo & phiên bản. */

import { svgIcon } from '../../components/icons.js';
import { api, bytes, date, esc, money, status } from './api.js';

const FIELD_VN = {
  form_no: 'Ký hiệu mẫu số', series: 'Ký hiệu', number: 'Số hoá đơn', issue_date: 'Ngày lập', currency: 'Tiền tệ', fx_rate: 'Tỷ giá',
  seller_name: 'Người bán', seller_tax_id: 'MST người bán', seller_address: 'Địa chỉ bán', buyer_name: 'Người mua', buyer_tax_id: 'MST người mua',
  buyer_person: 'Người mua hàng', subtotal: 'Cộng tiền hàng', vat_amount: 'Tiền thuế GTGT', total: 'Tổng thanh toán', authority_code: 'Mã CQT',
  invoice_name: 'Tên hoá đơn', vat_rate_text: 'Thuế suất',
};
const MONEY_FIELDS = new Set(['subtotal', 'vat_amount', 'total']);
const DIRECTION = { sale: 'Bán ra', purchase: 'Mua vào', unknown: 'Chưa rõ chiều (thiếu MST tổ chức)', unrelated: 'Không liên quan tới tổ chức' };

export class Inspector {
  constructor(shell, el, ctx) {
    this.shell = shell; // phần tử .ac-shell (bật/tắt panel)
    this.el = el;
    this.ctx = ctx; // { org: () => id, toast }
    this.current = null;
  }

  close() {
    this.shell.classList.add('no-inspector');
    this.shell.classList.remove('insp-wide');
    this.current = null;
  }

  frame(title, actions, body) {
    this.shell.classList.remove('no-inspector');
    this.el.innerHTML = `
      <div class="ac-insp-head"><h3 title="${esc(title)}">${esc(title)}</h3>
        <div class="ac-actions">${actions || ''}<button class="ac-icon-btn ac-wide-btn" data-wide title="Mở rộng / thu hẹp">${svgIcon('arrow', 15, 2)}</button><button class="ac-icon-btn" data-x title="Đóng">${svgIcon('x', 16, 2)}</button></div></div>
      <div class="ac-insp-body">${body}</div>`;
    this.el.querySelector('[data-x]').onclick = () => this.close();
    this.el.querySelector('[data-wide]').onclick = () => this.shell.classList.toggle('insp-wide');
    return this.el.querySelector('.ac-insp-body');
  }

  loading(title) { this.frame(title, '', '<div class="ac-insp-empty">Đang tải…</div>'); }

  fail(e) { this.frame('Không mở được', '', `<div class="ac-alert bad">${esc(e.message)}</div>`); }

  // ── File ───────────────────────────────────────────
  async file(fileId, focus = null) {
    const org = this.ctx.org();
    this.current = { kind: 'file', id: fileId };
    this.loading('Chứng từ');
    try {
      const [d, p] = await Promise.all([api(`/o/${org}/files/${fileId}`), api(`/o/${org}/files/${fileId}/preview`)]);
      const f = d.file;
      const ex = f.extraction;
      const dl = `<a class="btn btn-secondary btn-xs" href="/api/accounting/o/${org}/files/${fileId}/download" title="Tải bản gốc">${svgIcon('download', 14, 2)}</a>`;
      const body = this.frame(f.name, dl, `
        <dl class="ac-kv">
          <dt>Định dạng</dt><dd>${esc(f.kind)} · ${bytes(f.size)}</dd>
          <dt>Quét virus</dt><dd>${status(f.scan)}</dd>
          <dt>Trích xuất</dt><dd>${ex ? `${status(ex.status)} <span class="ac-note">${esc(ex.parser)}@${esc(ex.version)}</span>` : '—'}</dd>
          ${f.archive_path ? `<dt>Trong ZIP</dt><dd>${esc(f.archive_path)}</dd>` : ''}
          <dt>SHA-256</dt><dd style="font-family:var(--font-mono);font-size:11px">${esc(f.sha256)}</dd>
        </dl>
        ${ex?.error ? `<div class="ac-alert bad">${esc(ex.error.message)}</div>` : ''}
        ${f.warnings.map((w) => `<div class="ac-alert">${esc(w)}</div>`).join('')}
        ${d.documents.flatMap((doc) => doc.warnings).map((w) => `<div class="ac-alert">${esc(w)}</div>`).join('')}
        ${d.invoices.length ? `<div class="ac-section-title"><h3>Hoá đơn</h3><span>bấm để xem bằng chứng</span></div>
          <div class="ac-table-wrap"><table class="ac-table"><tr><th>Số</th><th>Ngày</th><th class="num">Tổng</th><th></th></tr>
          ${d.invoices.map((i) => `<tr class="click" data-inv="${i.id}"><td>${esc(i.series || '')}/${esc(i.number || '?')}</td><td>${date(i.issue_date)}</td>
            <td class="num">${money(i.total)} ${esc(i.currency || '')}</td><td>${status(i.status)}</td></tr>`).join('')}</table></div>` : ''}
        <div class="ac-section-title"><h3>Xem trước</h3></div>
        <div data-preview></div>`);
      body.querySelectorAll('[data-inv]').forEach((tr) => (tr.onclick = () => this.invoice(tr.dataset.inv)));
      this.renderPreview(body.querySelector('[data-preview]'), org, fileId, p, focus);
    } catch (e) { this.fail(e); }
  }

  renderPreview(el, org, fileId, p, focus) {
    if (p.kind === 'pdf') {
      const n = p.pages || 1;
      let page = focus?.page || 1;
      const draw = () => {
        const bbox = focus?.bbox && focus.page === page ? `?bbox=${focus.bbox.join(',')}` : '';
        el.innerHTML = `${n > 1 ? `<div class="ac-tabs" style="margin-bottom:8px">${Array.from({ length: Math.min(n, 30) }, (_, i) =>
          `<button class="ac-tab ${i + 1 === page ? 'active' : ''}" data-p="${i + 1}">Trang ${i + 1}</button>`).join('')}</div>` : ''}
          <img class="ac-page" alt="Trang ${page}" src="/api/accounting/o/${org}/files/${fileId}/page/${page}.png${bbox}" />
          ${focus?.bbox ? '<div class="ac-note">Vùng tô cam là vị trí giá trị trong chứng từ gốc.</div>' : ''}`;
        el.querySelectorAll('[data-p]').forEach((b) => (b.onclick = () => { page = +b.dataset.p; draw(); }));
      };
      draw();
      return;
    }
    if (p.tables?.length) {
      let t = 0;
      const draw = () => {
        const tb = p.tables[t];
        const focusRow = focus?.row;
        el.innerHTML = `${p.tables.length > 1 ? `<div class="ac-tabs" style="margin-bottom:8px">${p.tables.map((x, i) =>
          `<button class="ac-tab ${i === t ? 'active' : ''}" data-t="${i}">${esc(x.sheet || 'Bảng ' + (i + 1))}</button>`).join('')}</div>` : ''}
          <div class="ac-note">Tiêu đề ở dòng ${tb.header_row} · loại bảng: ${esc(tb.kind || 'dữ liệu')} · ${tb.rows.length} dòng đầu</div>
          <div class="ac-table-wrap" style="max-height:60vh"><table class="ac-table"><tr><th>#</th>${tb.header.map((h) => `<th>${esc(h)}</th>`).join('')}</tr>
          ${tb.rows.map((r, i) => `<tr ${tb.row_numbers[i] === focusRow ? 'style="outline:2px solid var(--primary)"' : ''}><td class="muted">${tb.row_numbers[i]}</td>${tb.header.map((_, c) =>
            `<td>${esc(r[c] ?? '')}</td>`).join('')}</tr>`).join('')}</table></div>`;
        el.querySelectorAll('[data-t]').forEach((b) => (b.onclick = () => { t = +b.dataset.t; draw(); }));
      };
      draw();
      return;
    }
    el.innerHTML = p.text ? `<pre class="ac-pre">${esc(p.text.slice(0, 60000))}</pre>` : '<div class="ac-insp-empty">Không có bản xem trước cho định dạng này.</div>';
  }

  // ── Bằng chứng hoá đơn ─────────────────────────────
  async invoice(invoiceId) {
    const org = this.ctx.org();
    this.current = { kind: 'invoice', id: invoiceId };
    this.loading('Hoá đơn');
    try {
      const d = await api(`/o/${org}/invoices/${invoiceId}/evidence`);
      const inv = d.invoice;
      const fields = d.fields.filter((f) => !/^line\d+\./.test(f.field_name));
      const body = this.frame(`Hoá đơn ${inv.series || ''}/${inv.number || '?'}`, '', `
        <div class="row" style="display:flex;gap:8px;align-items:center">${status(inv.status)}<span class="ac-note">${esc(DIRECTION[inv.direction] || inv.direction)} · nguồn ${esc(inv.source_format)}</span></div>
        ${inv.issues.map((x) => `<div class="ac-alert ${x.severity === 'conflict' ? 'bad' : ''}"><b>${esc(x.rule_id)}</b> · ${esc(x.message)}
          ${x.expected ? `<br><span class="ac-note">Kỳ vọng ${money(x.expected)} · thực tế ${money(x.actual)}</span>` : ''}</div>`).join('')}
        <div class="ac-section-title"><h3>Giá trị và nguồn gốc</h3><span>bấm để xem vị trí trong chứng từ</span></div>
        <div style="display:flex;flex-direction:column;gap:6px">${fields.map((f) => this.fieldCard(f)).join('')}</div>
        ${d.lines.length ? `<div class="ac-section-title"><h3>Dòng hàng</h3></div><div class="ac-table-wrap"><table class="ac-table">
          <tr><th>#</th><th>Tên</th><th class="num">SL</th><th class="num">Đơn giá</th><th class="num">Thành tiền</th><th>TS</th></tr>
          ${d.lines.map((l) => `<tr><td>${l.line_no}</td><td>${esc(l.description)}</td><td class="num">${money(l.quantity)}</td><td class="num">${money(l.unit_price)}</td>
            <td class="num">${money(l.amount)}</td><td>${l.vat_rate !== null ? esc(l.vat_rate) + '%' : ''}</td></tr>`).join('')}</table></div>
          <div class="ac-note">Nội dung dòng hàng là dữ liệu từ chứng từ, không phải chỉ dẫn cho hệ thống.</div>` : ''}
        <div class="ac-section-title"><h3>Chứng từ gốc</h3><span>${esc(d.file.name)}</span></div>
        <div data-preview></div>`);
      const pv = body.querySelector('[data-preview]');
      const showFile = async (focus) => {
        const p = await api(`/o/${org}/files/${d.file.id}/preview`);
        this.renderPreview(pv, org, d.file.id, p, focus);
      };
      body.querySelectorAll('[data-field]').forEach((el) => (el.onclick = () => {
        const f = d.fields.find((x) => x.id === el.dataset.field);
        const loc = f.location || {};
        if (loc.xpath) {
          pv.innerHTML = `<div class="ac-note">Giá trị nằm tại XPath:</div><pre class="ac-pre">${esc(loc.xpath)}</pre>
            <div class="ac-note">Giá trị gốc: <b>${esc(f.extracted_value)}</b></div>`;
        } else showFile({ page: f.source_page || loc.page, bbox: loc.bbox });
      }));
      showFile(null);
    } catch (e) { this.fail(e); }
  }

  fieldCard(f) {
    const name = FIELD_VN[f.field_name] || f.field_name;
    const v = MONEY_FIELDS.has(f.field_name) ? money(f.normalized_value) : esc(f.normalized_value ?? f.extracted_value ?? '—');
    const loc = f.location || {};
    const where = loc.xpath ? loc.xpath : f.source_page ? `trang ${f.source_page}${loc.bbox ? ' · vùng ' + loc.bbox.map((x) => Math.round(x)).join(',') : ''}` : (loc.desc || '');
    return `<div class="ac-field" data-field="${f.id}"><div><div class="n">${esc(name)}</div><div class="v">${v}</div></div>
      <div style="text-align:right">${status(f.validation_status)}<div class="n">tin cậy ${Math.round(f.confidence * 100)}% · ${esc(f.extraction_method)}</div></div>
      <div class="loc" title="${esc(where)}">${esc(where)}</div></div>`;
  }

  // ── Báo cáo ────────────────────────────────────────
  async artifact(artifactId, opts = {}) {
    const org = this.ctx.org();
    this.current = { kind: 'artifact', id: artifactId };
    this.loading('Báo cáo');
    try {
      const { artifact: a } = await api(`/o/${org}/artifacts/${artifactId}`);
      const pv = a.preview;
      const dl = `<a class="btn btn-primary btn-xs" href="/api/accounting/o/${org}/artifacts/${a.id}/download">${svgIcon('download', 14, 2)} ${a.kind.toUpperCase()}</a>`;
      const ver = a.versions.length > 1 ? `<select class="ac-select" data-ver>${a.versions.map((v) =>
        `<option value="${v.id}" ${v.id === a.id ? 'selected' : ''}>Phiên bản ${v.version} (${v.kind})</option>`).join('')}</select>` : '';
      // Mặc định mở sheet kết quả chính (không phải sheet tóm tắt/kỹ thuật); báo cáo nhiều sheet mở rộng panel
      const META = ['Tóm tắt', 'Chứng từ', 'Trích xuất'];
      let sheet = opts.sheet ? pv.sheets.findIndex((s) => s.name === opts.sheet) : pv.sheets.findIndex((s) => !META.includes(s.name));
      if (sheet < 0) sheet = 0;
      if (opts.wide && a.kind === 'xlsx') this.shell.classList.add('insp-wide');
      const body = this.frame(a.name, dl, `
        <div class="row" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          ${a.validation?.ok ? '<span class="ac-status ok">Đã tự xác minh</span>' : '<span class="ac-status bad">Chưa qua xác minh</span>'}
          <span class="ac-note">${esc(pv.period || '')} · ${esc(pv.currency || '')}</span>${ver}</div>
        <details><summary class="ac-note" style="cursor:pointer">Chi tiết xác minh (${(a.validation?.checks || []).length} kiểm tra)</summary>
          <ul class="ac-note" style="margin:6px 0 0 16px;padding:0">${(a.validation?.checks || []).map((c) => `<li>${c.ok ? '✓' : '✗'} ${esc(c.check)}</li>`).join('')}</ul>
          <div class="ac-note" style="margin-top:6px">${esc(a.validation?.note || '')}</div></details>
        ${pv.warnings.length ? `<details ${pv.warnings.length < 4 ? 'open' : ''}><summary class="ac-note" style="cursor:pointer;color:var(--amber)">${pv.warnings.length} cảnh báo dữ liệu</summary>
          ${pv.warnings.map((w) => `<div class="ac-alert" style="margin-top:6px">${esc(w.message || w)}</div>`).join('')}</details>` : ''}
        ${a.kind === 'pdf' ? `<iframe title="PDF" style="width:100%;height:70vh;border:1px solid var(--border-color);border-radius:6px;background:#fff" src="/api/accounting/o/${org}/artifacts/${a.id}/download?inline=1"></iframe>` : `
        <div class="ac-tabs">${pv.sheets.map((s, i) => `<button class="ac-tab ${i === sheet ? 'active' : ''}" data-s="${i}">${esc(s.name)}</button>`).join('')}</div>
        <div data-sheet></div>`}`);
      body.querySelector('[data-ver]')?.addEventListener('change', (e) => this.artifact(e.target.value));
      if (a.kind === 'pdf') return;
      const sheetEl = body.querySelector('[data-sheet]');
      const draw = () => {
        const s = pv.sheets[sheet];
        const hasSrc = s.rows.some((r) => r._src);
        const cell = (c, v) => (c.type === 'money' || c.type === 'number' || c.type === 'percent' ? `<td class="num">${money(v)}</td>`
          : c.type === 'date' ? `<td>${date(v)}</td>` : `<td>${esc(v ?? '')}</td>`);
        sheetEl.innerHTML = `<div class="ac-note" style="margin-bottom:6px"><b style="color:var(--text-main)">${esc(s.title)}</b> · ${s.row_count} dòng${s.row_count > s.rows.length ? ` (hiển thị ${s.rows.length})` : ''}</div>
          <div class="ac-table-wrap" style="max-height:62vh"><table class="ac-table">
          <tr>${s.columns.map((c) => `<th class="${['money', 'number', 'percent'].includes(c.type) ? 'num' : ''}">${esc(c.label)}${c.expr ? ' ƒ' : ''}</th>`).join('')}${hasSrc ? '<th>Nguồn</th>' : ''}</tr>
          ${s.rows.map((r, i) => `<tr class="${r._invoice_id ? 'click' : ''}" data-row="${i}">${s.columns.map((c) => cell(c, r[c.key])).join('')}
            ${hasSrc ? `<td>${(r._src || []).map((x) => `<span class="src" data-src="${esc(x)}">${esc(x)}</span>`).join('<br>')}</td>` : ''}</tr>`).join('')}
          ${Object.keys(s.totals || {}).length ? `<tr class="tot">${s.columns.map((c, i) => (c.key in s.totals ? `<td class="num">${money(s.totals[c.key])}</td>` : `<td>${i === 0 ? 'Tổng cộng' : ''}</td>`)).join('')}${hasSrc ? '<td></td>' : ''}</tr>` : ''}
          </table></div>
          ${s.charts?.length ? `<div class="ac-note">Biểu đồ trong file Excel: ${s.charts.map((c) => esc(c.title)).join(', ')}</div>` : ''}
          ${s.columns.some((c) => c.expr) ? '<div class="ac-note">ƒ: cột công thức Excel; giá trị hiển thị được hệ thống tính độc lập bằng số thập phân chính xác.</div>' : ''}`;
        sheetEl.querySelectorAll('[data-src]').forEach((el) => (el.onclick = (ev) => {
          ev.stopPropagation();
          const sid = el.dataset.src.split(' · ')[0];
          const loc = el.dataset.src.split(' · ')[1] || '';
          const src = pv.sources.find((x) => x.id === sid);
          const m = loc.match(/(\d+)\s*$/) || loc.match(/!A?(\d+)/);
          if (src?.file_id) this.file(src.file_id, m ? { row: +m[1] } : null);
        }));
        sheetEl.querySelectorAll('tr[data-row]').forEach((tr) => {
          const r = s.rows[+tr.dataset.row];
          if (r._invoice_id) tr.onclick = () => this.invoice(r._invoice_id);
        });
      };
      body.querySelectorAll('[data-s]').forEach((b) => (b.onclick = () => {
        sheet = +b.dataset.s;
        body.querySelectorAll('[data-s]').forEach((x) => x.classList.toggle('active', x === b));
        draw();
      }));
      draw();
    } catch (e) { this.fail(e); }
  }

  step(task, s) {
    this.current = { kind: 'step' };
    this.frame(`Bước ${s.seq}: ${s.tool}`, '', `
      <dl class="ac-kv"><dt>Mục tiêu</dt><dd>${esc(s.goal)}</dd><dt>Lớp tác vụ</dt><dd>${esc(s.task_class)}</dd>
        <dt>Rủi ro</dt><dd>${esc(s.risk)}${s.approval_required ? ' · cần phê duyệt' : ''}</dd><dt>Trạng thái</dt><dd>${status(s.status)}</dd>
        <dt>Số lần chạy</dt><dd>${s.attempts}</dd><dt>Thời gian</dt><dd>${s.started_at && s.finished_at ? (s.finished_at - s.started_at).toFixed(1) + ' giây' : '—'}</dd></dl>
      ${s.summary ? `<div class="ac-card"><p>${esc(s.summary)}</p></div>` : ''}
      ${s.error ? `<div class="ac-alert bad">${esc(s.error.message)}</div>` : ''}
      ${(s.warnings || []).map((w) => `<div class="ac-alert">${esc(w)}</div>`).join('')}
      <div class="ac-note">Hệ thống chỉ hiển thị tóm tắt thực thi, công cụ đã gọi và bằng chứng — không hiển thị suy luận nội bộ của mô hình.</div>`);
  }
}
