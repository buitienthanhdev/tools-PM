/**
 * AI Tư vấn pháp luật — chat cho người dùng + khu vực nạp luật ẩn (chỉ admin).
 * Mở khu admin: bấm 5 lần liên tiếp vào biểu tượng ⚖️ trên tiêu đề, rồi nhập khóa admin.
 */

import { eventBus } from '../../stores/eventBus.js';
import { authStore } from '../../stores/authStore.js';
import { panelHead, svgIcon } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Dự phòng khi không tải được thư viện (offline): Markdown tối giản
function mdBasic(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/(^|\W)_(.+?)_(?=\W|$)/g, '$1<em>$2</em>')
    .replace(/^\s*[-*] (.+)$/gm, '• $1')
    .replace(/\n/g, '<br>');
}

// Thư viện Markdown / công thức tải một lần từ CDN (đã ghim phiên bản)
const CDN = 'https://cdn.jsdelivr.net/npm/';
let libsPromise = null;
function loadLibs() {
  libsPromise ??= (async () => {
    if (!document.getElementById('lg-katex-css')) {
      const l = document.createElement('link');
      l.id = 'lg-katex-css';
      l.rel = 'stylesheet';
      l.href = CDN + 'katex@0.16.11/dist/katex.min.css';
      document.head.appendChild(l);
    }
    const [marked, purify, katex] = await Promise.all([
      import(CDN + 'marked@12.0.2/lib/marked.esm.js'),
      import(CDN + 'dompurify@3.1.6/dist/purify.es.mjs'),
      import(CDN + 'katex@0.16.11/dist/katex.mjs'),
    ]);
    return { marked: marked.marked, purify: purify.default, katex: katex.default };
  })().catch((err) => { console.warn('[legal] không tải được thư viện Markdown:', err); return null; });
  return libsPromise;
}

