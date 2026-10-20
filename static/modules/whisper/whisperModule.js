/* ============================================================
   Whisper Speech-to-Text Module Plugin
   Integrated with Background JobTracker & Desktop Notifications
   ============================================================ */

import { whisperService } from '../../services/whisperService.js';
import { eventBus } from '../../stores/eventBus.js';
import { jobTracker } from '../../services/jobTracker.js';
import { pageHero, panelHead, svgIcon } from '../../components/pageHero.js';

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
      ${pageHero(this, {
        title: 'Bóc băng <span class="thin">giọng nói</span> thành văn bản',
        sub: 'Tải file âm thanh hoặc video, Whisper chạy trên GPU sẽ chép lại từng câu kèm mốc thời gian, xuất được TXT, SRT và VTT.',
        word: 'Whisper',
        meta: ['GPU CUDA', 'MP3 · WAV · MP4', 'Xuất SRT / VTT'],
      })}

      <div class="mp-body">
        <div class="mp-grid">
          <div class="mp-panel">
            ${panelHead('01', 'Cấu hình', 'bóc băng')}

            <div class="form-group">
              <label class="form-label">File âm thanh / video</label>
              <div class="mp-drop" id="whisperDropzone">
                <div class="mp-drop-ic">${svgIcon('music', 22)}</div>
                <div class="mp-drop-title" id="dropzoneTitle">Kéo thả file vào đây hoặc <u>chọn file</u></div>
                <div class="mp-drop-sub">MP3, WAV, M4A, FLAC, OGG, MP4, WebM</div>
                <input type="file" id="whisperFileInput" hidden accept=".mp3,.wav,.m4a,.flac,.ogg,.mp4,.webm" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Mô hình AI</label>
              <select class="form-select" id="whisperModel">
                <option value="turbo" selected>Turbo — nhanh & chính xác nhất (khuyên dùng)</option>
                <option value="tiny">Tiny — rất nhanh, nhẹ nhất</option>
                <option value="base">Base — cân bằng cho bài test nhanh</option>
                <option value="small">Small — độ chính xác tốt</option>
                <option value="medium">Medium — chính xác cao, dịch tốt</option>
                <option value="large">Large — chính xác cao nhất</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Ngôn ngữ</label>
              <select class="form-select" id="whisperLang">
                <option value="vi" selected>Tiếng Việt (khuyên dùng cho nhạc Việt)</option>
                <option value="auto">Tự nhận diện</option>
                <option value="en">Tiếng Anh</option>
                <option value="zh">Tiếng Trung</option>
                <option value="ja">Tiếng Nhật</option>
                <option value="ko">Tiếng Hàn</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Tác vụ</label>
              <select class="form-select" id="whisperTask">
                <option value="transcribe" selected>Transcribe — chép lại đúng ngôn ngữ gốc</option>
                <option value="translate">Translate — dịch thẳng sang tiếng Anh</option>
              </select>
            </div>

            <button class="btn btn-primary btn-block btn-lg" id="btnStartTranscribe" disabled>
              ${svgIcon('spark', 18, 2)} Bắt đầu bóc băng
            </button>
          </div>

          <div class="mp-panel flex">
            ${panelHead('02', 'Kết quả', 'văn bản', `
              <span id="exportGroup" style="display:contents">
                <button class="btn btn-secondary btn-sm" id="btnCopyText">${svgIcon('copy', 14, 2)} Copy</button>
                <button class="btn btn-secondary btn-sm" id="btnExportTxt">${svgIcon('file', 14, 2)} TXT</button>
                <button class="btn btn-secondary btn-sm" id="btnExportSrt">${svgIcon('download', 14, 2)} SRT</button>
                <button class="btn btn-secondary btn-sm" id="btnExportVtt">${svgIcon('download', 14, 2)} VTT</button>
              </span>`)}

            <div class="mp-progress" id="progressArea" style="display:none;">
              <div class="mp-progress-msg" id="progressText">Đang xử lý...</div>
              <div class="progress-bar-bg"><div class="progress-bar-fill" id="progressBar"></div></div>
            </div>

            <audio id="whisperAudio" controls style="width:100%;display:none;"></audio>

            <div class="mp-output result-box" id="resultText" style="min-height:420px;max-height:640px;">
              <div class="mp-empty">
                <div class="mp-drop-ic">${svgIcon('text', 22)}</div>
                Chưa có dữ liệu. Chọn file và bấm “Bắt đầu bóc băng”.
              </div>
            </div>
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
    if (titleEl) titleEl.innerHTML = `<strong>${this.escapeHtml(file.name)}</strong> (${sizeMB} MB)`;
    const audio = document.getElementById('whisperAudio');
    if (audio) {
      if (audio.dataset.url) URL.revokeObjectURL(audio.dataset.url);
      audio.dataset.url = URL.createObjectURL(file);
      audio.src = audio.dataset.url;
      audio.style.display = 'block';
    }
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

    let html = `<div class="mp-meta" style="margin:0 0 1rem;">`;
    html += `<span>Ngôn ngữ: ${result.language.toUpperCase()}</span><span>Thời lượng: ${result.duration}s</span><span>Model: ${result.model}</span>`;
    html += `</div>`;

    result.segments.forEach(seg => {
      const startStr = this.formatTime(seg.start);
      const endStr = this.formatTime(seg.end);
      html += `
        <div class="segment-row" data-start="${seg.start}" style="cursor:pointer;" title="Bấm để nghe đoạn này">
          <div class="segment-time">${startStr} → ${endStr}</div>
          <div class="segment-text">${this.escapeHtml(seg.text)}</div>
        </div>
      `;
    });

    containerEl.innerHTML = html;
    containerEl.querySelectorAll('.segment-row[data-start]').forEach((row) => {
      row.addEventListener('click', () => {
        const audio = document.getElementById('whisperAudio');
        if (audio && audio.src) { audio.currentTime = parseFloat(row.dataset.start); audio.play().catch(() => {}); }
      });
    });
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
