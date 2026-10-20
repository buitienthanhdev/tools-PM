import { pageHero } from '../../components/pageHero.js';

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 32_000_000;
const PREVIEW_EDGE = 2048;
const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/bmp']);
const ALLOWED_EXTENSIONS = /\.(jpe?g|png|webp|bmp)$/i;

const DEFAULT_FILTERS = Object.freeze({
  brightness: 100,
  contrast: 100,
  saturation: 100,
  hue: 0,
  blur: 0,
  preset: 'none',
});

const mountedEditors = new WeakMap();

function initialState() {
  return {
    rotation: 0,
    flipX: false,
    flipY: false,
    crop: { x: 0, y: 0, width: 100, height: 100 },
    filters: { ...DEFAULT_FILTERS },
  };
}

function cloneState(state) {
  return {
    ...state,
    crop: { ...state.crop },
    filters: { ...state.filters },
  };
}

function stateKey(state) {
  return JSON.stringify(state);
}

function imageDimensions(bitmap, state, scale = 1) {
  const width = Math.max(1, Math.round(bitmap.width * state.crop.width / 100));
  const height = Math.max(1, Math.round(bitmap.height * state.crop.height / 100));
  const rotated = Math.abs(state.rotation % 2) === 1;
  return {
    width: Math.max(1, Math.round((rotated ? height : width) * scale)),
    height: Math.max(1, Math.round((rotated ? width : height) * scale)),
  };
}

function drawImage(source, state, scale = 1) {
  const canvas = document.createElement('canvas');
  const size = imageDimensions(source, state, scale);
  const cropWidth = Math.max(1, Math.round(source.width * state.crop.width / 100));
  const cropHeight = Math.max(1, Math.round(source.height * state.crop.height / 100));
  const cropX = Math.round(source.width * state.crop.x / 100);
  const cropY = Math.round(source.height * state.crop.y / 100);
  const pixelScale = size.width / (Math.abs(state.rotation % 2) ? cropHeight : cropWidth);

  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext('2d', { alpha: true });
  if (!context) {
    throw new Error('Trình duyệt không thể tạo canvas xử lý ảnh.');
  }

  const presetFilter = {
    mono: ' grayscale(1)',
    warm: ' sepia(0.18)',
    vivid: '',
    none: '',
  }[state.filters.preset] || '';
  context.filter = [
    `brightness(${state.filters.brightness}%)`,
    `contrast(${state.filters.contrast}%)`,
    `saturate(${state.filters.saturation}%)`,
    `hue-rotate(${state.filters.hue}deg)`,
    `blur(${state.filters.blur}px)`,
    presetFilter,
  ].join(' ');
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = 'high';
  context.translate(canvas.width / 2, canvas.height / 2);
  context.rotate(state.rotation * Math.PI / 2);
  context.scale(state.flipX ? -1 : 1, state.flipY ? -1 : 1);
  context.drawImage(
    source,
    cropX,
    cropY,
    cropWidth,
    cropHeight,
    -cropWidth * pixelScale / 2,
    -cropHeight * pixelScale / 2,
    cropWidth * pixelScale,
    cropHeight * pixelScale,
  );
  context.setTransform(1, 0, 0, 1, 0, 0);
  return canvas;
}

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error('Không thể tạo ảnh xuất. Hãy thử PNG hoặc giảm kích thước.'));
      }
    }, type, quality);
  });
}

