/**
 * MonaliMeow — VoxCPM2 Voice AI Module
 * Integrated with Background JobTracker & Desktop Notifications
 * Runs ENTIRELY inside https://sonxit.io.vn/VoxCPM
 */

import { jobTracker } from '../../services/jobTracker.js';
import { eventBus } from '../../stores/eventBus.js';

export const voxcpmModule = {
  id: 'voxcpm',
  name: 'VoxCPM Voice AI',
  route: '/VoxCPM',
  icon: '🔊',
  category: 'Speech AI',
  description: 'VoxCPM2 (2B) — 30 ngôn ngữ, Voice Design & Cloning, 48kHz WAV. Chạy trực tiếp trong trang.',
  status: 'active',

  _state: { refFile: null, busy: false, unsubscribe: null },

  render(el) {
    this._state.refFile = null;
    this._state.busy    = false;

    el.innerHTML = `
    <div class="workspace-page-header">
      <div class="page-title-group">
        <h1>🔊 VoxCPM2 Voice Design &amp; Cloning Engine</h1>
        <p>Tạo giọng nói 48kHz đa ngôn ngữ. Sinh giọng mới từ mô tả hoặc nhân bản giọng nói từ file audio.</p>
      </div>
    </div>

    <div class="workspace-two-col">

      <!-- LEFT: Settings -->
      <div class="panel-card">
        <h3 class="panel-title">🎛️ Cài Đặt</h3>

        <div class="form-group">
          <label class="form-label">Chế độ</label>
          <select class="form-select" id="vox-mode">
            <option value="design" selected>🎨 Voice Design — Tạo giọng từ mô tả</option>
            <option value="cloning">🎤 Voice Cloning — Nhân bản từ audio</option>
            <option value="ultimate">🎙️ Ultimate Clone — Kế thừa hoàn toàn</option>
          </select>
        </div>

        <div class="form-group" id="vox-group-prompt">
          <label class="form-label">Mô tả giọng nói (Control Prompt)</label>
          <textarea class="form-textarea" id="vox-prompt" rows="3"
            placeholder="Ví dụ: Giọng nam trẻ, truyền cảm, nhịp nhàng, năng lượng tích cực..."></textarea>
        </div>

        <div class="form-group" id="vox-group-ref-text" style="display:none">
          <label class="form-label">Lời thoại trong audio tham chiếu</label>
          <textarea class="form-textarea" id="vox-ref-text" rows="2"
            placeholder="Nhập chính xác nội dung lời nói trong file audio tham chiếu (để trống nếu muốn AI tự nhận diện)..."></textarea>
        </div>

        <div class="form-group">
          <label class="form-label">Audio tham chiếu (cho Voice Cloning)</label>
          <input type="file" class="form-input" id="vox-ref-audio"
                 accept=".mp3,.wav,.m4a,.flac,.ogg,.webm" />
          <div id="vox-ref-name" style="font-size:0.75rem;color:var(--primary);margin-top:0.3rem;"></div>
          <div style="font-size:0.72rem; color:var(--text-muted); margin-top:0.35rem; line-height:1.35;">
            💡 <strong>Mẹo nhân bản giọng hay nhất:</strong> Chọn file audio ngắn khoảng 5–15 giây <em>chỉ có tiếng người nói</em> (tránh file bài hát dài hoặc có nhạc nền dạo đầu).
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">CFG Scale (1.0 – 5.0)</label>
          <input type="number" class="form-input" id="vox-cfg"
                 value="2.0" step="0.5" min="1.0" max="5.0" />
        </div>

        <div class="form-group">
          <label class="form-label">Mô hình</label>
          <select class="form-select" id="vox-model">
            <option value="voxcpm2-2b" selected>VoxCPM2 (2B · 30 langs · 48kHz)</option>
            <option value="voxcpm1.5">VoxCPM1.5 (Expressive SFT)</option>
          </select>
        </div>
      </div>

      <!-- RIGHT: Input + Output -->
      <div class="panel-card" style="display:flex;flex-direction:column;gap:1rem;">

        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
            <h3 class="panel-title" style="margin-bottom:0;">📝 Văn Bản Cần Đọc</h3>
            <button class="btn btn-secondary" id="btnInsertSampleText" style="font-size:0.75rem; padding:0.25rem 0.6rem;">💡 Văn bản mẫu</button>
          </div>
          <textarea class="form-textarea" id="vox-text" rows="6"
            placeholder="Nhập đoạn văn bản bạn muốn AI phát âm (Tiếng Việt, Anh, Trung, Nhật, Hàn...)"></textarea>
        </div>

        <button class="btn btn-primary" id="vox-btn" style="width:100%;font-size:1rem;padding:0.85rem;">
          ⚡ Tổng Hợp Giọng Nói AI
        </button>

        <!-- Progress -->
        <div id="vox-progress-wrap" style="display:none;">
          <div id="vox-progress-msg"
               style="font-size:0.85rem;font-weight:600;color:var(--primary);margin-bottom:0.5rem;">
            Đang xử lý...
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="vox-progress-bar" style="width:5%"></div>
          </div>
        </div>

        <!-- Audio Output -->
        <div>
          <h4 style="font-size:0.9rem;font-weight:700;color:var(--text-main);margin-bottom:0.6rem;">
            🔊 Kết Quả Âm Thanh
          </h4>
          <div id="vox-output"
               style="background:var(--bg-input);border:1px solid var(--border-color);
                      border-radius:var(--radius-md);padding:1.25rem;text-align:center;
                      font-size:0.85rem;color:var(--text-dim);">
            Chưa có âm thanh. Nhập văn bản và bấm "⚡ Tổng Hợp Giọng Nói AI".
          </div>
        </div>

      </div>
    </div>`;

    this._bind(el);
    this._restoreLatestJob(el);
  },

  _restoreLatestJob(el) {
    const latest = jobTracker.getLatestJobForModule('voxcpm');
    if (!latest) return;

    const progWrap = el.querySelector('#vox-progress-wrap');
    const progBar  = el.querySelector('#vox-progress-bar');
    const progMsg  = el.querySelector('#vox-progress-msg');
    const output   = el.querySelector('#vox-output');
    const btn      = el.querySelector('#vox-btn');

    if (latest.status === 'completed' && latest.result) {
      this._renderAudioResult(latest.result, output);
    } else if (latest.status === 'queued' || latest.status === 'processing') {
      this._state.busy = true;
      if (btn) btn.disabled = true;
      if (progWrap) progWrap.style.display = 'block';
      if (progBar)  progBar.style.width    = `${latest.progress || 10}%`;
      if (progMsg)  progMsg.textContent    = latest.message || 'Đang sinh giọng ngầm...';
    }

    this._state.unsubscribe = jobTracker.subscribe(job => {
      if (job.module !== 'voxcpm') return;

      if (job.status === 'processing' || job.status === 'queued') {
        this._state.busy = true;
        if (btn) btn.disabled = true;
        if (progWrap) progWrap.style.display = 'block';
        if (progBar)  progBar.style.width    = `${job.progress || 10}%`;
        if (progMsg)  progMsg.textContent    = job.message || 'Đang sinh giọng nói...';
      } else if (job.status === 'completed' && job.result) {
        this._state.busy = false;
        if (btn) btn.disabled = false;
        if (progWrap) progWrap.style.display = 'none';
        this._renderAudioResult(job.result, output);
      } else if (job.status === 'failed') {
        this._state.busy = false;
        if (btn) btn.disabled = false;
        if (progWrap) progWrap.style.display = 'none';
        output.innerHTML = `<div style="color:var(--rose);font-weight:600;">❌ Lỗi: ${job.message}</div>`;
      }
    });
  },

  _bind(el) {
    // Insert sample text button
    el.querySelector('#btnInsertSampleText')?.addEventListener('click', () => {
      const sample = "Thằng em tạo có lỗi, nhưng ở đây có thằng nào không có lỗi không? Ngay cả tao với mày cũng có lỗi!";
      el.querySelector('#vox-text').value = sample;
      eventBus.emit('toast:show', { message: 'Đã điền văn bản mẫu!' });
    });

    // Mode toggle
    el.querySelector('#vox-mode').addEventListener('change', e => {
      const v = e.target.value;
      el.querySelector('#vox-group-prompt').style.display   = v === 'ultimate' ? 'none' : 'block';
      el.querySelector('#vox-group-ref-text').style.display = v === 'ultimate' ? 'block' : 'none';
    });

    // Ref audio picker
    el.querySelector('#vox-ref-audio').addEventListener('change', e => {
      const f = e.target.files[0];
      if (f) {
        this._state.refFile = f;
        el.querySelector('#vox-ref-name').textContent =
          `🎵 ${f.name} (${(f.size / 1048576).toFixed(2)} MB)`;
      }
    });

    // Synthesize button
    el.querySelector('#vox-btn').addEventListener('click', () => this._synthesize(el));
  },

  async _synthesize(el) {
    if (this._state.busy) return;

    const text = el.querySelector('#vox-text').value.trim();
    if (!text) {
      eventBus.emit('toast:show', { message: 'Vui lòng nhập văn bản bạn muốn AI đọc!', type: 'error' });
      el.querySelector('#vox-text').focus();
      return;
    }

    const control    = el.querySelector('#vox-prompt').value.trim();
    const refText    = el.querySelector('#vox-ref-text').value.trim();
    const cfg        = parseFloat(el.querySelector('#vox-cfg').value) || 2.0;
    const mode       = el.querySelector('#vox-mode').value;

    const btn        = el.querySelector('#vox-btn');
    const progWrap   = el.querySelector('#vox-progress-wrap');
    const progBar    = el.querySelector('#vox-progress-bar');
    const progMsg    = el.querySelector('#vox-progress-msg');
    const output     = el.querySelector('#vox-output');

    this._state.busy = true;
    btn.disabled     = true;
    progWrap.style.display = 'block';
    progBar.style.width    = '5%';
    progMsg.textContent    = 'Đang gửi yêu cầu tới VoxCPM2 GPU Engine...';

    try {
      const fd = new FormData();
      fd.append('text',        text);
      fd.append('control',     mode === 'ultimate' ? '' : control);
      fd.append('prompt_text', mode === 'ultimate' ? refText : '');
      fd.append('cfg',         cfg);
      if (this._state.refFile) fd.append('ref_audio', this._state.refFile);

      const res = await fetch('/api/voxcpm/generate', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const { job_id } = await res.json();

      // Register with global jobTracker for background execution & notification
      jobTracker.trackJob({
        id: job_id,
        module: 'voxcpm',
        route: '/VoxCPM',
        title: `VoxCPM Giọng Nói AI ("${text.slice(0, 20)}...")`
      });

      eventBus.emit('toast:show', { message: '🚀 Tác vụ sinh giọng đang chạy ngầm! Bạn có thể chuyển trang.' });

    } catch (err) {
      this._state.busy = false;
      btn.disabled     = false;
      progWrap.style.display = 'none';
      output.innerHTML = `<div style="color:var(--rose);font-weight:600;">❌ Lỗi: ${err.message}</div>`;
      eventBus.emit('toast:show', { message: `❌ ${err.message}`, type: 'error' });
    }
  },

  _renderAudioResult(r, outputEl) {
    if (!outputEl || !r) return;
    const durStr = r.duration ? `${r.duration}s` : 'Hoàn tất!';
    outputEl.innerHTML = `
      <div style="color:var(--primary);font-weight:700;margin-bottom:0.75rem;">
        ✅ Hoàn tất! ${durStr} · ${r.sample_rate || 48000}Hz
      </div>
      <audio controls autoplay src="${r.audio_url}"
             style="width:100%;outline:none;margin-bottom:0.75rem;"></audio>
      <a href="${r.audio_url}" download="voxcpm_output.wav"
         class="btn btn-primary" style="text-decoration:none;display:inline-block;">
        📥 Tải WAV 48kHz
      </a>`;
  },

  unmount(el) {
    if (this._state.unsubscribe) {
      this._state.unsubscribe();
      this._state.unsubscribe = null;
    }
    el.innerHTML = '';
  }
};
