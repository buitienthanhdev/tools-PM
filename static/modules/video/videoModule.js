/* Video Workspace (/video): tải video, tăng độ phân giải / phục hồi / nội suy fps bằng backend REAL-Video-Enhancer
   chạy trên GPU của máy chủ. Mọi thông số đầu ra lấy từ /api/video/plan (máy chủ tính), không ước đoán ở trình duyệt. */

import { eventBus } from '../../stores/eventBus.js';
import { pageHero, panelHead } from '../../components/pageHero.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (message, type = 'info') => eventBus.emit('toast:show', { message, type });
const API = '/api/video';

async function api(path, opt = {}) {
  const r = await fetch(API + path, { credentials: 'same-origin', ...opt,
    headers: opt.body && !(opt.body instanceof Blob) ? { 'Content-Type': 'application/json', ...(opt.headers || {}) } : opt.headers });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.error || `Lỗi ${r.status}`); e.code = d.code; e.status = r.status; e.data = d; throw e; }
  return d;
}

const bytes = (b) => (b == null ? '—' : b < 1024 ** 2 ? `${(b / 1024).toFixed(0)} KB` : b < 1024 ** 3 ? `${(b / 1024 ** 2).toFixed(1)} MB` : `${(b / 1024 ** 3).toFixed(2)} GB`);
const dur = (s) => { if (s == null) return '—'; s = Math.round(s); const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); const x = s % 60; return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${m}:${String(x).padStart(2, '0')}`; };
const etaTxt = (s) => (s == null ? null : s < 60 ? `khoảng ${Math.max(1, Math.round(s))} giây` : s < 3600 ? `khoảng ${Math.round(s / 60)} phút` : `khoảng ${(s / 3600).toFixed(1)} giờ`);
const when = (t) => (t ? new Date(t * 1000).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');
const left = (t) => { if (!t) return ''; const s = t - Date.now() / 1000; return s <= 0 ? 'đã hết hạn' : s < 3600 ? `còn ${Math.round(s / 60)} phút` : s < 86400 ? `còn ${Math.round(s / 3600)} giờ` : `còn ${Math.round(s / 86400)} ngày`; };
const fps = (f) => (f == null ? '—' : `${Number(f).toLocaleString('vi-VN', { maximumFractionDigits: 3 })} fps`);
const res = (w, h) => (w ? `${w}×${h}` : '—');

const STAGES = [['queued', 'Chờ xử lý'], ['preparing', 'Chuẩn bị model'], ['processing', 'Xử lý video'], ['encoding', 'Mã hoá'], ['done', 'Hoàn tất']];
const STAGE_IDX = { queued: 0, preparing: 1, loading: 1, processing: 2, encoding: 3, verifying: 3, done: 4 };
const STATUS = { queued: ['Chờ xử lý', 'warn'], running: ['Đang chạy', 'run'], completed: ['Hoàn tất', 'ok'], failed: ['Lỗi', 'bad'], cancelled: ['Đã huỷ', ''] };
const GROUPS = { decompress: 'Khử vỡ hình do nén', denoise: 'Khử nhiễu', deblur: 'Khử nhoè' };

export const videoModule = {
  id: 'video',
  name: 'Video Workspace',
  route: '/video',
  icon: '🎬',
  category: 'Video AI',
  description: 'Tăng độ phân giải, khử nhiễu, phục hồi video nén và nội suy fps bằng REAL-Video-Enhancer trên GPU riêng; có xử lý thử và so sánh trước/sau.',
  status: 'active',

  s: null,

  unmount() {
    if (!this.s) return;
    clearTimeout(this.s.poll);
    this.s.uploadAbort?.abort();
    this.s.cmp?.stop?.();
    this.s = null;
  },

  async render(el) {
    this.unmount();
    if (!document.querySelector('link[data-video-css]')) {
      const l = document.createElement('link');
      l.rel = 'stylesheet'; l.href = '/styles/video.css?v=1'; l.dataset.videoCss = '1';
      document.head.appendChild(l);
    }
    const s = (this.s = { el, status: null, videos: [], jobs: [], cur: null, conf: { upscale: null, interpolate: null, factor: 2, restore: [], scene_detect: 'pyscenedetect' }, plan: null, planErr: null, preset: null });
    el.innerHTML = `
      ${pageHero(this, {
        title: 'Video <span class="thin">Workspace</span>',
        sub: 'Tải video lên, chọn tăng độ phân giải, phục hồi hoặc làm mượt fps. Xử lý bằng các model của REAL-Video-Enhancer trên GPU máy chủ, có xử lý thử một đoạn ngắn và so sánh trước/sau.',
        word: 'Video',
        meta: ['GPU riêng', 'Xử lý thử 10 giây', 'So sánh trước/sau'],
      })}
      <div class="mp-body vw" id="vw">
        <div class="vw-note" id="vw-note" hidden></div>
        <div class="vw-top">
          <div class="mp-panel vw-lib">
            ${panelHead('01', 'Video', 'của bạn')}
            <label class="vw-drop" id="vw-drop" tabindex="0">
              <input type="file" id="vw-file" accept="video/*,.mkv,.mov,.mp4,.webm,.avi,.m4v,.ts,.mts" hidden />
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 16V4"/><path d="m6 10 6-6 6 6"/><path d="M4 20h16"/></svg>
              <b>Kéo thả video vào đây</b><span>hoặc bấm để chọn file</span><small id="vw-limits"></small>
            </label>
            <div class="vw-upload" id="vw-upload" hidden></div>
            <div class="vw-list" id="vw-videos"></div>
            <div class="vw-usage" id="vw-usage"></div>
          </div>
          <div class="mp-panel vw-main">
            ${panelHead('02', 'Video gốc', '', '<span class="vw-sub" id="vw-curname"></span>')}
            <div id="vw-player" class="vw-player"><div class="vw-empty">Chọn hoặc tải lên một video để bắt đầu</div></div>
            <div id="vw-info"></div>
          </div>
        </div>
        <div class="mp-panel vw-settings" id="vw-settings">
          ${panelHead('03', 'Thông số', 'xử lý')}
          <div id="vw-form"><div class="vw-empty">Chọn video để cấu hình</div></div>
        </div>
        <div class="mp-panel">
          ${panelHead('04', 'Hàng đợi', '& kết quả', '<span class="vw-sub" id="vw-qstat"></span>')}
          <div id="vw-jobs" class="vw-jobs"></div>
        </div>
        <div class="vw-legal" id="vw-legal"></div>
      </div>`;
    this.bindUpload();
    await this.refresh(true);
  },

  // ── Dữ liệu ──
  async refresh(first = false) {
    const s = this.s;
    if (!s) return;
    try {
      const [st, v, j] = await Promise.all([api('/status'), api('/videos'), api('/jobs')]);
      if (!this.s) return;
      s.status = st; s.videos = v.videos; s.jobs = j.jobs;
      this.renderStatus();
      this.renderVideos();
      this.renderJobs();
      if (first && s.videos.length && !s.cur) this.select(s.videos[0].id);
      else if (first) this.renderForm();
    } catch (e) {
      s.el.querySelector('#vw-note').hidden = false;
      s.el.querySelector('#vw-note').innerHTML = `<b>Không tải được Video Workspace:</b> ${esc(e.message)}`;
    }
    this.schedule();
  },

  schedule() {
    const s = this.s;
    if (!s) return;
    clearTimeout(s.poll);
    const active = s.jobs.some((j) => ['queued', 'running'].includes(j.status)) || s.videos.some((v) => v.info.proxy === 'pending') || s.status?.checking;
    s.poll = setTimeout(() => this.pollJobs(), active ? 2000 : 15000);
  },

  async pollJobs() {
    const s = this.s;
    if (!s) return;
    try {
      const prev = Object.fromEntries(s.jobs.map((j) => [j.id, j.status]));
      const [{ jobs }, vids] = await Promise.all([api('/jobs'), s.videos.some((v) => v.info.proxy === 'pending') ? api('/videos') : null]);
      if (!this.s) return;
      s.jobs = jobs;
      jobs.forEach((j) => {
        if (prev[j.id] && prev[j.id] !== j.status && j.status === 'completed') toast(`Xong: ${j.preview ? 'bản thử' : 'video'} ${res(j.output?.video?.width, j.output?.video?.height)}`, 'success');
        if (prev[j.id] && prev[j.id] !== j.status && j.status === 'failed') toast(`Job lỗi: ${j.error_message || ''}`, 'error');
      });
      if (vids) { s.videos = vids.videos; this.renderVideos(); if (s.cur) { const c = s.videos.find((v) => v.id === s.cur.id); if (c && c.info.proxy !== s.cur.info.proxy) { s.cur = c; this.renderPlayer(); } } }
      if (s.status?.checking) { s.status = await api('/status'); this.renderStatus(); this.renderForm(); }
      this.renderJobs();
    } catch { /* thử lại ở nhịp sau */ }
    this.schedule();
  },

  renderStatus() {
    const s = this.s;
    const st = s.status;
    const note = s.el.querySelector('#vw-note');
    const L = st.limits;
    s.el.querySelector('#vw-limits').textContent = `Tối đa ${bytes(L.max_upload_mb * 1024 ** 2)}, ${dur(L.max_duration_s)} · lưu ${L.retention_hours} giờ`;
    s.el.querySelector('#vw-usage').innerHTML = `Đang dùng ${bytes(st.usage_bytes)} / ${L.quota_per_user_gb} GB · video và kết quả tự xoá sau ${L.retention_hours} giờ`;
    if (st.checking) { note.hidden = false; note.className = 'vw-note'; note.innerHTML = 'Đang kiểm tra GPU và backend xử lý video…'; }
    else if (!st.ready) { note.hidden = false; note.className = 'vw-note bad'; note.innerHTML = `<b>Máy xử lý video chưa sẵn sàng.</b> ${esc(st.problems.join('; '))}. Bạn vẫn tải lên và xem thông tin video được.`; }
    else note.hidden = true;
    s.el.querySelector('#vw-qstat').textContent = `Máy chủ: ${st.queue.running} đang chạy · ${st.queue.queued} đang chờ · ${st.limits.gpu_concurrency} job/GPU${st.hardware.gpus?.length ? ` · ${st.hardware.gpus.join(', ')}` : ''}`;
    s.el.querySelector('#vw-legal').innerHTML = `Xử lý bằng <a href="${esc(st.license.source)}" target="_blank" rel="noopener">REAL-Video-Enhancer</a>
      (AGPL-3.0, mã nguồn${st.license.commit ? ` commit <code>${esc(st.license.commit.slice(0, 10))}</code>` : ''}, không sửa đổi) · model của các tác giả ghi trong từng lựa chọn;
      model đánh dấu <b>NC</b> chỉ dùng phi thương mại.`;
  },

  // ── Tải lên theo phần ──
  bindUpload() {
    const s = this.s;
    const drop = s.el.querySelector('#vw-drop');
    const input = s.el.querySelector('#vw-file');
    input.onchange = () => { if (input.files[0]) this.upload(input.files[0]); input.value = ''; };
    ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('on'); }));
    ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('on'); }));
    drop.addEventListener('drop', (e) => { const f = e.dataTransfer.files[0]; if (f) this.upload(f); });
    drop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  },

  async upload(file) {
    const s = this.s;
    if (s.uploading) return toast('Đang tải một file khác', 'info');
    const box = s.el.querySelector('#vw-upload');
    const ctl = (s.uploadAbort = new AbortController());
    s.uploading = true;
    box.hidden = false;
    const show = (p, txt) => { box.innerHTML = `<div class="vw-up-row"><b>${esc(file.name)}</b><button class="btn btn-secondary btn-xs" id="vw-up-x">Huỷ</button></div>
      <div class="vw-bar"><div style="width:${p}%"></div></div><small>${txt}</small>`; box.querySelector('#vw-up-x').onclick = () => ctl.abort(); };
    let up;
    try {
      show(0, 'Bắt đầu tải lên…');
      up = await api('/uploads', { method: 'POST', body: JSON.stringify({ name: file.name, size: file.size }) });
      let off = 0;
      const t0 = performance.now();
      while (off < file.size) {
        const chunk = file.slice(off, off + up.chunk_size);
        let ok = false;
        for (let attempt = 0; attempt < 4 && !ok; attempt++) {
          try {
            const r = await fetch(`${API}/uploads/${up.upload_id}?offset=${off}`, { method: 'PUT', body: chunk, credentials: 'same-origin', signal: ctl.signal });
            const d = await r.json().catch(() => ({}));
            if (r.status === 409 && d.received != null) { off = d.received; ok = true; break; }
            if (!r.ok) throw new Error(d.error || `Lỗi ${r.status}`);
            off = d.received; ok = true;
          } catch (e) {
            if (ctl.signal.aborted) throw e;
            if (attempt === 3) throw e;
            await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
          }
        }
        const sp = off / ((performance.now() - t0) / 1000);
        show((off / file.size) * 100, `${bytes(off)} / ${bytes(file.size)} · ${bytes(sp)}/s · còn ${etaTxt((file.size - off) / Math.max(1, sp)) || '…'}`);
      }
      show(100, 'Đang phân tích video (ffprobe)…');
      const d = await api(`/uploads/${up.upload_id}/complete`, { method: 'POST' });
      toast('Đã tải lên và phân tích video', 'success');
      box.hidden = true;
      await this.refresh();
      this.select(d.video.id);
    } catch (e) {
      if (up && ctl.signal.aborted) fetch(`${API}/uploads/${up.upload_id}`, { method: 'DELETE', credentials: 'same-origin' }).catch(() => {});
      box.innerHTML = `<div class="vw-err">${ctl.signal.aborted ? 'Đã huỷ tải lên' : esc(e.message)}</div>`;
      if (!ctl.signal.aborted) toast(e.message, 'error');
    } finally {
      if (this.s) { s.uploading = false; s.uploadAbort = null; }
    }
  },

  // ── Thư viện & video đang chọn ──
  renderVideos() {
    const s = this.s;
    const box = s.el.querySelector('#vw-videos');
    box.innerHTML = s.videos.length ? s.videos.map((v) => `<button class="vw-item ${s.cur?.id === v.id ? 'on' : ''}" data-v="${v.id}">
        <b>${esc(v.name)}</b><small>${res(v.info.video.display_width, v.info.video.display_height)} · ${fps(v.info.video.fps)} · ${dur(v.info.duration)} · ${bytes(v.size)}</small>
        <small class="dim">${left(v.expires_at)}</small></button>`).join('')
      : '<div class="vw-empty sm">Chưa có video nào</div>';
    box.querySelectorAll('[data-v]').forEach((b) => (b.onclick = () => this.select(b.dataset.v)));
  },

  select(id) {
    const s = this.s;
    s.cur = s.videos.find((v) => v.id === id) || null;
    s.plan = null;
    this.renderVideos();
    this.renderPlayer();
    this.renderForm();
  },

  renderPlayer() {
    const s = this.s;
    const v = s.cur;
    const box = s.el.querySelector('#vw-player');
    s.el.querySelector('#vw-curname').textContent = v ? v.name : '';
    if (!v) { box.innerHTML = '<div class="vw-empty">Chọn hoặc tải lên một video để bắt đầu</div>'; s.el.querySelector('#vw-info').innerHTML = ''; return; }
    const i = v.info;
    const canPlay = i.playable || i.proxy === 'ready';
    box.innerHTML = canPlay ? `<video id="vw-src" controls preload="metadata" playsinline src="${API}/videos/${v.id}/file"></video>
        ${!i.playable ? '<div class="vw-tag">Bản xem trước H.264 — xử lý dùng file gốc</div>' : ''}`
      : `<div class="vw-empty">${i.proxy === 'pending' ? 'Trình duyệt không phát được định dạng gốc — đang tạo bản xem trước…' : 'Trình duyệt không phát được định dạng này; vẫn xử lý được bình thường.'}</div>`;
    const V = i.video;
    const A = i.audio;
    const rows = [
      ['Độ phân giải', `${res(V.width, V.height)}${V.display_width !== V.width || V.display_height !== V.height ? ` → hiển thị ${res(V.display_width, V.display_height)}` : ''}`],
      ['Khung hình', `${fps(V.fps)}${V.vfr ? ' <span class="vw-chip warn">fps biến thiên</span>' : ''}${V.frames ? ` · ${V.frames.toLocaleString('vi-VN')} khung` : ''}`],
      ['Thời lượng', dur(i.duration)],
      ['Dung lượng', `${bytes(v.size)}${i.bitrate ? ` · ${(i.bitrate / 1e6).toFixed(1)} Mb/s` : ''}`],
      ['Mã hoá hình', `${esc(V.codec)}${V.profile ? ` (${esc(V.profile)})` : ''} · ${esc(V.pix_fmt)} · ${V.bit_depth}-bit`],
      ['Màu', `${esc(V.color_primaries || 'không ghi')} / ${esc(V.color_transfer || 'không ghi')}${V.hdr ? ' <span class="vw-chip warn">HDR</span>' : ''}`],
      ['Âm thanh', A ? `${esc(A.codec)} · ${A.channels} kênh${A.sample_rate ? ` · ${(A.sample_rate / 1000).toFixed(1)} kHz` : ''}${A.count > 1 ? ` · ${A.count} luồng` : ''}` : 'Không có'],
      ['Khác', [V.rotation ? `xoay ${V.rotation}°` : '', V.sar !== '1:1' ? `SAR ${esc(V.sar)}` : '', i.subtitles ? `${i.subtitles} phụ đề` : '', esc((i.container || '').split(',')[0])].filter(Boolean).join(' · ')],
    ];
    s.el.querySelector('#vw-info').innerHTML = `<dl class="vw-kv">${rows.map(([k, x]) => `<dt>${k}</dt><dd>${x}</dd>`).join('')}</dl>
      <div class="vw-row"><small class="dim">Lưu đến ${when(v.expires_at)} (${left(v.expires_at)})</small><button class="btn btn-secondary btn-xs" id="vw-del">Xoá video</button></div>`;
    s.el.querySelector('#vw-del').onclick = async () => {
      if (!confirm(`Xoá video "${v.name}"? Các job đang chờ của video này sẽ bị huỷ.`)) return;
      try { await api(`/videos/${v.id}`, { method: 'DELETE' }); s.cur = null; await this.refresh(); this.renderPlayer(); this.renderForm(); } catch (e) { toast(e.message, 'error'); }
    };
  },

  // ── Thông số xử lý ──
  models(kind) { return (this.s.status?.models || []).filter((m) => m.kind === kind); },

  renderForm() {
    const s = this.s;
    const box = s.el.querySelector('#vw-form');
    if (!s.cur || !s.status) { box.innerHTML = '<div class="vw-empty">Chọn video để cấu hình</div>'; return; }
    const c = s.conf;
    const st = s.status;
    const opt = (m) => `<option value="${m.id}" ${c.upscale === m.id || c.interpolate === m.id ? 'selected' : ''}>${esc(m.label)}${m.noncommercial ? ' · NC' : ''}${m.installed ? '' : ' · tải lần đầu'}</option>`;
    const up = this.models('upscale');
    const it = this.models('interpolate');
    const rs = this.models('restore');
    const groups = [...new Set(rs.map((m) => m.group))];
    box.innerHTML = `
      <div class="vw-presets">${st.presets.map((p) => `<button class="vw-preset ${s.preset === p.id ? 'on' : ''}" data-p="${p.id}"><b>${esc(p.label)}</b><small>${esc(p.desc)}</small></button>`).join('')}</div>
      <div class="vw-form">
        <fieldset><legend>Tăng độ phân giải</legend>
          <select id="f-up"><option value="">Không tăng</option>${up.map(opt).join('')}</select>
          <small class="dim" id="f-up-note">${esc(up.find((m) => m.id === c.upscale)?.best_for || 'Hệ số do model quyết định (2× hoặc 4×)')}</small></fieldset>
        <fieldset><legend>Nội suy khung hình (làm mượt)</legend>
          <div class="vw-inline"><select id="f-it"><option value="">Không nội suy</option>${it.map(opt).join('')}</select>
          <select id="f-fac" ${c.interpolate ? '' : 'disabled'}>${st.factors.map((f) => `<option value="${f}" ${c.factor === f ? 'selected' : ''}>×${f}${s.cur.info.video.fps ? ` → ${(s.cur.info.video.fps * f).toLocaleString('vi-VN', { maximumFractionDigits: 2 })} fps` : ''}</option>`).join('')}</select></div>
          <small class="dim">Chỉ hệ số nguyên: thời lượng giữ nguyên, không thành slow-motion</small>
          <label class="vw-lbl">Phát hiện chuyển cảnh <select id="f-sd" ${c.interpolate ? '' : 'disabled'}>${Object.entries(st.scene_detect).map(([k, l]) => `<option value="${k}" ${c.scene_detect === k ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label></fieldset>
        <fieldset><legend>Phục hồi (trước khi tăng độ phân giải)</legend>
          ${groups.map((g) => `<label class="vw-lbl">${esc(GROUPS[g] || g)} <select data-g="${g}"><option value="">Không</option>${rs.filter((m) => m.group === g).map((m) => `<option value="${m.id}" ${c.restore.includes(m.id) ? 'selected' : ''}>${esc(m.label)}${m.installed ? '' : ' · tải lần đầu'}</option>`).join('')}</select></label>`).join('')}
          <small class="dim" id="f-rs-note">${esc(rs.filter((m) => c.restore.includes(m.id)).map((m) => m.best_for).join(' · ') || 'Khử vỡ hình, khử nhiễu, khử nhoè — 1×, không đổi kích thước')}</small></fieldset>
      </div>
      <div class="vw-plan" id="vw-plan"></div>
      <div class="vw-actions">
        <label class="vw-lbl">Xử lý thử ${st.limits.preview_seconds} giây từ <input type="number" id="f-start" min="0" step="0.5" value="0" /> giây <button class="btn btn-secondary btn-xs" id="f-now" title="Lấy thời điểm đang phát">⟲ vị trí đang phát</button></label>
        <div class="vw-btns"><button class="btn btn-secondary" id="f-preview">Xử lý thử</button><button class="btn btn-primary" id="f-run">Xử lý toàn bộ</button></div>
      </div>`;
    const set = (patch) => { Object.assign(c, patch); s.preset = null; this.renderForm(); };
    box.querySelectorAll('[data-p]').forEach((b) => (b.onclick = () => {
      const p = st.presets.find((x) => x.id === b.dataset.p);
      Object.assign(c, { upscale: p.upscale || null, interpolate: p.interpolate || null, factor: p.factor || 2, restore: [...(p.restore || [])] });
      s.preset = p.id;
      this.renderForm();
    }));
    box.querySelector('#f-up').onchange = (e) => set({ upscale: e.target.value || null });
    box.querySelector('#f-it').onchange = (e) => set({ interpolate: e.target.value || null });
    box.querySelector('#f-fac').onchange = (e) => set({ factor: Number(e.target.value) });
    box.querySelector('#f-sd').onchange = (e) => set({ scene_detect: e.target.value });
    box.querySelectorAll('[data-g]').forEach((sel) => (sel.onchange = () => {
      const g = sel.dataset.g;
      const others = c.restore.filter((id) => rs.find((m) => m.id === id)?.group !== g);
      set({ restore: sel.value ? [...others, sel.value] : others });
    }));
    box.querySelector('#f-now').onclick = () => { const v = s.el.querySelector('#vw-src'); if (v) box.querySelector('#f-start').value = v.currentTime.toFixed(1); };
    box.querySelector('#f-preview').onclick = () => this.submit(true);
    box.querySelector('#f-run').onclick = () => this.submit(false);
    this.loadPlan();
  },

  config(preview) {
    const s = this.s;
    const c = s.conf;
    const out = { restore: c.restore };
    if (c.upscale) out.upscale = c.upscale;
    if (c.interpolate) Object.assign(out, { interpolate: c.interpolate, factor: c.factor, scene_detect: c.scene_detect });
    if (preview) out.preview = { start: Number(s.el.querySelector('#f-start')?.value || 0) };
    return out;
  },

  async loadPlan() {
    const s = this.s;
    const box = s.el.querySelector('#vw-plan');
    const c = s.conf;
    const btns = [s.el.querySelector('#f-preview'), s.el.querySelector('#f-run')];
    if (!c.upscale && !c.interpolate && !c.restore.length) {
      box.innerHTML = '<div class="vw-empty sm">Chọn một preset hoặc ít nhất một thao tác</div>';
      btns.forEach((b) => (b.disabled = true));
      return;
    }
    const key = JSON.stringify([s.cur.id, this.config(false)]);
    s.planKey = key;
    box.innerHTML = '<div class="vw-empty sm">Đang tính thông số đầu ra…</div>';
    try {
      const { plan } = await api('/plan', { method: 'POST', body: JSON.stringify({ video_id: s.cur.id, config: this.config(false) }) });
      if (!this.s || s.planKey !== key) return;
      const o = plan.output;
      const name = (id) => s.status.models.find((m) => m.id === id)?.label || id;
      const steps = [...plan.restore.map(name), plan.interpolate ? `${name(plan.interpolate)} ×${plan.factor}` : null, plan.upscale ? name(plan.upscale) : null].filter(Boolean);
      box.innerHTML = `<div class="vw-plan-grid">
          <div><small>Đầu vào</small><b>${res(plan.input.width, plan.input.height)}</b><span>${fps(plan.input.fps)}</span></div>
          <div class="arrow">→</div>
          <div><small>Đầu ra</small><b>${res(o.width, o.height)}</b><span>${fps(o.fps)}</span></div>
          <div><small>Thời lượng</small><b>${dur(plan.duration)}</b><span>${o.frames.toLocaleString('vi-VN')} khung</span></div>
          <div><small>Định dạng</small><b>MP4 ${o.codec === 'hevc' ? 'H.265 10-bit' : 'H.264'}</b><span>${o.audio === 'copy' ? 'giữ nguyên âm thanh' : o.audio === 'aac' ? 'âm thanh → AAC' : 'không có âm thanh'}</span></div>
        </div>
        <div class="vw-steps-txt">Thứ tự xử lý: ${steps.map(esc).join(' → ')}${plan.scene_detect ? ` · chuyển cảnh: ${esc(s.status.scene_detect[plan.scene_detect])}` : ''}${plan.normalize.length ? ` · chuẩn hoá trước: ${esc(plan.normalize.join(', '))}` : ''}</div>
        ${plan.warnings.map((w) => `<div class="vw-warn">⚠ ${esc(w)}</div>`).join('')}`;
      btns.forEach((b) => (b.disabled = !s.status.ready));
      if (!s.status.ready) box.insertAdjacentHTML('beforeend', '<div class="vw-warn">Máy xử lý chưa sẵn sàng — chưa tạo job được.</div>');
    } catch (e) {
      if (!this.s || s.planKey !== key) return;
      box.innerHTML = `<div class="vw-err">${esc(e.message)}</div>`;
      btns.forEach((b) => (b.disabled = true));
    }
  },

  async submit(preview) {
    const s = this.s;
    try {
      await api('/jobs', { method: 'POST', body: JSON.stringify({ video_id: s.cur.id, config: this.config(preview) }) });
      toast(preview ? 'Đã thêm job xử lý thử vào hàng đợi' : 'Đã thêm job vào hàng đợi', 'success');
      const j = await api('/jobs');
      s.jobs = j.jobs;
      this.renderJobs();
      this.schedule();
      s.el.querySelector('#vw-jobs').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) { toast(e.message, 'error'); }
  },

  // ── Hàng đợi & kết quả ──
  renderJobs() {
    const s = this.s;
    const box = s.el.querySelector('#vw-jobs');
    if (!s.jobs.length) { box.innerHTML = '<div class="vw-empty sm">Chưa có job nào. Kết quả xuất hiện ở đây kèm nút xem, so sánh và tải xuống.</div>'; return; }
    const open = s.openCmp;
    box.innerHTML = s.jobs.map((j) => {
      const v = s.videos.find((x) => x.id === j.video_id);
      const [lbl, tone] = STATUS[j.status] || [j.status, ''];
      const si = j.status === 'completed' ? 4 : STAGE_IDX[j.stage] ?? 0;
      const failed = ['failed', 'cancelled'].includes(j.status);
      const p = j.plan || {};
      const o = j.output?.video;
      const prog = j.status === 'running' && j.progress != null
        ? `<div class="vw-bar"><div style="width:${j.progress}%"></div></div><small>${j.progress.toLocaleString('vi-VN')}% · ${j.frames_done?.toLocaleString('vi-VN')}/${j.frames_total?.toLocaleString('vi-VN')} khung${j.fps ? ` · ${j.fps} khung/giây` : ''} · ${j.eta_s != null ? `còn ${etaTxt(j.eta_s)}` : 'chưa ước lượng được thời gian còn lại'}</small>`
        : j.status === 'running' ? `<div class="vw-bar ind"><div></div></div><small>${esc(j.message || '')} · chưa có số liệu tiến độ</small>`
          : j.status === 'queued' ? `<small>${esc(j.message || 'Đang chờ')}</small>` : '';
      return `<div class="vw-job ${j.status}" data-j="${j.id}">
        <div class="vw-job-h"><span class="vw-chip ${tone}">${lbl}</span>${j.preview ? '<span class="vw-chip">Thử ' + dur(p.duration) + '</span>' : ''}
          <b>${esc(v?.name || 'video đã xoá')}</b><small class="dim">${when(j.created_at)}</small></div>
        <div class="vw-job-cfg">${res(p.input?.width, p.input?.height)} @ ${fps(p.input?.fps)} → <b>${res(p.output?.width, p.output?.height)} @ ${fps(p.output?.fps)}</b> · ${esc(Object.keys(j.models || {}).map((id) => s.status?.models.find((m) => m.id === id)?.label || id).join(' + '))}</div>
        ${failed ? '' : `<ol class="vw-stages">${STAGES.map(([k, l], i) => `<li class="${i < si ? 'done' : i === si ? (j.status === 'completed' ? 'done' : 'now') : ''}">${l}</li>`).join('')}</ol>`}
        ${prog}
        ${j.status === 'failed' ? `<div class="vw-err">${esc(j.error_message || 'Lỗi')}${j.error_code ? ` <small>(${esc(j.error_code)})</small>` : ''}</div>` : ''}
        ${j.status === 'completed' && o ? `<div class="vw-out">Đầu ra: <b>${res(o.width, o.height)}</b> · ${fps(o.fps)} · ${dur(j.output.duration)} · ${esc(o.codec)}${j.output.audio ? ` + ${esc(j.output.audio.codec)}` : ''} · ${bytes(j.output_size)} · ${j.has_result ? `lưu ${left(j.expires_at)}` : 'đã hết hạn'}</div>` : ''}
        <div class="vw-job-a">
          ${['queued', 'running'].includes(j.status) ? `<button class="btn btn-secondary btn-xs" data-a="cancel" ${j.cancel_requested ? 'disabled' : ''}>${j.cancel_requested ? 'Đang huỷ…' : 'Huỷ'}</button>` : ''}
          ${j.status === 'completed' && j.has_result ? `<button class="btn btn-primary btn-xs" data-a="cmp">${open === j.id ? 'Đóng so sánh' : 'Xem & so sánh'}</button><a class="btn btn-secondary btn-xs" href="${API}/jobs/${j.id}/result?download=1">Tải xuống</a>` : ''}
          ${!['queued', 'running'].includes(j.status) ? '<button class="btn btn-secondary btn-xs vw-danger" data-a="del">Xoá</button>' : ''}
        </div>
        ${open === j.id ? '<div class="vw-cmp-host"></div>' : ''}
      </div>`;
    }).join('');
    box.querySelectorAll('[data-a]').forEach((b) => (b.onclick = () => this.jobAction(b.closest('[data-j]').dataset.j, b.dataset.a)));
    if (open) {
      const host = box.querySelector(`[data-j="${open}"] .vw-cmp-host`);
      if (host && !host.firstChild) this.compare(host, s.jobs.find((j) => j.id === open));
    }
  },

  async jobAction(id, a) {
    const s = this.s;
    try {
      if (a === 'cancel') await api(`/jobs/${id}/cancel`, { method: 'POST' });
      if (a === 'del') { if (!confirm('Xoá job và file kết quả?')) return; await api(`/jobs/${id}`, { method: 'DELETE' }); }
      if (a === 'cmp') { s.cmp?.stop?.(); s.openCmp = s.openCmp === id ? null : id; }
      const j = await api('/jobs');
      s.jobs = j.jobs;
      this.renderJobs();
      this.schedule();
    } catch (e) { toast(e.message, 'error'); }
  },

  // ── So sánh trước/sau: hai video chồng nhau, thanh kéo chia đôi, phát đồng bộ ──
  compare(host, j) {
    const s = this.s;
    const v = s.videos.find((x) => x.id === j.video_id);
    const offset = j.plan?.start || 0; // bản thử bắt đầu từ giây thứ "start" của video gốc
    const canSrc = v && (v.info.playable || v.info.proxy === 'ready');
    host.innerHTML = `<div class="vw-cmp" style="aspect-ratio:${j.output.video.width}/${j.output.video.height}">
        <video class="after" src="${API}/jobs/${j.id}/result" playsinline preload="auto"></video>
        ${canSrc ? `<video class="before" src="${API}/videos/${v.id}/file" playsinline muted preload="auto"></video>` : ''}
        <div class="vw-cmp-line"><span>Gốc</span><span>Sau xử lý</span></div>
        <input type="range" class="vw-cmp-split" min="0" max="100" value="50" aria-label="Vị trí chia so sánh" ${canSrc ? '' : 'hidden'}/>
      </div>
      <div class="vw-cmp-bar"><button class="btn btn-secondary btn-xs" data-c="play">▶ Phát</button>
        <input type="range" class="vw-cmp-seek" min="0" max="1000" value="0" aria-label="Tua"/>
        <span class="vw-cmp-t">0:00</span>
        <button class="btn btn-secondary btn-xs" data-c="slow" title="Xem chậm để thấy rõ khung nội suy">0.25×</button>
        <button class="btn btn-secondary btn-xs" data-c="full">Toàn màn hình</button></div>
      ${canSrc ? `<small class="dim">Kéo thanh trên video để so sánh. Bên trái là video gốc (âm thanh tắt), bên phải là kết quả; thời điểm được đồng bộ${offset ? ` (bản thử bắt đầu ở giây ${offset.toFixed(1)} của video gốc)` : ''}.</small>` : '<small class="dim">Không phát được video gốc trên trình duyệt — chỉ xem kết quả.</small>'}`;
    const after = host.querySelector('video.after');
    const before = host.querySelector('video.before');
    const wrap = host.querySelector('.vw-cmp');
    const split = host.querySelector('.vw-cmp-split');
    const seek = host.querySelector('.vw-cmp-seek');
    const tEl = host.querySelector('.vw-cmp-t');
    const setSplit = () => { if (before) before.style.clipPath = `inset(0 ${100 - split.value}% 0 0)`; wrap.style.setProperty('--x', `${split.value}%`); };
    split.oninput = setSplit;
    setSplit();
    const sync = () => {
      if (!before) return;
      const want = after.currentTime + offset;
      if (Math.abs(before.currentTime - want) > 0.08) before.currentTime = want;
      before.playbackRate = after.playbackRate;
    };
    let raf;
    const tick = () => {
      if (after.duration) seek.value = String((after.currentTime / after.duration) * 1000);
      tEl.textContent = `${dur(after.currentTime)} / ${dur(after.duration)}`;
      if (before && !after.paused && Math.abs(before.currentTime - (after.currentTime + offset)) > 0.12) sync();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    const playBtn = host.querySelector('[data-c="play"]');
    after.onplay = () => { sync(); before?.play().catch(() => {}); playBtn.textContent = '❚❚ Dừng'; };
    after.onpause = () => { before?.pause(); sync(); playBtn.textContent = '▶ Phát'; };
    after.onseeked = sync;
    after.onended = () => { before?.pause(); };
    playBtn.onclick = () => {
      if (!after.paused) return after.pause();
      after.play().catch((e) => toast(`Không phát được video: ${e.message}`, 'error'));
    };
    seek.oninput = () => { if (after.duration) { after.currentTime = (seek.value / 1000) * after.duration; sync(); } };
    host.querySelector('[data-c="slow"]').onclick = (e) => { after.playbackRate = after.playbackRate === 1 ? 0.25 : 1; e.target.textContent = after.playbackRate === 1 ? '0.25×' : '1×'; sync(); };
    host.querySelector('[data-c="full"]').onclick = () => wrap.requestFullscreen?.();
    s.cmp = { stop: () => { cancelAnimationFrame(raf); after.pause(); before?.pause(); } };
  },
};
