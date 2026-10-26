/**
 * MonaliMeow — VoxCPM2 Voice AI Module
 * Integrated with Background JobTracker & Desktop Notifications
 * Runs ENTIRELY inside https://sonxit.io.vn/VoxCPM
 */

import { jobTracker } from '../../services/jobTracker.js';
import { eventBus } from '../../stores/eventBus.js';
import { pageHero, panelHead, svgIcon } from '../../components/pageHero.js';

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
    ${pageHero(this, {
      title: 'Thiết kế <span class="thin">& nhân bản</span> giọng nói AI',
      sub: 'Tạo giọng nói 48kHz cho 30 ngôn ngữ. Mô tả giọng bạn muốn, hoặc đưa một đoạn audio ngắn để AI nhân bản đúng chất giọng đó.',
      word: 'Voice',
      meta: ['VoxCPM2 · 2B', '30 ngôn ngữ', 'WAV 48kHz'],
    })}

    <div class="mp-body">
      <div class="mp-grid">

        <div class="mp-panel">
          ${panelHead('01', 'Cài đặt', 'giọng nói')}

          <div class="form-group">
            <label class="form-label">Chế độ</label>
            <select class="form-select" id="vox-mode">
              <option value="design" selected>Voice Design — tạo giọng từ mô tả</option>
              <option value="cloning">Voice Cloning — nhân bản từ audio</option>
              <option value="ultimate">Ultimate Clone — kế thừa hoàn toàn</option>
            </select>
          </div>

          <div class="form-group" id="vox-group-prompt">
            <label class="form-label">Mô tả giọng nói</label>
            <textarea class="form-textarea" id="vox-prompt" rows="3"
              placeholder="Ví dụ: Giọng nam trẻ, truyền cảm, nhịp nhàng, năng lượng tích cực..."></textarea>
          </div>

          <div class="form-group" id="vox-group-ref-text" style="display:none">
            <label class="form-label">Lời thoại trong audio tham chiếu</label>
            <textarea class="form-textarea" id="vox-ref-text" rows="2"
              placeholder="Nhập đúng lời nói trong file tham chiếu (để trống để AI tự nhận diện)..."></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">Audio tham chiếu (cho nhân bản giọng)</label>
            <input type="file" class="form-input" id="vox-ref-audio" accept=".mp3,.wav,.m4a,.flac,.ogg,.webm" />
            <div id="vox-ref-name" style="font-size:12.5px;color:var(--primary);margin-top:8px;"></div>
            <div class="mp-hint">${svgIcon('bulb', 15, 2)}<span><b>Mẹo:</b> chọn đoạn 5–15 giây <em>chỉ có tiếng người nói</em>, tránh bài hát dài hoặc có nhạc nền.</span></div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1.4fr;gap:14px;">
            <div class="form-group">
              <label class="form-label">CFG Scale</label>
              <input type="number" class="form-input" id="vox-cfg" value="2.0" step="0.5" min="1.0" max="5.0" />
            </div>
            <div class="form-group">
              <label class="form-label">Mô hình</label>
              <select class="form-select" id="vox-model">
                <option value="voxcpm2-2b" selected>VoxCPM2 · 2B · 48kHz</option>
                <option value="voxcpm1.5">VoxCPM1.5 · Expressive</option>
              </select>
            </div>
          </div>
        </div>

        <div class="mp-panel flex">
          ${panelHead('02', 'Văn bản', 'cần đọc', `<button class="btn btn-secondary btn-sm" id="btnInsertSampleText">${svgIcon('bulb', 14, 2)} Văn bản mẫu</button>`)}

          <textarea class="form-textarea" id="vox-text" rows="8"
            placeholder="Nhập đoạn văn bản bạn muốn AI đọc (Tiếng Việt, Anh, Trung, Nhật, Hàn...)"></textarea>

          <button class="btn btn-primary btn-block btn-lg" id="vox-btn">${svgIcon('spark', 18, 2)} Tổng hợp giọng nói</button>

          <div class="mp-progress" id="vox-progress-wrap" style="display:none;">
            <div class="mp-progress-msg" id="vox-progress-msg">Đang xử lý...</div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" id="vox-progress-bar" style="width:5%"></div></div>
          </div>

          <div>
            <div class="mp-label">Kết quả âm thanh</div>
            <div class="mp-output" id="vox-output">
              <div class="mp-empty" style="min-height:150px;">
                <div class="mp-drop-ic">${svgIcon('voxcpm', 22)}</div>
                Chưa có âm thanh. Nhập văn bản và bấm “Tổng hợp giọng nói”.
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>`;

    this._bind(el);
    this._restoreLatestJob(el);
  },

  _restoreLatestJob(el) {
    // Luôn đăng ký nhận kết quả — kể cả lần dùng đầu tiên (chưa có tác vụ cũ nào)
    const latest = jobTracker.getLatestJobForModule('voxcpm');

    const progWrap = el.querySelector('#vox-progress-wrap');
    const progBar  = el.querySelector('#vox-progress-bar');
    const progMsg  = el.querySelector('#vox-progress-msg');
    const output   = el.querySelector('#vox-output');
    const btn      = el.querySelector('#vox-btn');

    if (latest?.status === 'completed' && latest.result) {
      this._renderAudioResult(latest.result, output);
    } else if (latest?.status === 'queued' || latest?.status === 'processing') {
      this._state.busy = true;
      if (btn) btn.disabled = true;
      if (progWrap) progWrap.style.display = 'block';
      if (progBar)  progBar.style.width    = `${latest.progress || 10}%`;
      if (progMsg)  progMsg.textContent    = latest.message || 'Đang sinh giọng ngầm...';
    }

    if (this._state.unsubscribe) this._state.unsubscribe();
    this._state.unsubscribe = jobTracker.subscribe(job => {
      if (job?.module !== 'voxcpm') return;

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
        output.innerHTML = `<div class="mp-error">${svgIcon('alert', 18, 2)} Lỗi: ${job.message}</div>`;
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
      output.innerHTML = `<div class="mp-error">${svgIcon('alert', 18, 2)} Lỗi: ${err.message}</div>`;
      eventBus.emit('toast:show', { message: `❌ ${err.message}`, type: 'error' });
    }
  },

  _renderAudioResult(r, outputEl) {
    if (!outputEl || !r) return;
    const durStr = r.duration ? `${r.duration}s` : 'Hoàn tất!';
    outputEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
        <div class="mp-meta" style="margin:0;"><span>Hoàn tất</span><span>${durStr}</span><span>${r.sample_rate || 48000}Hz</span></div>
        <a href="${r.audio_url}" download="voxcpm_output.wav" class="btn btn-primary btn-sm">${svgIcon('download', 14, 2)} Tải WAV 48kHz</a>
      </div>
      <audio controls autoplay src="${r.audio_url}" style="width:100%;outline:none;"></audio>`;
  },

  unmount(el) {
    if (this._state.unsubscribe) {
      this._state.unsubscribe();
      this._state.unsubscribe = null;
    }
    el.innerHTML = '';
  }
};