function delay(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

class ImageWorkspace {
  constructor(containerEl, module) {
    this.container = containerEl;
    this.module = module;
    this.bitmap = null;
    this.file = null;
    this.originalUrl = null;
    this.state = initialState();
    this.undoStack = [];
    this.redoStack = [];
    this.rangeStart = null;
    this.previewFrame = null;
    this.jobSession = 0;
    this.destroyed = false;
    this.downloadUrls = new Set();
    this.render();
    this.bindEvents();
  }

  render() {
    this.container.innerHTML = `
      ${pageHero(this.module, {
        title: 'Image <span class="thin">Workspace</span>',
        sub: 'Chỉnh ảnh ngay trong trình duyệt. Ảnh chỉ được gửi đến máy chủ khi bạn chủ động bật đồng ý và chạy Real-ESRGAN.',
        word: 'Image',
        meta: ['Chỉnh sửa cục bộ', 'PNG · JPG · WebP', 'Undo · Redo'],
      })}
      <section class="iw-workspace" aria-label="Image editing workspace">
        <div class="iw-toolbar">
          <button class="btn btn-secondary btn-sm" type="button" data-action="open">Mở ảnh</button>
          <input class="iw-file-input" type="file" accept="image/jpeg,image/png,image/webp,image/bmp,.jpg,.jpeg,.png,.webp,.bmp" aria-label="Chọn ảnh">
          <span class="iw-toolbar-separator" aria-hidden="true"></span>
          <button class="btn btn-secondary btn-sm" type="button" data-action="undo" disabled>Hoàn tác</button>
          <button class="btn btn-secondary btn-sm" type="button" data-action="redo" disabled>Làm lại</button>
          <button class="btn btn-secondary btn-sm" type="button" data-action="reset" disabled>Đặt lại</button>
          <span class="iw-toolbar-spacer"></span>
          <button class="btn btn-secondary btn-sm" type="button" data-action="compare" disabled>So sánh gốc</button>
          <button class="btn btn-primary btn-sm" type="button" data-action="export" disabled>Xuất ảnh</button>
        </div>

        <div class="iw-layout">
          <aside class="iw-sidebar" aria-label="Công cụ">
            <div class="iw-sidebar-title">Công cụ</div>
            <button type="button" class="iw-nav-button" data-scroll="iw-transform">Biến đổi</button>
            <button type="button" class="iw-nav-button" data-scroll="iw-adjust">Điều chỉnh</button>
            <button type="button" class="iw-nav-button" data-scroll="iw-export">Xuất ảnh</button>
            <button type="button" class="iw-nav-button" data-scroll="iw-ai">AI upscale</button>
            <div class="iw-privacy-note">Ảnh được giữ trong trình duyệt cho đến khi bạn tự chạy công cụ AI trên máy chủ.</div>
          </aside>

          <main class="iw-canvas-panel">
            <div class="iw-stage" aria-label="Bản xem trước ảnh">
              <div class="iw-empty">
                <strong>Mở ảnh để bắt đầu</strong>
                <span>Kéo thả, dán từ clipboard hoặc chọn JPEG, PNG, WebP, BMP</span>
                <button class="btn btn-primary" type="button" data-action="open">Chọn ảnh</button>
              </div>
              <canvas class="iw-preview" aria-label="Ảnh đã chỉnh sửa" hidden></canvas>
              <img class="iw-before" alt="Ảnh gốc" hidden>
              <div class="iw-empty-error" role="alert" hidden></div>
            </div>
            <div class="iw-compare-row" hidden>
              <label for="iw-compare">Ảnh gốc / Kết quả</label>
              <input id="iw-compare" type="range" min="0" max="100" value="50" aria-label="Mức hiển thị ảnh gốc">
              <output data-compare-value>50%</output>
            </div>
            <div class="iw-status" role="status" aria-live="polite">Ảnh chưa được tải lên máy chủ.</div>
            <div class="iw-ai-result" hidden>
              <div><strong>Kết quả Real-ESRGAN</strong><span data-ai-dimensions></span></div>
              <img alt="Ảnh sau khi được AI nâng cấp" data-ai-preview>
              <a class="btn btn-primary btn-sm" data-ai-download>Tải ảnh AI</a>
            </div>
          </main>

          <aside class="iw-inspector" aria-label="Thông số chỉnh ảnh">
            <section class="iw-tool-section" id="iw-transform">
              <h2>Biến đổi</h2>
              <div class="iw-button-grid">
                <button class="btn btn-secondary btn-sm" type="button" data-action="rotate-left" disabled>↶ Xoay trái</button>
                <button class="btn btn-secondary btn-sm" type="button" data-action="rotate-right" disabled>↷ Xoay phải</button>
                <button class="btn btn-secondary btn-sm" type="button" data-action="flip-x" disabled>Lật ngang</button>
                <button class="btn btn-secondary btn-sm" type="button" data-action="flip-y" disabled>Lật dọc</button>
              </div>
              <h3>Cắt ảnh (%)</h3>
              <div class="iw-crop-grid">
                <label>X <input type="number" min="0" max="100" step="1" data-crop="x" value="0" disabled></label>
                <label>Y <input type="number" min="0" max="100" step="1" data-crop="y" value="0" disabled></label>
                <label>Rộng <input type="number" min="1" max="100" step="1" data-crop="width" value="100" disabled></label>
                <label>Cao <input type="number" min="1" max="100" step="1" data-crop="height" value="100" disabled></label>
              </div>
              <p class="iw-hint">Vùng cắt được áp dụng trước khi xoay/lật.</p>
            </section>

            <section class="iw-tool-section" id="iw-adjust">
              <h2>Điều chỉnh</h2>
              <label class="iw-field">Preset
                <select data-setting="preset" disabled>
                  <option value="none">Gốc</option>
                  <option value="warm">Ấm</option>
                  <option value="mono">Đen trắng</option>
                  <option value="vivid">Rực rỡ</option>
                </select>
              </label>
              <label class="iw-range">Độ sáng <output data-value="brightness">100%</output>
                <input type="range" min="0" max="200" value="100" data-setting="brightness" disabled>
              </label>
              <label class="iw-range">Tương phản <output data-value="contrast">100%</output>
                <input type="range" min="0" max="200" value="100" data-setting="contrast" disabled>
              </label>
              <label class="iw-range">Độ bão hòa <output data-value="saturation">100%</output>
                <input type="range" min="0" max="200" value="100" data-setting="saturation" disabled>
              </label>
              <label class="iw-range">Sắc độ <output data-value="hue">0°</output>
                <input type="range" min="-180" max="180" value="0" data-setting="hue" disabled>
              </label>
              <label class="iw-range">Làm mờ <output data-value="blur">0 px</output>
                <input type="range" min="0" max="12" value="0" step="0.5" data-setting="blur" disabled>
              </label>
            </section>

            <section class="iw-tool-section" id="iw-export">
              <h2>Xuất ảnh</h2>
              <label class="iw-field">Định dạng
                <select data-export="format" disabled>
                  <option value="image/png">PNG (giữ alpha)</option>
                  <option value="image/jpeg">JPEG</option>
                  <option value="image/webp">WebP</option>
                </select>
              </label>
              <label class="iw-field">Kích thước
                <select data-export="scale" disabled>
                  <option value="1">100% · kích thước gốc</option>
                  <option value="0.75">75%</option>
                  <option value="0.5">50%</option>
                  <option value="0.25">25%</option>
                </select>
              </label>
              <label class="iw-range">Chất lượng JPEG/WebP <output data-value="quality">92%</output>
                <input type="range" min="40" max="100" value="92" data-export="quality" disabled>
              </label>
              <div class="iw-output-size" data-output-size>—</div>
            </section>

            <section class="iw-tool-section iw-ai-section" id="iw-ai">
              <h2>AI Upscale</h2>
              <p>Chạy Real-ESRGAN trên máy chủ PM Tools. Chỉ tải ảnh đã chỉnh sửa sau khi bạn đồng ý bên dưới.</p>
              <label class="iw-field">Tỉ lệ
                <select data-ai="scale" disabled>
                  <option value="2x">2×</option>
                  <option value="4x" selected>4×</option>
                </select>
              </label>
              <label class="iw-field">Mô hình
                <select data-ai="model" disabled>
                  <option value="photo">Ảnh chụp</option>
                  <option value="anime">Anime</option>
                  <option value="fast">Nhanh</option>
                </select>
              </label>
              <label class="iw-consent"><input type="checkbox" data-ai="consent" disabled> Tôi đồng ý gửi ảnh đã chỉnh sửa đến máy chủ PM Tools để xử lý AI.</label>
              <button class="btn btn-primary btn-sm" type="button" data-action="ai" disabled>Chạy Real-ESRGAN</button>
              <div class="iw-ai-progress" data-ai-progress hidden>
                <progress max="100" value="0" data-ai-progress-bar></progress>
                <span data-ai-message></span>
              </div>
            </section>
          </aside>
        </div>
      </section>
    `;
  }

  bindEvents() {
    this.root = this.container.querySelector('.iw-workspace');
    this.fileInput = this.container.querySelector('.iw-file-input');
    this.canvas = this.container.querySelector('.iw-preview');
    this.before = this.container.querySelector('.iw-before');
    this.empty = this.container.querySelector('.iw-empty');
    this.error = this.container.querySelector('.iw-empty-error');
    this.status = this.container.querySelector('.iw-status');
    this.stage = this.container.querySelector('.iw-stage');
    this.compareRow = this.container.querySelector('.iw-compare-row');
    this.aiResult = this.container.querySelector('.iw-ai-result');

    this.root.addEventListener('click', (event) => this.handleClick(event));
    this.root.addEventListener('change', (event) => this.handleChange(event));
    this.root.addEventListener('input', (event) => this.handleInput(event));
    this.root.addEventListener('pointerdown', (event) => this.beginRangeEdit(event));
    this.root.addEventListener('focusin', (event) => this.beginRangeEdit(event));
    this.root.addEventListener('focusout', (event) => this.finishRangeEdit(event));
    this.root.addEventListener('keydown', (event) => this.handleKeydown(event));
    this.root.addEventListener('dragover', (event) => {
      if (event.dataTransfer?.types.includes('Files')) {
        event.preventDefault();
        this.root.classList.add('iw-dragging');
      }
    });
    this.root.addEventListener('dragleave', (event) => {
      if (!this.root.contains(event.relatedTarget)) this.root.classList.remove('iw-dragging');
    });
    this.root.addEventListener('drop', (event) => {
      if (!event.dataTransfer?.files.length) return;
      event.preventDefault();
      this.root.classList.remove('iw-dragging');
      this.loadFile(event.dataTransfer.files[0]);
    });
    this.root.addEventListener('paste', (event) => {
      const file = Array.from(event.clipboardData?.items || [])
        .find((item) => item.type.startsWith('image/'))?.getAsFile();
      if (file) {
        event.preventDefault();
        this.loadFile(file);
      }
    });
  }

  handleClick(event) {
    const actionButton = event.target.closest('[data-action]');
    if (actionButton) {
      const { action } = actionButton.dataset;
      if (action === 'open') this.fileInput.click();
      else if (action === 'undo') this.undo();
      else if (action === 'redo') this.redo();
      else if (action === 'reset') this.reset();
      else if (action === 'compare') this.toggleCompare();
      else if (action === 'rotate-left') this.applyAction((state) => { state.rotation = (state.rotation + 3) % 4; });
      else if (action === 'rotate-right') this.applyAction((state) => { state.rotation = (state.rotation + 1) % 4; });
      else if (action === 'flip-x') this.applyAction((state) => { state.flipX = !state.flipX; });
      else if (action === 'flip-y') this.applyAction((state) => { state.flipY = !state.flipY; });
      else if (action === 'export') this.exportImage();
      else if (action === 'ai') this.runAiUpscale();
      return;
    }

    const navButton = event.target.closest('[data-scroll]');
    if (navButton) {
      this.container.querySelector(`#${navButton.dataset.scroll}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  handleChange(event) {
    const input = event.target;
    if (input === this.fileInput) {
      if (input.files?.[0]) this.loadFile(input.files[0]);
      return;
    }

    if (input.dataset.crop) {
      this.updateCrop(input.dataset.crop, input.value);
      return;
    }

    if (input.dataset.setting === 'preset') {
      this.applyAction((state) => {
        const presets = {
          none: { ...DEFAULT_FILTERS },
          warm: { ...DEFAULT_FILTERS, brightness: 103, contrast: 105, saturation: 110, hue: -5, preset: 'warm' },
          mono: { ...DEFAULT_FILTERS, contrast: 108, preset: 'mono' },
          vivid: { ...DEFAULT_FILTERS, brightness: 103, contrast: 108, saturation: 145, preset: 'vivid' },
        };
        state.filters = { ...presets[input.value] };
      });
      return;
    }

    if (input.matches('input[type="range"][data-setting]')) {
      this.finishRangeEdit({ target: input });
      return;
    }

    if (input.id === 'iw-compare') {
      this.updateCompare(input.value);
      return;
    }

    if (input.dataset.export === 'format' || input.dataset.export === 'scale') {
      this.updateOutputSize();
      return;
    }

    if (input.dataset.export === 'quality') {
      this.updateValueLabel('quality', `${input.value}%`);
      return;
    }

    if (input.dataset.ai === 'consent') {
      this.updateControls();
    }
  }

  handleInput(event) {
    const input = event.target;
    if (input.dataset.setting && input.dataset.setting !== 'preset') {
      const key = input.dataset.setting;
      const value = Number(input.value);
      if (!Number.isFinite(value)) return;
      this.state.filters[key] = value;
      this.state.filters.preset = 'none';
      this.updateValueLabel(key, key === 'hue' ? `${value}°` : key === 'blur' ? `${value} px` : `${value}%`);
      this.schedulePreview();
    } else if (input.id === 'iw-compare') {
      this.updateCompare(input.value);
    } else if (input.dataset.export === 'quality') {
      this.updateValueLabel('quality', `${input.value}%`);
    }
  }

  handleKeydown(event) {
    if (!(event.ctrlKey || event.metaKey)) return;
    const tag = event.target.tagName;
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;
    if (event.key.toLowerCase() === 'z' && event.shiftKey) {
      event.preventDefault();
      this.redo();
    } else if (event.key.toLowerCase() === 'z') {
      event.preventDefault();
      this.undo();
    } else if (event.key.toLowerCase() === 'y') {
      event.preventDefault();
      this.redo();
    }
  }

  beginRangeEdit(event) {
    if (event.target.matches('input[type="range"][data-setting]') && !this.rangeStart) {
      this.rangeStart = cloneState(this.state);
    }
  }

  finishRangeEdit(event) {
    if (event.target.matches('input[type="range"][data-setting]')) {
      if (this.rangeStart && stateKey(this.rangeStart) !== stateKey(this.state)) {
        this.undoStack.push(this.rangeStart);
        this.redoStack = [];
      }
      this.rangeStart = null;
      this.syncInputs();
      this.updateControls();
    }
  }

  async loadFile(file) {
    this.showError('');
    if (!ALLOWED_TYPES.has(file.type) && !ALLOWED_EXTENSIONS.test(file.name)) {
      this.showError('Định dạng không hỗ trợ. Hãy chọn JPEG, PNG hoặc WebP.');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      this.showError('Ảnh vượt quá giới hạn 50 MB. Hãy giảm dung lượng rồi thử lại.');
      return;
    }

    this.setStatus('Đang đọc ảnh cục bộ…');
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
      if (bitmap.width * bitmap.height > MAX_IMAGE_PIXELS) {
        bitmap.close();
        this.showError('Ảnh vượt quá giới hạn 32 megapixel để bảo vệ bộ nhớ trình duyệt.');
        return;
      }
    } catch (error) {
      this.showError(`Không thể giải mã ảnh: ${error.message || 'file có thể bị hỏng hoặc không được hỗ trợ.'}`);
      return;
    }

    if (this.destroyed) {
      bitmap.close();
      return;
    }
    this.invalidateAiSession();
    if (this.bitmap) this.bitmap.close();
    if (this.originalUrl) URL.revokeObjectURL(this.originalUrl);
    this.bitmap = bitmap;
    this.file = file;
    this.originalUrl = URL.createObjectURL(file);
    this.before.src = this.originalUrl;
    this.before.hidden = true;
    this.aiResult.hidden = true;
    this.root.querySelector('[data-ai="consent"]').checked = false;
    this.root.querySelector('[data-ai-progress]').hidden = true;
    this.compareRow.hidden = true;
    const compareButton = this.root.querySelector('[data-action="compare"]');
    compareButton.textContent = 'So sánh gốc';
    compareButton.setAttribute('aria-pressed', 'false');
    this.root.querySelector('[data-ai-preview]').removeAttribute('src');
    this.root.querySelector('[data-ai-download]').removeAttribute('href');
    this.state = initialState();
    this.undoStack = [];
    this.redoStack = [];
    this.rangeStart = null;
    this.empty.hidden = true;
    this.canvas.hidden = false;
    this.updateControls();
    this.syncInputs();
    this.renderPreview();
    this.setStatus(`${file.name} · ${bitmap.width} × ${bitmap.height} · ảnh chưa rời khỏi trình duyệt.`);
  }

  applyAction(action) {
    if (!this.bitmap) return;
    const before = cloneState(this.state);
    action(this.state);
    if (stateKey(before) === stateKey(this.state)) return;
    this.undoStack.push(before);
    this.redoStack = [];
    this.syncInputs();
    this.schedulePreview();
    this.updateControls();
  }

  updateCrop(key, rawValue) {
    const value = Number(rawValue);
    if (!Number.isFinite(value)) {
      this.setStatus('Nhập giá trị cắt hợp lệ từ 0 đến 100%.');
      return;
    }
    this.applyAction((state) => {
      const crop = state.crop;
      if (key === 'x') crop.x = Math.min(99, Math.max(0, value), 100 - crop.width);
      if (key === 'y') crop.y = Math.min(99, Math.max(0, value), 100 - crop.height);
      if (key === 'width') crop.width = Math.min(100 - crop.x, Math.max(1, value));
      if (key === 'height') crop.height = Math.min(100 - crop.y, Math.max(1, value));
    });
    this.setStatus(`Vùng cắt: ${this.state.crop.width}% × ${this.state.crop.height}%.`);
  }

  undo() {
    if (!this.undoStack.length) return;
    this.redoStack.push(cloneState(this.state));
    this.state = this.undoStack.pop();
    this.syncInputs();
    this.schedulePreview();
    this.updateControls();
    this.setStatus('Đã hoàn tác thay đổi gần nhất.');
  }

  redo() {
    if (!this.redoStack.length) return;
    this.undoStack.push(cloneState(this.state));
    this.state = this.redoStack.pop();
    this.syncInputs();
    this.schedulePreview();
    this.updateControls();
    this.setStatus('Đã làm lại thay đổi.');
  }

  reset() {
    if (!this.bitmap) return;
    this.applyAction((state) => Object.assign(state, initialState()));
    this.setStatus('Đã đặt lại các chỉnh sửa. Kích thước xuất và ảnh gốc được giữ nguyên.');
  }

  syncInputs() {
    for (const [key, value] of Object.entries(this.state.crop)) {
      const input = this.root.querySelector(`[data-crop="${key}"]`);
      if (input) input.value = value;
    }
    for (const [key, value] of Object.entries(this.state.filters)) {
      const input = this.root.querySelector(`[data-setting="${key}"]`);
      if (input) input.value = value;
      const label = key === 'hue' ? `${value}°` : key === 'blur' ? `${value} px` : `${value}%`;
      this.updateValueLabel(key, label);
    }
  }

  schedulePreview() {
    if (!this.bitmap || this.previewFrame !== null) return;
    this.previewFrame = window.requestAnimationFrame(() => {
      this.previewFrame = null;
      try {
        this.renderPreview();
      } catch (error) {
        this.showError(`Không thể tạo bản xem trước: ${error.message}`);
      }
    });
  }

  renderPreview() {
    if (!this.bitmap) return;
    const raw = imageDimensions(this.bitmap, this.state);
    const scale = Math.min(1, PREVIEW_EDGE / Math.max(raw.width, raw.height));
    const preview = drawImage(this.bitmap, this.state, scale);
    this.canvas.width = preview.width;
    this.canvas.height = preview.height;
    const context = this.canvas.getContext('2d', { alpha: true });
    if (!context) {
      preview.width = 0;
      preview.height = 0;
      throw new Error('Không tạo được canvas xem trước.');
    }
    context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    context.drawImage(preview, 0, 0);
    preview.width = 0;
    preview.height = 0;
    this.stage.style.aspectRatio = `${raw.width} / ${raw.height}`;
    this.updateOutputSize();
    this.updateCompare(this.root.querySelector('#iw-compare').value);
    this.showError('');
  }

  updateCompare(rawValue) {
    const value = Math.min(100, Math.max(0, Number(rawValue) || 0));
    this.before.style.clipPath = `inset(0 ${100 - value}% 0 0)`;
    this.root.querySelector('[data-compare-value]').value = `${value}%`;
  }

  toggleCompare() {
    const visible = this.before.hidden;
    this.before.hidden = !visible;
    this.compareRow.hidden = !visible;
    this.root.querySelector('[data-action="compare"]').setAttribute('aria-pressed', String(visible));
    this.root.querySelector('[data-action="compare"]').textContent = visible ? 'Ẩn ảnh gốc' : 'So sánh gốc';
    this.setStatus(visible ? 'Đang so sánh ảnh gốc với bản xem trước; kéo thanh để đổi vùng hiển thị.' : 'Đã tắt chế độ so sánh.');
  }

  async exportImage() {
    if (!this.bitmap) return;
    const button = this.root.querySelector('[data-action="export"]');
    button.disabled = true;
    this.setStatus('Đang kết xuất ảnh ở độ phân giải đã chọn…');
    let canvas;
    try {
      const scale = Number(this.root.querySelector('[data-export="scale"]').value);
      const type = this.root.querySelector('[data-export="format"]').value;
      const quality = Number(this.root.querySelector('[data-export="quality"]').value) / 100;
      canvas = drawImage(this.bitmap, this.state, scale);
      if (type === 'image/jpeg') {
        const flattened = document.createElement('canvas');
        flattened.width = canvas.width;
        flattened.height = canvas.height;
        const context = flattened.getContext('2d');
        if (!context) throw new Error('Không thể tạo ảnh JPEG.');
        context.fillStyle = '#fff';
        context.fillRect(0, 0, flattened.width, flattened.height);
        context.drawImage(canvas, 0, 0);
        canvas.width = 0;
        canvas.height = 0;
        canvas = flattened;
      }
      const blob = await canvasBlob(canvas, type, quality);
      if (blob.type !== type) {
        throw new Error(`Trình duyệt không hỗ trợ xuất ${type.split('/')[1].toUpperCase()}.`);
      }
      const url = URL.createObjectURL(blob);
      const extension = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' }[type];
      const link = document.createElement('a');
      link.href = url;
      link.download = `paint-and-more-${Date.now()}.${extension}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      this.downloadUrls.add(url);
      window.setTimeout(() => {
        URL.revokeObjectURL(url);
        this.downloadUrls.delete(url);
      }, 30_000);
      const displaySize = blob.size < 1024 ? `${blob.size} B` : `${Math.round(blob.size / 1024)} KB`;
      this.setStatus(`Đã xuất ${canvas.width} × ${canvas.height} ${extension.toUpperCase()} (${displaySize}).`);
    } catch (error) {
      this.showError(`Không thể xuất ảnh: ${error.message}`);
    } finally {
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
      button.disabled = false;
    }
  }

  async runAiUpscale() {
    if (!this.bitmap || !this.root.querySelector('[data-ai="consent"]').checked) return;
    const button = this.root.querySelector('[data-action="ai"]');
    const progress = this.root.querySelector('[data-ai-progress]');
    const progressBar = this.root.querySelector('[data-ai-progress-bar]');
    const message = this.root.querySelector('[data-ai-message]');
    const session = ++this.jobSession;
    const controller = new AbortController();
    this.aiController = controller;
    button.disabled = true;
    progress.hidden = false;
    progressBar.value = 0;
    this.aiResult.hidden = true;
    this.setStatus('Đang chuẩn bị ảnh đã chỉnh sửa để gửi đến máy chủ PM Tools…');
    let canvas;
    try {
      canvas = drawImage(this.bitmap, this.state);
      const blob = await canvasBlob(canvas, 'image/png', 1);
      if (blob.size > MAX_FILE_BYTES) throw new Error('Ảnh sau chỉnh sửa vượt quá giới hạn tải lên 50 MB.');
      const form = new FormData();
      form.append('image', new File([blob], 'edited-image.png', { type: 'image/png' }));
      const uploaded = await this.apiJson('/api/image/upload', { method: 'POST', body: form, signal: controller.signal });
      this.assertCurrentSession(session);
      this.setStatus('Ảnh đã được gửi theo yêu cầu. Đang xếp hàng xử lý Real-ESRGAN…');
      const started = await this.apiJson('/api/image/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: uploaded.job_id,
          scale: this.root.querySelector('[data-ai="scale"]').value,
          model: this.root.querySelector('[data-ai="model"]').value,
        }),
        signal: controller.signal,
      });
      const deadline = Date.now() + 30 * 60 * 1000;
      let job;
      while (Date.now() < deadline) {
        await delay(1200);
        this.assertCurrentSession(session);
        job = await this.apiJson(`/api/job/${encodeURIComponent(started.job_id)}`, { signal: controller.signal });
        progressBar.value = Math.max(0, Math.min(100, Number(job.progress) || 0));
        message.textContent = job.message || 'Đang xử lý ảnh trên máy chủ…';
        if (job.status === 'completed') break;
        if (job.status === 'failed') throw new Error(job.message || 'Real-ESRGAN không xử lý được ảnh.');
      }
      if (!job || job.status !== 'completed') throw new Error('Tác vụ vượt quá 30 phút. Hãy kiểm tra trạng thái máy chủ hoặc thử ảnh nhỏ hơn.');
      this.assertCurrentSession(session);
      const result = job.result;
      const image = this.root.querySelector('[data-ai-preview]');
      image.src = result.enhanced_path;
      this.root.querySelector('[data-ai-dimensions]').textContent = `${result.width} × ${result.height} · ${result.engine}`;
      const download = this.root.querySelector('[data-ai-download]');
      download.href = `${result.enhanced_path}?download=1`;
      download.download = `enhanced_${result.scale}_${result.width}x${result.height}.png`;
      this.aiResult.hidden = false;
      this.setStatus(`Real-ESRGAN hoàn tất: ${result.width} × ${result.height}.`);
    } catch (error) {
      if (error.name !== 'AbortError' && session === this.jobSession) {
        this.showError(`AI Upscale thất bại: ${error.message}`);
        progress.hidden = true;
      }
    } finally {
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
      if (session === this.jobSession) {
        button.disabled = !this.bitmap || !this.root.querySelector('[data-ai="consent"]').checked;
        if (!this.destroyed) this.updateControls();
      }
    }
  }

  async apiJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`Máy chủ trả phản hồi không hợp lệ (HTTP ${response.status}).`);
    }
    if (!response.ok) throw new Error(payload.error || `Yêu cầu thất bại (HTTP ${response.status}).`);
    return payload;
  }

  assertCurrentSession(session) {
    if (session !== this.jobSession || this.destroyed) throw new DOMException('Tác vụ đã bị dừng.', 'AbortError');
  }

  invalidateAiSession() {
    this.jobSession += 1;
    if (this.aiController) this.aiController.abort();
    this.aiController = null;
  }

  updateOutputSize() {
    if (!this.bitmap) return;
    const scale = Number(this.root.querySelector('[data-export="scale"]').value);
    const size = imageDimensions(this.bitmap, this.state, scale);
    this.root.querySelector('[data-output-size]').textContent = `${size.width} × ${size.height} px`;
  }

  updateValueLabel(key, value) {
    const output = this.root.querySelector(`[data-value="${key}"]`);
    if (output) output.value = value;
  }

  updateControls() {
    const hasImage = Boolean(this.bitmap);
    for (const control of this.root.querySelectorAll('button[data-action], input[data-crop], input[data-setting], select[data-setting], select[data-export], input[data-export], select[data-ai]')) {
      control.disabled = !hasImage;
    }
    this.root.querySelector('[data-action="undo"]').disabled = !hasImage || this.undoStack.length === 0;
    this.root.querySelector('[data-action="redo"]').disabled = !hasImage || this.redoStack.length === 0;
    this.root.querySelector('[data-action="compare"]').disabled = !hasImage;
    this.root.querySelector('[data-action="export"]').disabled = !hasImage;
    this.root.querySelector('[data-ai="consent"]').disabled = !hasImage;
    this.root.querySelector('[data-action="ai"]').disabled = !hasImage || !this.root.querySelector('[data-ai="consent"]').checked;
    this.root.querySelectorAll('[data-scroll]').forEach((button) => { button.disabled = !hasImage; });
  }

  setStatus(message) {
    this.status.textContent = message;
  }

  showError(message) {
    this.error.hidden = !message;
    this.error.textContent = message;
    if (message) this.setStatus('Có lỗi cần xử lý trước khi tiếp tục.');
  }

  destroy() {
    this.destroyed = true;
    this.invalidateAiSession();
    if (this.previewFrame !== null) window.cancelAnimationFrame(this.previewFrame);
    if (this.bitmap) this.bitmap.close();
    if (this.originalUrl) URL.revokeObjectURL(this.originalUrl);
    this.root.querySelector('[data-ai-preview]').removeAttribute('src');
    for (const url of this.downloadUrls) URL.revokeObjectURL(url);
    this.downloadUrls.clear();
    this.container.innerHTML = '';
  }
}

export function mountImageWorkspace(containerEl, module) {
  mountedEditors.get(containerEl)?.destroy();
  const editor = new ImageWorkspace(containerEl, module);
  mountedEditors.set(containerEl, editor);
}

export function unmountImageWorkspace(containerEl) {
  mountedEditors.get(containerEl)?.destroy();
  mountedEditors.delete(containerEl);
}
