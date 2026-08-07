/* ============================================================
   Whisper Speech-to-Text Module Plugin
   Integrated with Background JobTracker & Desktop Notifications
   ============================================================ */

import { whisperService } from '../../services/whisperService.js';
import { eventBus } from '../../stores/eventBus.js';
import { jobTracker } from '../../services/jobTracker.js';

export const whisperModule = {
  id: 'whisper',
  name: 'Whisper Speech AI',
  route: '/Whisper',
  icon: '🎙️',
  category: 'Speech AI',
  description: 'Bóc băng âm thanh, dịch thuật và xuất phụ đề tự động bằng mô hình OpenAI Whisper GPU.',
  status: 'active',

  state: {
    selectedFile: null,
    resultData: null,
    isProcessing: false,
    currentJobId: null,
    unsubscribe: null
  },

  render(containerEl) {
    this.state.selectedFile = null;

    containerEl.innerHTML = `
      <div class="workspace-page-header">
        <div class="page-title-group">
          <h1>🎙️ Module: Whisper Speech Recognition</h1>
          <p>Tải file âm thanh/video để bóc băng chính xác bằng GPU PyTorch CUDA.</p>
        </div>
      </div>

      <div class="workspace-two-col">
        <!-- LEFT PANEL: Settings & File Upload -->
        <div class="panel-card">
          <h3 class="panel-title">⚙️ Cấu Hình Bóc Băng</h3>
          
          <div class="form-group">
            <label class="form-label">Tải file Âm Thanh / Video</label>
            <div class="dropzone-container" id="whisperDropzone">
              <div class="dropzone-icon">🎵</div>
              <div class="dropzone-title" id="dropzoneTitle">Kéo thả file vào đây hoặc bấm để chọn</div>
              <div class="dropzone-sub">Hỗ trợ: MP3, WAV, M4A, FLAC, OGG, MP4, WebM</div>
              <input type="file" id="whisperFileInput" hidden accept=".mp3,.wav,.m4a,.flac,.ogg,.mp4,.webm" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Chọn Mô Hình AI (Model)</label>
            <select class="form-select" id="whisperModel">
              <option value="turbo" selected>Turbo (Nhanh & Chính xác nhất - Khuyên dùng)</option>
              <option value="tiny">Tiny (Rất nhanh - Nhẹ nhất)</option>
              <option value="base">Base (Cân bằng cho bài test nhanh)</option>
              <option value="small">Small (Độ chính xác tốt)</option>
              <option value="medium">Medium (Chính xác cao, hỗ trợ dịch tốt)</option>
              <option value="large">Large (Chính xác cao nhất)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Ngôn Ngữ</label>
            <select class="form-select" id="whisperLang">
              <option value="vi" selected>Tiếng Việt (Vietnamese - Khuyên dùng cho nhạc Việt)</option>
              <option value="auto">Auto Detect (Tự nhận diện)</option>
              <option value="en">Tiếng Anh (English)</option>
              <option value="zh">Tiếng Trung (Chinese)</option>
              <option value="ja">Tiếng Nhật (Japanese)</option>
              <option value="ko">Tiếng Hàn (Korean)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Tác Vụ (Task)</label>
            <select class="form-select" id="whisperTask">
              <option value="transcribe" selected>Transcribe (Bóc băng ra văn bản gốc)</option>
              <option value="translate">Translate (Dịch trực tiếp sang Tiếng Anh)</option>
            </select>
          </div>

          <button class="btn btn-primary" id="btnStartTranscribe" style="width:100%; margin-top:0.5rem;" disabled>
            🚀 Bắt Đầu Chuyển Đổi
          </button>
        </div>

        <!-- RIGHT PANEL: Result & Progress -->
        <div class="panel-card" style="display:flex; flex-direction:column;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <h3 class="panel-title" style="margin-bottom:0;">📝 Kết Quả Văn Bản</h3>
            <div style="display:flex; gap:0.5rem;" id="exportGroup">
              <button class="btn btn-secondary" id="btnCopyText" style="padding:0.4rem 0.75rem; font-size:0.8rem;">📋 Copy</button>
              <button class="btn btn-secondary" id="btnExportTxt" style="padding:0.4rem 0.75rem; font-size:0.8rem;">📄 TXT</button>
              <button class="btn btn-secondary" id="btnExportSrt" style="padding:0.4rem 0.75rem; font-size:0.8rem;">🎬 SRT</button>
              <button class="btn btn-secondary" id="btnExportVtt" style="padding:0.4rem 0.75rem; font-size:0.8rem;">📺 VTT</button>
            </div>
          </div>

          <div id="progressArea" style="display:none; margin-bottom:1rem; padding:1rem; background-color:var(--primary-light); border-radius:var(--radius-md); border:1px solid var(--primary);">
            <div style="font-weight:700; color:var(--primary); margin-bottom:0.4rem; font-size:0.875rem;" id="progressText">Đang xử lý...</div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" id="progressBar"></div>
            </div>
          </div>

          <div class="result-box" id="resultText">
            Chưa có dữ liệu. Vui lòng chọn file và bấm "Bắt Đầu Chuyển Đổi".
          </div>
        </div>
      </div>
    `;

    this.bindEvents(containerEl);
    this.restoreLatestJob(containerEl);
  },

  restoreLatestJob(containerEl) {
    const latest = jobTracker.getLatestJobForModule('whisper');
    if (!latest) return;

    const progressArea = containerEl.querySelector('#progressArea');
    const progressBar = containerEl.querySelector('#progressBar');
    const progressText = containerEl.querySelector('#progressText');
    const resultText = containerEl.querySelector('#resultText');

    if (latest.status === 'completed' && latest.result) {
      this.state.resultData = latest.result;
      this.renderResult(latest.result, resultText);
    } else if (latest.status === 'queued' || latest.status === 'processing') {
      this.state.isProcessing = true;
      if (progressArea) progressArea.style.display = 'block';
      if (progressBar) progressBar.style.width = `${latest.progress || 10}%`;
      if (progressText) progressText.textContent = latest.message || 'Đang bóc băng ngầm...';
    }

    // Subscribe to updates from jobTracker
    this.state.unsubscribe = jobTracker.subscribe(job => {
      if (job.module !== 'whisper') return;

      if (job.status === 'processing' || job.status === 'queued') {
        if (progressArea) progressArea.style.display = 'block';
        if (progressBar) progressBar.style.width = `${job.progress || 10}%`;
        if (progressText) progressText.textContent = job.message || 'Đang bóc băng...';
      } else if (job.status === 'completed' && job.result) {
        this.state.isProcessing = false;
        if (progressArea) progressArea.style.display = 'none';
        const btnStart = containerEl.querySelector('#btnStartTranscribe');
        if (btnStart) btnStart.disabled = false;
        this.state.resultData = job.result;
        this.renderResult(job.result, resultText);
      } else if (job.status === 'failed') {
        this.state.isProcessing = false;
        if (progressArea) progressArea.style.display = 'none';
        const btnStart = containerEl.querySelector('#btnStartTranscribe');
        if (btnStart) btnStart.disabled = false;
        if (resultText) resultText.textContent = `❌ Lỗi: ${job.message}`;
      }
    });
  },

  bindEvents(containerEl) {
    const dropzone = containerEl.querySelector('#whisperDropzone');
    const fileInput = containerEl.querySelector('#whisperFileInput');
    const btnStart = containerEl.querySelector('#btnStartTranscribe');
    const dropzoneTitle = containerEl.querySelector('#dropzoneTitle');

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());

      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
      });

      dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
          this.handleFile(e.dataTransfer.files[0], dropzoneTitle, btnStart);
        }
      });

      fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) {
          this.handleFile(e.target.files[0], dropzoneTitle, btnStart);
        }
      });
    }

    if (btnStart) {
      btnStart.addEventListener('click', () => this.startTranscribe(containerEl));
    }

    // Export Buttons
    containerEl.querySelector('#btnCopyText')?.addEventListener('click', () => {
      if (this.state.resultData?.text) {
        navigator.clipboard.writeText(this.state.resultData.text);
        eventBus.emit('toast:show', { message: 'Đã sao chép văn bản vào bộ nhớ tạm!' });
      }
    });

    ['txt', 'srt', 'vtt'].forEach(fmt => {
      containerEl.querySelector(`#btnExport${fmt.charAt(0).toUpperCase() + fmt.slice(1)}`)?.addEventListener('click', () => {
        if (this.state.resultData) {
          whisperService.exportResult(fmt, this.state.resultData).catch(err => {
            eventBus.emit('toast:show', { message: `Lỗi xuất file: ${err.message}`, type: 'error' });
          });
        }
      });
    });
  },

  handleFile(file, titleEl, btnEl) {
    this.state.selectedFile = file;
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    if (titleEl) titleEl.innerHTML = `<strong>${file.name}</strong> (${sizeMB} MB)`;
    if (btnEl) btnEl.disabled = false;
  },

  async startTranscribe(containerEl) {
    if (!this.state.selectedFile || this.state.isProcessing) return;

    const btnStart = containerEl.querySelector('#btnStartTranscribe');
    const progressArea = containerEl.querySelector('#progressArea');
    const progressBar = containerEl.querySelector('#progressBar');
    const progressText = containerEl.querySelector('#progressText');
    const resultText = containerEl.querySelector('#resultText');

    this.state.isProcessing = true;
    if (btnStart) btnStart.disabled = true;
    if (progressArea) progressArea.style.display = 'block';
    if (progressBar) progressBar.style.width = '10%';
    if (progressText) progressText.textContent = 'Đang tải file lên server...';
    if (resultText) resultText.textContent = 'Đang tiến hành bóc băng âm thanh...';

    const model = containerEl.querySelector('#whisperModel').value;
    const language = containerEl.querySelector('#whisperLang').value;
    const task = containerEl.querySelector('#whisperTask').value;

    try {
      const jobRes = await whisperService.transcribeAudio(this.state.selectedFile, model, language, task);
      const jobId = jobRes.job_id;

      // Track in global background jobTracker
      jobTracker.trackJob({
        id: jobId,
        module: 'whisper',
        route: '/Whisper',
        title: `Whisper Bóc Băng (${this.state.selectedFile.name})`
      });

      eventBus.emit('toast:show', { message: '🚀 Tác vụ đã chạy ngầm! Bạn có thể chuyển trang thoải mái.' });

    } catch (err) {
      this.state.isProcessing = false;
      if (btnStart) btnStart.disabled = false;
      if (progressArea) progressArea.style.display = 'none';
      if (resultText) resultText.textContent = `❌ Lỗi: ${err.message}`;
    }
  },

  renderResult(result, containerEl) {
    if (!result || !result.segments) {
      containerEl.textContent = result?.text || 'Không phát hiện thấy giọng nói.';
      return;
    }

    let html = `<div style="font-weight:700; color:var(--primary); margin-bottom:0.75rem;">`;
    html += `🌐 Ngôn ngữ: ${result.language.toUpperCase()} | ⏱ Thời gian bóc băng: ${result.duration}s | ⚡ Model: ${result.model}`;
    html += `</div>`;

    result.segments.forEach(seg => {
      const startStr = this.formatTime(seg.start);
      const endStr = this.formatTime(seg.end);
      html += `
        <div class="segment-row">
          <div class="segment-time">${startStr} → ${endStr}</div>
          <div class="segment-text">${this.escapeHtml(seg.text)}</div>
        </div>
      `;
    });

    containerEl.innerHTML = html;
  },

  formatTime(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 10);
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}.${ms}`;
  },

  escapeHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  },

  unmount(containerEl) {
    if (this.state.unsubscribe) {
      this.state.unsubscribe();
      this.state.unsubscribe = null;
    }
    containerEl.innerHTML = '';
  }
};