/** Markdown (đậm, nghiêng, tiêu đề, danh sách, bảng, code, trích dẫn) + công thức LaTeX → HTML an toàn */
async function renderRich(text) {
  const libs = await loadLibs();
  if (!libs) return mdBasic(text);
  const { marked, purify, katex } = libs;
  const codes = [];
  const maths = [];
  const keepMath = (tex, display) => `M${maths.push({ tex, display }) - 1}`;
  let t = String(text ?? '')
    .replace(/```[\s\S]*?```|`[^`\n]+`/g, (m) => `C${codes.push(m) - 1}`)
    .replace(/\$\$([\s\S]+?)\$\$/g, (m, x) => keepMath(x, true))
    .replace(/\\\[([\s\S]+?)\\\]/g, (m, x) => keepMath(x, true))
    .replace(/\\\(([\s\S]+?)\\\)/g, (m, x) => keepMath(x, false))
    .replace(/(?<![\\$\d])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)/g, (m, x) => keepMath(x, false))
    .replace(/C(\d+)/g, (m, i) => codes[i]);
  const html = purify.sanitize(marked.parse(t, { gfm: true, breaks: true }));
  return html.replace(/M(\d+)/g, (m, i) => {
    const { tex, display } = maths[i];
    return katex.renderToString(tex, { displayMode: display, throwOnError: false, output: 'html' });
  });
}

const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });

export const legalModule = {
  id: 'legal',
  name: 'AI Tư vấn pháp luật',
  route: '/legal',
  icon: '⚖️',
  category: 'Legal AI',
  description: 'Hỏi đáp pháp luật bằng AI — trả lời có căn cứ điều luật, thân thiện và đầy đủ.',
  status: 'active',

  _s: { history: [], busy: false, adminKey: '', taps: 0, tapTimer: null },

  unmount() {
    this._viewport?.classList.remove('lg-full');
    if (this._onKey) { document.removeEventListener('keydown', this._onKey); this._onKey = null; }
  },

  render(el) {
    const s = this._s;
    s.history = [];
    s.busy = false;
    try { s.adminKey = sessionStorage.getItem('legalAdminKey') || ''; } catch { s.adminKey = ''; }

    // Chat chiếm trọn vùng làm việc, khóa cuộn trang: chỉ danh sách tin nhắn bên trong được cuộn
    this._viewport = el.closest('.workspace-container');
    this._viewport?.classList.add('lg-full');
    loadLibs(); // tải trước

    el.innerHTML = `
    <div class="lg-shell">
      <div class="lg-top">
        <span class="mp-num" id="lg-logo" style="cursor:default;user-select:none">01</span>
        <h3>Trợ lý <span class="thin">pháp luật</span></h3>
        <div class="mp-actions"><span class="badge-tag badge-active">Trực tuyến</span></div>
      </div>
      <div id="lg-msgs" class="lg-msgs"><div class="lg-col" id="lg-col"></div></div>
      <div class="lg-foot">
        <form id="lg-form" class="lg-compose">
          <textarea id="lg-input" rows="1"
            placeholder="Ví dụ: Người lao động nghỉ việc không báo trước thì bị xử lý thế nào?"></textarea>
          <button class="lg-send" id="lg-send" type="submit" title="Gửi (Enter)">${svgIcon('send', 18, 2)}</button>
        </form>
        <div class="lg-disclaimer">${svgIcon('alert', 14, 2)}<span>Câu trả lời chỉ mang tính tham khảo, không thay thế tư vấn của luật sư.</span></div>
      </div>
    </div>

    <button id="lg-lock" type="button" title="Quản trị (cần khóa admin)" class="lg-lock">${svgIcon('lock', 16, 2)}</button>

    <div id="lg-admin" class="lg-modal" style="display:none;">
     <div class="mp-panel" style="width:min(720px,100%);max-height:90vh;overflow-y:auto;">
      ${panelHead('', 'Nạp', 'văn bản luật', '<button class="btn btn-secondary btn-sm" id="lg-close" type="button">Đóng</button>')}
      <div id="lg-admin-login" style="display:flex;gap:10px;">
        <input type="password" class="form-input" id="lg-key" placeholder="Khóa admin" style="flex:1" />
        <button class="btn btn-primary" id="lg-login">Mở khóa</button>
      </div>
      <div id="lg-admin-body" style="display:none;">
        <div class="form-group">
          <label class="form-label">Tên luật / văn bản (VD: Bộ luật Lao động 2019)</label>
          <input class="form-input" id="lg-name" />
        </div>
        <div class="form-group">
          <label class="form-label">Tải file (.txt .md .docx .pdf)</label>
          <input type="file" class="form-input" id="lg-file" accept=".txt,.md,.docx,.pdf" />
        </div>
        <div class="form-group">
          <label class="form-label">…hoặc dán nội dung luật (tự tách theo "Điều")</label>
          <textarea class="form-textarea" id="lg-text" rows="6"></textarea>
        </div>
        <button class="btn btn-primary" id="lg-add">Nạp vào hệ thống</button>
        <div id="lg-list" style="margin-top:1.2rem;"></div>
      </div>
     </div>
    </div>`;

    const $ = (id) => el.querySelector('#' + id);
    const msgs = $('lg-msgs');
    const col = $('lg-col');
    const input = $('lg-input');

    const toBottom = () => { msgs.scrollTop = msgs.scrollHeight; };
    const autoGrow = () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px'; };
    input.addEventListener('input', autoGrow);

    const copyText = async (text, btn) => {
      try { await navigator.clipboard.writeText(text); btn.textContent = 'Đã chép'; }
      catch { btn.textContent = 'Lỗi'; }
      setTimeout(() => { btn.textContent = btn.dataset.label; }, 1400);
    };
    const addCopyButton = (host, label, getText, cls = 'lg-copy') => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = cls;
      b.dataset.label = b.textContent = label;
      b.addEventListener('click', () => copyText(getText(), b));
      host.appendChild(b);
    };

    // [1] → chú thích nhỏ bấm được (bỏ qua công thức và code)
    const linkCitations = (root, sources) => {
      const nums = new Set(sources.map((x) => x.n));
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: (n) => (n.parentElement.closest('.katex, pre, code') ? NodeFilter.FILTER_REJECT : /\[\d{1,2}\]/.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
      });
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach((node) => {
        const frag = document.createDocumentFragment();
        node.nodeValue.split(/(\[\d{1,2}\])/).forEach((part) => {
          const m = part.match(/^\[(\d{1,2})\]$/);
          if (m && nums.has(+m[1])) {
            const sup = document.createElement('sup');
            sup.className = 'lg-cite';
            sup.dataset.n = m[1];
            sup.textContent = m[1];
            frag.appendChild(sup);
          } else frag.appendChild(document.createTextNode(part));
        });
        node.replaceWith(frag);
      });
    };

    const refLabel = (x) => `${esc(x.law)} — ${x.article ? `Điều ${esc(x.article)}. ${esc(x.title)}` : 'Trích đoạn'}${x.clause ? ` (khoản ${esc(x.clause)})` : ''}`;

    const bubble = (role, html, meta = {}) => {
      const d = document.createElement('div');
      const user = role === 'user';
      const sources = meta.sources || [];
      d.className = `lg-bubble ${user ? 'is-user' : 'is-bot'}`;
      const body = document.createElement('div');
      body.className = user ? 'lg-text' : 'lg-md';
      body.innerHTML = html;
      d.appendChild(body);
      if (!user) {
        linkCitations(body, sources);
        body.querySelectorAll('a').forEach((a) => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
        body.querySelectorAll('pre').forEach((pre) => {
          const head = document.createElement('div');
          head.className = 'lg-codehead';
          head.innerHTML = `<span>${esc(pre.querySelector('code')?.className.replace(/^.*language-/, '') || 'code')}</span>`;
          addCopyButton(head, 'Sao chép', () => pre.querySelector('code')?.innerText ?? pre.innerText);
          pre.prepend(head);
        });
        body.querySelectorAll('table').forEach((t) => {
          const w = document.createElement('div');
          w.className = 'lg-tablewrap';
          t.replaceWith(w);
          w.appendChild(t);
        });
      }

      const notes = [];
      if (!user && meta.unverified_articles?.length) notes.push(`Lưu ý: Điều ${meta.unverified_articles.map(esc).join(', ')} nhắc trong câu trả lời chưa có trong căn cứ tìm được, bạn nên kiểm tra lại.`);
      if (!user && meta.ai_error) notes.push('AI đang bận nên mình chỉ hiển thị điều luật gần nhất.');
      notes.forEach((t) => { const n = document.createElement('div'); n.className = 'lg-note'; n.textContent = t; d.appendChild(n); });

      if (sources.length) {
        const src = document.createElement('details');
        src.className = 'lg-sources';
        src.innerHTML = `<summary>Xem điều luật được dẫn (${sources.length})</summary>` +
          sources.map((x) => `<div data-src="${x.n}" class="${x.cited ? 'is-cited' : ''}">
            <strong><span class="lg-n">${x.n}</span> ${refLabel(x)}</strong>
            ${x.chapter ? `<small>${esc(x.chapter)}</small>` : ''}<br>${esc(x.excerpt)}…</div>`).join('');
        d.appendChild(src);
        d.querySelectorAll('.lg-cite').forEach((c) => c.addEventListener('click', () => {
          src.open = true;
          const target = src.querySelector(`[data-src="${c.dataset.n}"]`);
          src.querySelectorAll('[data-src]').forEach((e) => e.classList.remove('flash'));
          target?.classList.add('flash');
          target?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }));
      }
      if (!user && meta.raw) {
        const bar = document.createElement('div');
        bar.className = 'lg-actions';
        addCopyButton(bar, 'Sao chép câu trả lời', () => meta.raw, 'lg-copy lg-copy-all');
        d.appendChild(bar);
      }
      col.appendChild(d);
      toBottom();
      return d;
    };

    const welcome = bubble('assistant', mdBasic('Xin chào! Mình là trợ lý pháp luật của Anh Thành đẹp troai. Bạn đang thắc mắc điều gì cứ hỏi nhé 😊'));
    const chips = document.createElement('div');
    chips.className = 'lg-chips';
    ['Người lao động nghỉ việc không báo trước thì bị xử lý thế nào?', 'Mức phạt khi không đội mũ bảo hiểm là bao nhiêu?', 'Thời hạn thử việc tối đa theo luật là bao lâu?'].forEach((t) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = t;
      b.addEventListener('click', () => { input.value = t; $('lg-form').requestSubmit(); });
      chips.appendChild(b);
    });
    welcome.appendChild(chips);

    $('lg-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q || s.busy) return;
      s.busy = true;
      $('lg-send').disabled = true;
      input.value = '';
      autoGrow();
      chips.remove();
      bubble('user', esc(q));
      const wait = bubble('assistant', '<span class="lg-typing"><i></i><i></i><i></i></span> Đang suy nghĩ…');
      try {
        const res = await fetch('/api/legal/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, history: s.history }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        const html = await renderRich(data.answer);
        wait.remove();
        bubble('assistant', html, { ...data, raw: data.answer });
        s.history.push({ role: 'user', content: q }, { role: 'assistant', content: data.answer });
      } catch (err) {
        wait.innerHTML = 'Lỗi: ' + esc(err.message);
      } finally {
        s.busy = false;
        $('lg-send').disabled = false;
      }
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('lg-form').requestSubmit(); }
    });
    input.focus();

    // ── Admin (ẩn) ──
    const adminFetch = async (path, opts = {}) => {
      const res = await fetch('/api/legal/admin' + path, {
        ...opts,
        headers: { ...(opts.headers || {}), 'X-Admin-Key': s.adminKey },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    };

    const refreshList = async () => {
      const { laws } = await adminFetch('/laws');
      $('lg-list').innerHTML = laws.length
        ? laws.map((l) => `<div style="display:flex;justify-content:space-between;gap:1rem;padding:0.4rem 0;border-top:1px solid rgba(255,255,255,0.08)">
            <span>📜 ${esc(l.name)} <small style="opacity:.7">(${l.articles} điều/đoạn)</small>${(l.warnings || []).map((w) => `<br><small style="color:#fbbf24">⚠ ${esc(w)}</small>`).join('')}</span>
            <button class="btn-secondary" data-del="${esc(l.id)}">Xóa</button></div>`).join('')
        : '<em style="opacity:.7">Chưa có luật nào được nạp.</em>';
      $('lg-list').insertAdjacentHTML('beforeend', laws.length ? '<div style="margin-top:12px"><button class="btn btn-secondary btn-sm" id="lg-reindex">Tạo lại chỉ mục vector</button></div>' : '');
    };

    const unlock = async () => {
      await adminFetch('/login', { method: 'POST' });
      try { sessionStorage.setItem('legalAdminKey', s.adminKey); } catch { /* ignore */ }
      $('lg-admin-login').style.display = 'none';
      $('lg-admin-body').style.display = 'block';
      await refreshList();
    };

    const openAdmin = () => {
      $('lg-admin').style.display = 'flex';
      if (authStore.isAdmin()) { $('lg-key').closest('#lg-admin-login').style.display = 'none'; unlock().catch((err) => toast('❌ ' + err.message, 'error')); }
      else toast('Chỉ quản trị viên mới nạp được văn bản luật', 'error');
    };
    $('lg-lock').addEventListener('click', openAdmin);
    if (!authStore.isAdmin()) $('lg-lock').style.display = 'none';
    $('lg-close').addEventListener('click', () => { $('lg-admin').style.display = 'none'; });
    $('lg-logo').addEventListener('click', () => {
      clearTimeout(s.tapTimer);
      s.tapTimer = setTimeout(() => { s.taps = 0; }, 1500);
      if (++s.taps >= 5) { s.taps = 0; openAdmin(); }
    });
    $('lg-key').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('lg-login').click(); });
    if (this._onKey) document.removeEventListener('keydown', this._onKey);
    this._onKey = (e) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'a' && el.isConnected) { e.preventDefault(); openAdmin(); }
    };
    document.addEventListener('keydown', this._onKey);
    if (new URLSearchParams(location.search).has('admin')) openAdmin();

    $('lg-login').addEventListener('click', async () => {
      s.adminKey = $('lg-key').value;
      try { await unlock(); toast('🔓 Đã mở khóa admin', 'success'); }
      catch (err) { s.adminKey = ''; toast('❌ ' + err.message, 'error'); }
    });

    $('lg-add').addEventListener('click', async () => {
      const fd = new FormData();
      fd.append('name', $('lg-name').value);
      fd.append('text', $('lg-text').value);
      const f = $('lg-file').files[0];
      if (f) fd.append('file', f);
      $('lg-add').disabled = true;
      try {
        let r = await adminFetch('/laws', { method: 'POST', body: fd });
        if (r.job) {
          for (;;) {
            await new Promise((ok) => setTimeout(ok, 2000));
            const j = await adminFetch('/jobs/' + r.job);
            $('lg-add').textContent = j.status === 'running' ? `${j.msg || 'Đang xử lý…'}` : 'Nạp vào hệ thống';
            if (j.status === 'error') throw new Error(j.error);
            if (j.status === 'done') { r = j; break; }
          }
        }
        toast(`✅ Đã nạp ${r.articles} điều/đoạn`, 'success');
        $('lg-name').value = ''; $('lg-text').value = ''; $('lg-file').value = '';
        await refreshList();
      } catch (err) { toast('❌ ' + err.message, 'error'); }
      finally { $('lg-add').disabled = false; $('lg-add').textContent = 'Nạp vào hệ thống'; }
    });

    $('lg-list').addEventListener('click', async (e) => {
      if (e.target.id === 'lg-reindex') {
        e.target.disabled = true;
        e.target.textContent = 'Đang tạo chỉ mục…';
        try { const r = await adminFetch('/reindex', { method: 'POST' }); toast(r.vectors ? `Đã lập chỉ mục ${r.chunks} đoạn` : 'Chỉ có BM25: ' + (r.error || 'chưa có vector'), r.vectors ? 'success' : 'error'); }
        catch (err) { toast('❌ ' + err.message, 'error'); }
        e.target.disabled = false; e.target.textContent = 'Tạo lại chỉ mục vector';
        return;
      }
      const id = e.target.dataset?.del;
      if (!id || !confirm('Xóa văn bản luật này khỏi hệ thống?')) return;
      try { await adminFetch('/laws/' + id, { method: 'DELETE' }); await refreshList(); }
      catch (err) { toast('❌ ' + err.message, 'error'); }
    });
  },
};
