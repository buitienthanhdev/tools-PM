/**
 * AI Tư vấn pháp luật — chat cho người dùng + khu vực nạp luật ẩn (chỉ admin).
 * Mở khu admin: bấm 5 lần liên tiếp vào biểu tượng ⚖️ trên tiêu đề, rồi nhập khóa admin.
 */

import { eventBus } from '../../stores/eventBus.js';
import { authStore } from '../../stores/authStore.js';
import { pageHero, panelHead, svgIcon } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function md(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|\W)_(.+?)_(?=\W|$)/g, '$1<em>$2</em>')
    .replace(/^\s*[-*] (.+)$/gm, '• $1')
    .replace(/\n/g, '<br>');
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

  render(el) {
    const s = this._s;
    s.history = [];
    s.busy = false;
    try { s.adminKey = sessionStorage.getItem('legalAdminKey') || ''; } catch { s.adminKey = ''; }

    el.innerHTML = `
    ${pageHero(this, {
      title: 'Hỏi đáp pháp luật <span class="thin">có căn cứ</span> điều luật',
      sub: 'Đặt câu hỏi bằng lời thường. AI tra cứu trong các văn bản luật đã nạp và trả lời kèm điều khoản cụ thể để bạn đối chiếu.',
      word: 'Legal',
      meta: ['Trích dẫn điều luật', 'Tiếng Việt', 'Tham khảo'],
    })}

    <div class="mp-body" style="max-width:1080px;">
      <div class="mp-panel flex lg-chat">
        <div class="mp-head">
          <span class="mp-num" id="lg-logo" style="cursor:default;user-select:none">01</span>
          <h3>Trợ lý <span class="thin">pháp luật</span></h3>
          <div class="mp-actions"><span class="badge-tag badge-active">Trực tuyến</span></div>
        </div>
        <div id="lg-msgs" class="lg-msgs"></div>
        <form id="lg-form" class="lg-compose">
          <textarea class="form-textarea" id="lg-input" rows="2"
            placeholder="Ví dụ: Người lao động nghỉ việc không báo trước thì bị xử lý thế nào?"></textarea>
          <button class="btn btn-primary" id="lg-send" type="submit">${svgIcon('send', 16, 2)} Gửi</button>
        </form>
        <div class="mp-hint" style="margin:0;">${svgIcon('alert', 15, 2)}<span>Câu trả lời chỉ mang tính tham khảo, không thay thế tư vấn của luật sư.</span></div>
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

    const refLabel = (x) => `${esc(x.law)} — ${x.article ? `Điều ${esc(x.article)}. ${esc(x.title)}` : 'Trích đoạn'}${x.clause ? ` (khoản ${esc(x.clause)})` : ''}`;

    const bubble = (role, html, meta = {}) => {
      const d = document.createElement('div');
      const user = role === 'user';
      const sources = meta.sources || [];
      d.className = `lg-bubble ${user ? 'is-user' : 'is-bot'}`;
      // [1] → chú thích nhỏ bấm được, mở và làm nổi căn cứ tương ứng
      d.innerHTML = user ? html : html.replace(/\[(\d{1,2})\]/g, (m, n) => (sources.some((x) => x.n === +n) ? `<sup class="lg-cite" data-n="${n}">${n}</sup>` : m));

      const notes = [];
      if (!user && meta.query) notes.push(`Đã hiểu câu hỏi là: “${esc(meta.query)}”`);
      if (!user && sources.length && meta.grounded === false) notes.push('⚠ AI chưa trích dẫn căn cứ cụ thể cho câu trả lời này — hãy đối chiếu các điều luật bên dưới.');
      if (!user && meta.unverified_articles?.length) notes.push(`⚠ Câu trả lời nhắc tới Điều ${meta.unverified_articles.map(esc).join(', ')} không nằm trong căn cứ đã tìm được — cần kiểm tra lại.`);
      if (!user && meta.ai_error) notes.push(`⚠ AI local không trả lời được (${esc(meta.ai_error)}); chỉ hiển thị điều luật liên quan nhất.`);
      notes.forEach((t) => { const n = document.createElement('div'); n.className = 'lg-note'; n.innerHTML = t; d.appendChild(n); });

      if (sources.length) {
        const src = document.createElement('details');
        src.className = 'lg-sources';
        src.innerHTML = `<summary>Căn cứ pháp lý (${sources.length}${meta.mode === 'hybrid' ? ' · tìm kiếm lai' : ''})</summary>` +
          sources.map((x) => `<div data-src="${x.n}" class="${x.cited ? 'is-cited' : ''}">
            <strong><span class="lg-n">${x.n}</span> ${refLabel(x)}</strong>${x.cited ? ' <em>được trích dẫn</em>' : ''}
            ${x.chapter ? `<small>${esc(x.chapter)}</small>` : ''}<br>${esc(x.excerpt)}…
            ${x.similarity != null ? `<small>Độ liên quan ${Math.round(x.similarity * 100)}%</small>` : ''}</div>`).join('');
        d.appendChild(src);
        d.querySelectorAll('.lg-cite').forEach((c) => c.addEventListener('click', () => {
          src.open = true;
          const target = src.querySelector(`[data-src="${c.dataset.n}"]`);
          src.querySelectorAll('[data-src]').forEach((e) => e.classList.remove('flash'));
          target?.classList.add('flash');
          target?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }));
      }
      msgs.appendChild(d);
      msgs.scrollTop = msgs.scrollHeight;
      return d;
    };

    bubble('assistant', md('Xin chào! Tôi là trợ lý tư vấn pháp luật. Bạn cứ hỏi, tôi sẽ trả lời kèm căn cứ điều luật cụ thể nhé.'));

    $('lg-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = $('lg-input').value.trim();
      if (!q || s.busy) return;
      s.busy = true;
      $('lg-send').disabled = true;
      $('lg-input').value = '';
      bubble('user', esc(q));
      const wait = bubble('assistant', '<span class="lg-typing"><i></i><i></i><i></i></span> Đang tra cứu điều luật…');
      try {
        const res = await fetch('/api/legal/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, history: s.history }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        wait.remove();
        bubble('assistant', md(data.answer), data);
        s.history.push({ role: 'user', content: q }, { role: 'assistant', content: data.answer });
      } catch (err) {
        wait.innerHTML = 'Lỗi: ' + esc(err.message);
      } finally {
        s.busy = false;
        $('lg-send').disabled = false;
      }
    });
    $('lg-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('lg-form').requestSubmit(); }
    });

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
