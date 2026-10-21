import { deleteProject, getProject, isPersistent, listProjects, saveProject } from './projectStore.js';

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 32_000_000;
const PREVIEW_EDGE = 1600;
const MASK_EDGE = 2048;
const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/bmp']);
const ALLOWED_EXTENSIONS = /\.(jpe?g|png|webp|bmp)$/i;
const CONSENT_KEY = 'pm-image-ai-consent';
const MAX_ZOOM = 16;
const MAX_FRAME_EDGE = 14000;
const CROP_MIN = 8;

const DEFAULT_FILTERS = Object.freeze({
  brightness: 100, contrast: 100, saturation: 100, hue: 0, blur: 0, preset: 'none',
});
const PRESETS = {
  none: { ...DEFAULT_FILTERS },
  warm: { ...DEFAULT_FILTERS, brightness: 103, contrast: 105, saturation: 110, hue: -5, preset: 'warm' },
  mono: { ...DEFAULT_FILTERS, contrast: 108, preset: 'mono' },
  vivid: { ...DEFAULT_FILTERS, brightness: 103, contrast: 108, saturation: 145, preset: 'vivid' },
};

const TOOLS = {
  rotate_left: 'Xoay trái',
  rotate_right: 'Xoay phải',
  flip_x: 'Lật ngang',
  flip_y: 'Lật dọc',
  crop: 'Cắt ảnh',
  adjust: 'Điều chỉnh màu',
  upscale: 'Upscale',
  enhance: 'Tăng nét',
  background: 'Tách nền',
  denoise: 'Khử nhiễu',
  deblur: 'Khử mờ',
  colorize: 'Tô màu ảnh cũ',
  erase: 'Xóa vật thể',
  face_restore: 'Phục hồi khuôn mặt',
};
const LOCAL_TOOLS = new Set(['rotate_left', 'rotate_right', 'flip_x', 'flip_y', 'crop', 'adjust']);
const AI_MODEL_KEY = {
  enhance: 'enhance', background: 'bg', denoise: 'denoise', deblur: 'deblur',
  colorize: 'colorize', erase: 'erase', face_restore: 'face',
};
const EXT_BY_TYPE = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/bmp': 'bmp' };

const mountedStudios = new WeakMap();

/* ---------- tiện ích ---------- */

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`);
const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
const esc = (text) => String(text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDateTime = (ts) => new Date(ts).toLocaleString('vi-VN', { hour12: false });
const fmtTime = (ts) => new Date(ts).toLocaleTimeString('vi-VN', { hour12: false });
const stamp = (ts) => {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
};
const fmtBytes = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`);

function storageGet(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* không lưu được thì hỏi lại lần sau */ }
}

function initialState() {
  return { rotation: 0, flipX: false, flipY: false, crop: { x: 0, y: 0, width: 100, height: 100 }, filters: { ...DEFAULT_FILTERS } };
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
  if (!context) throw new Error('Trình duyệt không thể tạo canvas xử lý ảnh.');
  const presetFilter = { mono: ' grayscale(1)', warm: ' sepia(0.18)' }[state.filters.preset] || '';
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
  context.drawImage(source, cropX, cropY, cropWidth, cropHeight,
    -cropWidth * pixelScale / 2, -cropHeight * pixelScale / 2, cropWidth * pixelScale, cropHeight * pixelScale);
  context.setTransform(1, 0, 0, 1, 0, 0);
  return canvas;
}

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Không thể tạo ảnh. Hãy thử PNG hoặc giảm kích thước.'))), type, quality);
  });
}

function freeCanvas(canvas) {
  if (canvas) { canvas.width = 0; canvas.height = 0; }
}

/* ---------- giao diện ---------- */

const btn = (act, icon, label, extra = '') => `
  <button class="is-btn" type="button" data-act="${act}" ${extra}><span class="is-ico" aria-hidden="true">${icon}</span><span>${label}</span></button>`;

const group = (name, body, cls = '') => `
  <div class="is-group ${cls}"><div class="is-group-body">${body}</div><div class="is-group-name">${name}</div></div>`;

const slider = (key, label, min, max, value, step = 1) => `
  <label class="is-slider">${label}
    <input type="range" min="${min}" max="${max}" step="${step}" value="${value}" data-adjust="${key}" data-needs-image>
    <output data-out="${key}">${value}</output>
  </label>`;

const TEMPLATE = `
  <section class="is-app" aria-label="Image Studio">
    <header class="is-ribbon">
      <div class="is-tabs" role="tablist">
        <button type="button" role="tab" class="is-tab" data-tab="file" aria-selected="true">Tệp</button>
        <button type="button" role="tab" class="is-tab" data-tab="transform" aria-selected="false">Biến đổi</button>
        <button type="button" role="tab" class="is-tab" data-tab="adjust" aria-selected="false">Điều chỉnh</button>
        <button type="button" role="tab" class="is-tab" data-tab="ai" aria-selected="false">AI</button>
        <button type="button" role="tab" class="is-tab" data-tab="projects" aria-selected="false">Dự án <span class="is-count" data-project-count></span></button>
        <span class="is-tabs-spacer"></span>
        <span class="is-project-title" data-project-title>Chưa có dự án</span>
        <button type="button" class="is-link is-history-btn" data-act="back" title="Trở lại bước trước (Ctrl+Z)" disabled>↶ Quay lại</button>
        <button type="button" class="is-link is-history-btn" data-act="reset" title="Đưa ảnh về trạng thái gốc" disabled>⟲ Đặt lại</button>
      </div>

      <div class="is-panel" data-panel="file">
        ${group('Ảnh mới', btn('open', '＋', 'Mở ảnh') + '<input class="is-file" type="file" accept="image/jpeg,image/png,image/webp,image/bmp,.jpg,.jpeg,.png,.webp,.bmp">')}
        ${group('Tải xuống', `
          <label class="is-field">Định dạng
            <select data-export="format"><option value="image/png">PNG</option><option value="image/jpeg">JPEG</option><option value="image/webp">WebP</option></select>
          </label>
          <label class="is-field">Chất lượng
            <span class="is-inline"><input type="range" min="40" max="100" value="92" data-export="quality"><output data-out="quality">92%</output></span>
          </label>
          ${btn('download-result', '↓', 'Tải kết quả', 'data-needs-result')}
          ${btn('download-source', '⇩', 'Tải ảnh nguồn', 'data-needs-image')}`)}
        ${group('Hiển thị', `
          <label class="is-field">Thu phóng
            <select data-zoom>
              <option value="fit">Vừa khung</option><option value="2">200%</option><option value="3">300%</option>
              <option value="4">400%</option><option value="6">600%</option><option value="8">800%</option>
              <option value="custom" hidden>Tùy chỉnh</option>
            </select>
          </label>
          <div class="is-tip">Rê chuột vào khung ảnh rồi <b>lăn chuột</b> để zoom, <b>kéo</b> để di chuyển, <b>nhấp đúp</b> để về vừa khung.</div>`)}
      </div>

      <div class="is-panel" data-panel="transform" hidden>
        ${group('Xoay & lật', `
          ${btn('rotate_left', '↶', 'Xoay trái', 'data-needs-image')}
          ${btn('rotate_right', '↷', 'Xoay phải', 'data-needs-image')}
          ${btn('flip_x', '⇋', 'Lật ngang', 'data-needs-image')}
          ${btn('flip_y', '⇅', 'Lật dọc', 'data-needs-image')}`)}
        ${group('Cắt ảnh', `
          ${btn('crop-mode', '✂', 'Cắt ảnh', 'data-needs-image')}
          <div class="is-crop-box">
            <div class="is-chips" role="group" aria-label="Tỉ lệ khung cắt">
              <button type="button" class="is-chip" data-act="crop-ratio" data-ratio="free" data-needs-image>Tự do</button>
              <button type="button" class="is-chip" data-act="crop-ratio" data-ratio="1" data-needs-image>1 : 1</button>
              <button type="button" class="is-chip" data-act="crop-ratio" data-ratio="0.75" data-needs-image>3 : 4</button>
              <button type="button" class="is-chip" data-act="crop-ratio" data-ratio="1.3333" data-needs-image>4 : 3</button>
              <button type="button" class="is-chip" data-act="crop-ratio" data-ratio="0.5625" data-needs-image>9 : 16</button>
              <button type="button" class="is-chip" data-act="crop-ratio" data-ratio="1.7778" data-needs-image>16 : 9</button>
            </div>
            <span class="is-crop-info" data-crop-info>Bấm "Cắt ảnh" hoặc chọn tỉ lệ</span>
          </div>
          ${btn('crop-apply', '✓', 'Cắt', 'disabled')}
          ${btn('crop-cancel', '✕', 'Hủy', 'disabled')}`)}
      </div>

      <div class="is-panel" data-panel="adjust" hidden>
        ${group('Màu sắc', `
          <div class="is-sliders">
            ${slider('brightness', 'Độ sáng', 0, 200, 100)}
            ${slider('contrast', 'Tương phản', 0, 200, 100)}
            ${slider('saturation', 'Bão hòa', 0, 200, 100)}
            ${slider('hue', 'Sắc độ', -180, 180, 0)}
            ${slider('blur', 'Làm mờ', 0, 12, 0, 0.5)}
          </div>`)}
        ${group('Bộ lọc nhanh', `
          <label class="is-field">Preset
            <select data-adjust-preset data-needs-image>
              <option value="none">Gốc</option><option value="warm">Ấm</option><option value="mono">Đơn sắc</option><option value="vivid">Rực rỡ</option>
            </select>
          </label>
          ${btn('adjust', '✓', 'Áp dụng', 'data-needs-image')}
          ${btn('adjust-reset', '⟲', 'Đặt lại', 'data-needs-image')}`)}
      </div>

      <div class="is-panel" data-panel="ai" hidden>
        ${group('Độ phân giải', `
          <label class="is-field">Tỉ lệ
            <select data-ai="scale" data-needs-image><option value="2x">2×</option><option value="4x" selected>4×</option></select>
          </label>
          <label class="is-field">Mô hình
            <select data-ai="model" data-needs-image><option value="photo">Ảnh chụp</option><option value="anime">Anime</option><option value="fast">Nhanh</option></select>
          </label>
          ${btn('upscale', '⤢', 'Upscale', 'data-needs-image')}
          ${btn('enhance', '✦', 'Tăng nét', 'data-needs-image')}`)}
        ${group('Làm sạch ảnh', `
          ${btn('denoise', '◌', 'Khử nhiễu', 'data-needs-image')}
          ${btn('deblur', '◎', 'Khử mờ', 'data-needs-image')}
          ${btn('face_restore', '☺', 'Phục hồi mặt', 'data-needs-image')}
          ${btn('colorize', '◐', 'Tô màu ảnh cũ', 'data-needs-image')}`)}
        ${group('Tách nền', `
          <label class="is-field">Nền mới
            <select data-ai-background data-needs-image><option value="transparent">Trong suốt</option><option value="custom">Màu tùy chọn</option></select>
          </label>
          <input type="color" value="#ffffff" data-ai-background-color hidden aria-label="Màu nền">
          ${btn('background', '▣', 'Tách nền', 'data-needs-image')}`)}
        ${group('Xóa vật thể', `
          ${btn('erase-mode', '✎', 'Vẽ vùng xóa', 'data-needs-image')}
          <label class="is-field">Cỡ cọ
            <span class="is-inline"><input type="range" min="8" max="120" value="36" data-brush data-needs-mask><output data-out="brush">36 px</output></span>
          </label>
          ${btn('mask-clear', '⌫', 'Xóa nét vẽ', 'data-needs-mask')}
          ${btn('erase', '▶', 'Xóa vật thể', 'data-needs-mask')}`)}
      </div>

      <div class="is-panel" data-panel="projects" hidden>
        <div class="is-projects" data-projects></div>
      </div>
    </header>

    <div class="is-split">
      <section class="is-pane" data-side="left" aria-label="Ảnh nguồn">
        <div class="is-pane-head">
          <div><strong>Ảnh nguồn</strong><span data-meta="left">Chưa có ảnh</span></div>
          <div class="is-pane-actions"><div class="is-zoombar" data-zoombar="left" hidden>
          <button type="button" data-act="zoom-out" title="Thu nhỏ" aria-label="Thu nhỏ">−</button>
          <output data-zoom-out>Vừa khung</output>
          <button type="button" data-act="zoom-in" title="Phóng to" aria-label="Phóng to">＋</button>
          <button type="button" data-act="zoom-fit" title="Vừa khung (nhấp đúp)" aria-label="Vừa khung">⤢</button>
        </div><button type="button" class="is-link" data-act="to-original" hidden>↺ Về ảnh gốc</button></div>
        </div>
        <div class="is-viewport" data-viewport="left">
          <div class="is-empty" data-empty="left">
            <strong>Kéo thả ảnh vào đây</strong>
            <span>hoặc dán từ clipboard · JPEG, PNG, WebP, BMP · tối đa 50 MB / 32 MP</span>
            <button type="button" class="btn btn-primary" data-act="open">Chọn ảnh</button>
          </div>
          <div class="is-frame" data-frame="left" hidden>
            <img alt="Ảnh nguồn" data-img="left" draggable="false">
            <canvas class="is-mask" data-mask hidden></canvas>
            <div class="is-crop" data-crop-layer hidden>
              <div class="is-crop-dim" data-crop-dim></div>
              <div class="is-crop-sel" data-crop-sel hidden>
                <span class="is-crop-label" data-crop-label></span>
                <i class="is-crop-h" data-h="nw"></i><i class="is-crop-h" data-h="n"></i><i class="is-crop-h" data-h="ne"></i>
                <i class="is-crop-h" data-h="e"></i><i class="is-crop-h" data-h="se"></i><i class="is-crop-h" data-h="s"></i>
                <i class="is-crop-h" data-h="sw"></i><i class="is-crop-h" data-h="w"></i>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="is-pane" data-side="right" aria-label="Kết quả">
        <div class="is-pane-head">
          <div><strong>Kết quả</strong><span data-meta="right">Chưa có kết quả</span></div>
          <div class="is-pane-actions">
            <div class="is-zoombar" data-zoombar="right" hidden>
          <button type="button" data-act="zoom-out" title="Thu nhỏ" aria-label="Thu nhỏ">−</button>
          <output data-zoom-out>Vừa khung</output>
          <button type="button" data-act="zoom-in" title="Phóng to" aria-label="Phóng to">＋</button>
          <button type="button" data-act="zoom-fit" title="Vừa khung (nhấp đúp)" aria-label="Vừa khung">⤢</button>
        </div>
            <button type="button" class="is-link is-link-accent" data-act="use-result" hidden>← Dùng làm ảnh nguồn</button>
            <button type="button" class="is-link" data-act="download-result" hidden>↓ Tải</button>
          </div>
        </div>
        <div class="is-viewport" data-viewport="right">
          <div class="is-empty is-empty-quiet" data-empty="right">
            <strong>Kết quả sẽ hiện ở đây</strong>
            <span>Chọn một công cụ trên thanh ruy băng. Mỗi lần chạy sẽ thay kết quả này và được lưu vào dự án.</span>
          </div>
          <div class="is-frame" data-frame="right" hidden>
            <img alt="Kết quả" data-img="right" draggable="false">
            <canvas class="is-live" data-live hidden></canvas>
          </div>
        </div>
      </section>
    </div>

    <section class="is-history" aria-label="Lịch sử dự án">
      <div class="is-history-head" data-history-head></div>
      <div class="is-film" data-film></div>
    </section>

    <footer class="is-status">
      <span class="is-status-msg" data-status role="status" aria-live="polite">Mở một ảnh để bắt đầu — mỗi ảnh là một dự án.</span>
      <span class="is-progress" data-progress hidden><progress max="100" value="0"></progress><button type="button" class="is-link" data-act="cancel">Hủy</button></span>
    </footer>

    <div class="is-overlay" data-overlay hidden role="status" aria-live="polite">
      <div class="is-overlay-card">
        <div class="is-ring" data-ring>
          <svg viewBox="0 0 80 80" aria-hidden="true">
            <circle class="is-ring-bg" cx="40" cy="40" r="34"></circle>
            <circle class="is-ring-fg" cx="40" cy="40" r="34"></circle>
            <path class="is-ring-check" d="M25 41 L36 52 L56 28"></path>
            <path class="is-ring-cross" d="M28 28 L52 52 M52 28 L28 52"></path>
          </svg>
          <span class="is-ring-pct" data-ring-pct></span>
        </div>
        <strong data-overlay-title></strong>
        <span class="is-overlay-msg" data-overlay-msg></span>
        <button type="button" class="is-link" data-act="cancel" data-overlay-cancel>Hủy</button>
        <button type="button" class="is-link" data-act="overlay-close" data-overlay-close hidden>Đóng</button>
      </div>
    </div>

    <dialog class="is-dialog" data-consent>
      <form method="dialog">
        <h3>Gửi ảnh lên máy chủ?</h3>
        <p>Công cụ AI chạy trên máy chủ PM Tools. Ảnh nguồn (khung bên trái) sẽ được gửi lên để xử lý và lưu tạm tối đa 24 giờ. Các chỉnh sửa cục bộ (xoay, cắt, điều chỉnh màu) không gửi ảnh đi đâu.</p>
        <div class="is-dialog-actions">
          <button type="submit" value="no" class="btn btn-secondary btn-sm">Hủy</button>
          <button type="submit" value="yes" class="btn btn-primary btn-sm">Đồng ý và tiếp tục</button>
        </div>
      </form>
    </dialog>
  </section>`;

/* ---------- Studio ---------- */

class ImageStudio {
  constructor(container) {
    this.container = container;
    this.destroyed = false;
    this.project = null;
    this.left = null;
    this.right = null;
    this.live = false;
    this.busy = false;
    this.session = 0;
    this.controller = null;
    this.aiModels = null;
    this.zoomLevel = 1;
    this.panDrag = null;
    this.cropMode = false;
    this.cropRatio = 'free';
    this.cropRect = null;
    this.cropDrag = null;
    this.maskMode = false;
    this.maskDrawing = false;
    this.maskHasContent = false;
    this.maskPointer = null;
    this.previewBitmap = null;
    this.previewKey = null;
    this.previewFrame = null;
    this.syncing = false;
    this.listUrls = [];
    this.filmUrls = [];
    this.consentResolver = null;
    this.undoStack = [];
    this.overlayTimer = null;
    this.render();
    this.bind();
    this.refreshProjects();
  }

  render() {
    this.container.innerHTML = TEMPLATE;
    const q = (sel) => this.container.querySelector(sel);
    this.root = q('.is-app');
    this.fileInput = q('.is-file');
    this.statusEl = q('[data-status]');
    this.progressEl = q('[data-progress]');
    this.dialog = q('[data-consent]');
    this.overlayEl = q('[data-overlay]');
    this.cropLayer = q('[data-crop-layer]');
    this.cropSel = q('[data-crop-sel]');
    this.cropDim = q('[data-crop-dim]');
    this.maskCanvas = q('[data-mask]');
    this.maskCtx = this.maskCanvas.getContext('2d', { willReadFrequently: true });
    this.liveCanvas = q('[data-live]');
    this.view = {
      left: { viewport: q('[data-viewport="left"]'), frame: q('[data-frame="left"]'), img: q('[data-img="left"]'), empty: q('[data-empty="left"]'), meta: q('[data-meta="left"]') },
      right: { viewport: q('[data-viewport="right"]'), frame: q('[data-frame="right"]'), img: q('[data-img="right"]'), empty: q('[data-empty="right"]'), meta: q('[data-meta="right"]') },
    };
    this.updateControls();
    this.renderAll();
  }

  bind() {
    this.root.addEventListener('click', (e) => this.onClick(e));
    this.root.addEventListener('change', (e) => this.onChange(e));
    this.root.addEventListener('input', (e) => this.onInput(e));
    // Phím tắt nghe ở cấp trang để Enter / Esc / Ctrl+Z hoạt động cả khi tiêu điểm đang ở nút vừa bấm.
    this.onKey = (e) => {
      if (!this.root.isConnected) return;
      const tag = e.target.tagName;
      const typing = ['INPUT', 'SELECT', 'TEXTAREA'].includes(tag) || e.target.isContentEditable;
      if (e.key === 'Escape') {
        if (this.overlayEl.dataset.state === 'error') this.hideOverlay();
        else if (this.cropMode) this.exitCropMode();
        else if (this.maskMode) this.exitMaskMode();
      } else if (e.key === 'Enter' && this.cropMode && !typing && !this.dialog.open) {
        const act = e.target.dataset?.act;
        if (tag === 'BUTTON' && !['crop-mode', 'crop-ratio'].includes(act)) return;
        e.preventDefault();
        this.applyCrop();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !typing) {
        e.preventDefault();
        this.goBack();
      }
    };
    document.addEventListener('keydown', this.onKey);
    this.root.addEventListener('dragover', (e) => {
      if (e.dataTransfer?.types.includes('Files')) { e.preventDefault(); this.root.classList.add('is-dragging'); }
    });
    this.root.addEventListener('dragleave', (e) => { if (!this.root.contains(e.relatedTarget)) this.root.classList.remove('is-dragging'); });
    this.root.addEventListener('drop', (e) => {
      if (!e.dataTransfer?.files.length) return;
      e.preventDefault();
      this.root.classList.remove('is-dragging');
      this.openFile(e.dataTransfer.files[0]);
    });
    this.onPaste = (e) => {
      const file = Array.from(e.clipboardData?.items || []).find((item) => item.type.startsWith('image/'))?.getAsFile();
      if (file) { e.preventDefault(); this.openFile(file); }
    };
    document.addEventListener('paste', this.onPaste);
    this.dialog.addEventListener('close', () => {
      const ok = this.dialog.returnValue === 'yes';
      if (ok) storageSet(CONSENT_KEY, '1');
      this.consentResolver?.(ok);
      this.consentResolver = null;
    });
    this.resizeObserver = new ResizeObserver(() => this.layout());
    this.resizeObserver.observe(this.view.left.viewport);
    this.resizeObserver.observe(this.view.right.viewport);
    for (const side of ['left', 'right']) {
      const vp = this.view[side].viewport;
      vp.addEventListener('scroll', () => this.syncScroll(side));
      vp.addEventListener('wheel', (e) => this.onWheel(side, e), { passive: false });
      vp.addEventListener('pointerdown', (e) => this.panDown(side, e));
      vp.addEventListener('pointermove', (e) => this.panMove(e));
      vp.addEventListener('pointerup', (e) => this.panUp(e));
      vp.addEventListener('pointercancel', (e) => this.panUp(e));
      vp.addEventListener('dblclick', (e) => {
        if (this[side] && !e.target.closest('[data-crop-layer]') && e.target !== this.maskCanvas) this.setZoom(1);
      });
    }
    this.cropLayer.addEventListener('pointerdown', (e) => this.cropDown(e));
    this.cropLayer.addEventListener('pointermove', (e) => this.cropMove(e));
    this.cropLayer.addEventListener('pointerup', (e) => this.cropUp(e));
    this.cropLayer.addEventListener('pointercancel', (e) => this.cropUp(e));
    const mc = this.maskCanvas;
    mc.addEventListener('pointerdown', (e) => this.maskDown(e));
    mc.addEventListener('pointermove', (e) => this.maskMove(e));
    mc.addEventListener('pointerup', (e) => this.maskUp(e));
    mc.addEventListener('pointercancel', (e) => this.maskUp(e));
  }

  /* ----- sự kiện ----- */

  onClick(event) {
    const tab = event.target.closest('[data-tab]');
    if (tab) { this.selectTab(tab.dataset.tab); return; }
    const el = event.target.closest('[data-act]');
    if (!el || el.disabled) return;
    const act = el.dataset.act;
    if (act === 'open') this.fileInput.click();
    else if (act === 'download-result') this.downloadImage(this.live ? null : this.right);
    else if (act === 'download-source') this.downloadImage(this.left);
    else if (act === 'use-result') this.useResult();
    else if (act === 'to-original') this.backToOriginal();
    else if (act === 'cancel') this.controller?.abort();
    else if (act === 'overlay-close') this.hideOverlay();
    else if (act === 'back') this.goBack();
    else if (act === 'reset') this.resetToOriginal();
    else if (act === 'crop-mode') { if (this.cropMode) this.exitCropMode(); else this.enterCropMode('free'); }
    else if (act === 'crop-ratio') this.setCropRatio(el.dataset.ratio);
    else if (act === 'crop-apply') this.applyCrop();
    else if (act === 'crop-cancel') this.exitCropMode();
    else if (act === 'zoom-in') this.zoomBy(1.5);
    else if (act === 'zoom-out') this.zoomBy(1 / 1.5);
    else if (act === 'zoom-fit') this.setZoom(1);
    else if (act === 'adjust') this.runTool('adjust', { filters: this.readFilters() });
    else if (act === 'adjust-reset') this.resetAdjust();
    else if (act === 'upscale') this.runTool('upscale', { scale: this.q('[data-ai="scale"]').value, model: this.q('[data-ai="model"]').value });
    else if (act === 'erase-mode') this.toggleMaskMode();
    else if (act === 'mask-clear') this.clearMask();
    else if (act === 'erase') this.runTool('erase', {});
    else if (act === 'card-show') this.showStep(el.dataset.step);
    else if (act === 'card-use') this.useStep(el.dataset.step);
    else if (act === 'card-dl') this.downloadImage(this.imageForStep(el.dataset.step));
    else if (act === 'project-open') this.openProject(el.dataset.id);
    else if (act === 'project-delete') this.removeProject(el.dataset.id);
    else if (TOOLS[act]) this.runTool(act, {});
  }

  onChange(event) {
    const t = event.target;
    if (t === this.fileInput) {
      if (t.files?.[0]) this.openFile(t.files[0]);
      t.value = '';
    } else if (t.matches('[data-zoom]')) {
      if (t.value !== 'custom') this.setZoom(t.value === 'fit' ? 1 : Number(t.value));
    } else if (t.matches('[data-adjust-preset]')) {
      this.setFilters({ ...PRESETS[t.value] });
      this.schedulePreview();
    } else if (t.matches('[data-ai-background]')) {
      this.q('[data-ai-background-color]').hidden = t.value !== 'custom';
    }
  }

  onInput(event) {
    const t = event.target;
    if (t.dataset.adjust) {
      const value = Number(t.value);
      this.q('[data-adjust-preset]').value = 'none';
      this.setOut(t.dataset.adjust, t.dataset.adjust === 'hue' ? `${value}°` : t.dataset.adjust === 'blur' ? `${value} px` : `${value}%`);
      this.schedulePreview();
    } else if (t.dataset.export === 'quality') {
      this.setOut('quality', `${t.value}%`);
    } else if (t.matches('[data-brush]')) {
      this.setOut('brush', `${t.value} px`);
    }
  }

  q(sel) { return this.root.querySelector(sel); }

  setOut(key, text) {
    const out = this.q(`[data-out="${key}"]`);
    if (out) out.value = text;
  }

  selectTab(name) {
    this.root.querySelectorAll('[data-tab]').forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.tab === name)));
    this.root.querySelectorAll('[data-panel]').forEach((panel) => { panel.hidden = panel.dataset.panel !== name; });
    if (name !== 'adjust' && this.live) this.cancelPreview();
    if (name !== 'transform' && this.cropMode) this.exitCropMode(true);
    if (name === 'projects') this.refreshProjects();
    requestAnimationFrame(() => this.layout());
  }

  setStatus(message, isError = false) {
    this.statusEl.textContent = message;
    this.statusEl.classList.toggle('is-error', isError);
    if (isError) this.statusEl.setAttribute('role', 'alert'); else this.statusEl.setAttribute('role', 'status');
    if (!isError && this.overlayEl.dataset.state === 'working') this.q('[data-overlay-msg]').textContent = message;
  }

  /* ----- lớp phủ tiến trình giữa màn hình ----- */

  showOverlay(title) {
    window.clearTimeout(this.overlayTimer);
    this.overlayEl.dataset.state = 'working';
    this.overlayEl.hidden = false;
    this.q('[data-overlay-title]').textContent = title;
    this.q('[data-overlay-msg]').textContent = 'Đang chuẩn bị…';
    this.q('[data-overlay-cancel]').hidden = false;
    this.q('[data-overlay-close]').hidden = true;
    this.setRing(null);
  }

  /** percent: số 0–100 hoặc null (chưa biết → vòng quay). */
  setRing(percent) {
    const ring = this.q('[data-ring]');
    const fg = ring.querySelector('.is-ring-fg');
    const known = Number.isFinite(percent);
    ring.classList.toggle('is-spin', !known);
    const circumference = 2 * Math.PI * 34;
    fg.style.strokeDasharray = `${circumference}`;
    fg.style.strokeDashoffset = known ? `${circumference * (1 - Math.min(100, Math.max(0, percent)) / 100)}` : `${circumference * 0.72}`;
    this.q('[data-ring-pct]').textContent = known ? `${Math.round(percent)}%` : '';
  }

  finishOverlay(ok, message) {
    window.clearTimeout(this.overlayTimer);
    this.overlayEl.dataset.state = ok ? 'done' : 'error';
    this.setRing(ok ? 100 : null);
    this.q('[data-ring]').classList.remove('is-spin');
    this.q('[data-ring-pct]').textContent = '';
    this.q('[data-overlay-title]').textContent = ok ? 'Hoàn tất' : 'Không thành công';
    this.q('[data-overlay-msg]').textContent = message;
    this.q('[data-overlay-cancel]').hidden = true;
    this.q('[data-overlay-close]').hidden = ok;
    if (ok) this.overlayTimer = window.setTimeout(() => this.hideOverlay(), 1300);
  }

  hideOverlay() {
    window.clearTimeout(this.overlayTimer);
    this.overlayEl.hidden = true;
    this.overlayEl.dataset.state = '';
  }

  setBusy(on, message) {
    this.busy = on;
    this.root.classList.toggle('is-busy', on);
    this.progressEl.hidden = !on;
    if (on) this.progressEl.querySelector('progress').removeAttribute('value');
    if (message) this.setStatus(message);
    this.updateControls();
  }

  updateControls() {
    const hasImage = Boolean(this.left);
    const hasResult = Boolean(this.right) && !this.live;
    this.root.querySelectorAll('[data-needs-image]').forEach((el) => { el.disabled = !hasImage || this.busy; });
    this.root.querySelectorAll('[data-needs-result]').forEach((el) => { el.disabled = !hasResult; });
    this.root.querySelectorAll('[data-needs-mask]').forEach((el) => { el.disabled = !this.maskMode || this.busy; });
    const run = this.q('[data-act="erase"]');
    if (run) run.disabled = !this.maskMode || !this.maskHasContent || this.busy;
    const clear = this.q('[data-act="mask-clear"]');
    if (clear) clear.disabled = !this.maskMode || !this.maskHasContent || this.busy;
    const cropOk = this.cropMode && this.cropValid() && !this.busy;
    const cropApply = this.q('[data-act="crop-apply"]');
    if (cropApply) cropApply.disabled = !cropOk;
    const cropCancel = this.q('[data-act="crop-cancel"]');
    if (cropCancel) cropCancel.disabled = !this.cropMode || this.busy;
    const cropBtn = this.q('[data-act="crop-mode"]');
    if (cropBtn) {
      cropBtn.classList.toggle('is-on', this.cropMode);
      cropBtn.querySelector('span:last-child').textContent = this.cropMode ? 'Thoát cắt' : 'Cắt ảnh';
    }
    this.root.querySelectorAll('[data-act="crop-ratio"]').forEach((chip) => {
      chip.classList.toggle('is-on', this.cropMode && chip.dataset.ratio === this.cropRatio);
    });
    const back = this.q('[data-act="back"]');
    if (back) back.disabled = this.busy || this.undoStack.length === 0;
    const reset = this.q('[data-act="reset"]');
    if (reset) reset.disabled = this.busy || !this.project || (this.left?.stepId === 'orig' && !this.right);
    const open = this.q('.is-panel [data-act="open"]');
    if (open) open.disabled = this.busy;
    const modeBtn = this.q('[data-act="erase-mode"]');
    if (modeBtn) {
      modeBtn.classList.toggle('is-on', this.maskMode);
      modeBtn.querySelector('span:last-child').textContent = this.maskMode ? 'Thoát vẽ' : 'Vẽ vùng xóa';
    }
  }

  /* ----- dự án ----- */

  async openFile(file) {
    if (this.busy) return;
    if (!ALLOWED_TYPES.has(file.type) && !ALLOWED_EXTENSIONS.test(file.name)) {
      this.setStatus('Định dạng không hỗ trợ. Hãy chọn JPEG, PNG, WebP hoặc BMP.', true);
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      this.setStatus('Ảnh vượt quá giới hạn 50 MB.', true);
      return;
    }
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch (error) {
      this.setStatus(`Không thể giải mã ảnh: ${error.message || 'file có thể bị hỏng.'}`, true);
      return;
    }
    const { width, height } = bitmap;
    bitmap.close();
    if (width * height > MAX_IMAGE_PIXELS) {
      this.setStatus('Ảnh vượt quá giới hạn 32 megapixel.', true);
      return;
    }
    const now = Date.now();
    const blob = file.slice(0, file.size, file.type || 'image/png');
    const project = {
      id: uid(), name: file.name || `anh-${stamp(now)}`, createdAt: now, updatedAt: now,
      original: blob, width, height, steps: [], sourceStepId: null,
    };
    try {
      await saveProject(project);
    } catch {
      this.setStatus('Không lưu được dự án vào trình duyệt (hết dung lượng?). Dự án chỉ tồn tại đến khi đóng trang.', true);
    }
    this.enterProject(project);
    this.setStatus(`Đã tạo dự án "${project.name}" · ${width} × ${height}.`);
    this.refreshProjects();
  }

  enterProject(project) {
    this.session += 1;
    this.controller?.abort();
    this.exitTools();
    this.cancelPreview();
    this.project = project;
    this.undoStack = [];
    this.zoomLevel = 1;
    this.hideOverlay();
    this.setImage('left', this.imageForStep(project.sourceStepId || 'orig'));
    const last = project.steps[project.steps.length - 1];
    this.setImage('right', last ? this.imageForStep(last.id) : null);
    this.resetAdjustInputs();
    this.renderAll();
  }

  async openProject(id) {
    if (this.busy) return;
    const project = await getProject(id);
    if (!project) { this.setStatus('Không tìm thấy dự án.', true); return; }
    this.enterProject(project);
    this.selectTab('file');
    this.setStatus(`Đã mở dự án "${project.name}".`);
  }

  async removeProject(id) {
    const project = await getProject(id);
    if (!project || !window.confirm(`Xóa dự án "${project.name}" cùng ${project.steps.length} kết quả đã lưu?`)) return;
    await deleteProject(id);
    if (this.project?.id === id) {
      this.project = null;
      this.undoStack = [];
      this.setImage('left', null);
      this.setImage('right', null);
      this.exitTools();
      this.renderAll();
    }
    this.refreshProjects();
    this.setStatus('Đã xóa dự án.');
  }

  async persist() {
    if (!this.project) return;
    this.project.updatedAt = Date.now();
    try { await saveProject(this.project); } catch {
      this.setStatus('Không lưu được dự án vào trình duyệt (hết dung lượng?).', true);
    }
    this.refreshProjects();
  }

  imageForStep(stepId) {
    const p = this.project;
    if (!p) return null;
    if (!stepId || stepId === 'orig') {
      return { blob: p.original, width: p.width, height: p.height, stepId: 'orig', label: 'Ảnh gốc', url: URL.createObjectURL(p.original) };
    }
    const step = p.steps.find((s) => s.id === stepId);
    if (!step) return null;
    return { blob: step.blob, width: step.width, height: step.height, stepId: step.id, label: step.label, url: URL.createObjectURL(step.blob) };
  }

  setImage(side, image) {
    const old = this[side];
    if (old?.url) URL.revokeObjectURL(old.url);
    this[side] = image;
    if (side === 'left') {
      this.previewKey = null;
      this.previewBitmap?.close?.();
      this.previewBitmap = null;
    }
  }

  async commitStep(tool, params, blob, width, height, info) {
    const step = {
      id: uid(), at: Date.now(), tool, label: TOOLS[tool], params, blob, width, height, info: info || '',
      sourceStepId: this.left.stepId === 'orig' ? null : this.left.stepId,
    };
    this.remember();
    this.project.steps.push(step);
    this.setImage('right', this.imageForStep(step.id));
    this.live = false;
    await this.persist();
    this.renderAll();
    this.setStatus(`${step.label} xong: ${width} × ${height}. Kết quả đã lưu vào dự án.`);
  }

  showStep(stepId) {
    if (!this.project || this.busy) return;
    if (this.right?.stepId === stepId && !this.live) return;
    this.remember();
    this.cancelPreview();
    this.setImage('right', this.imageForStep(stepId));
    this.renderAll();
  }

  async useStep(stepId) {
    if (!this.project || this.busy) return;
    this.remember();
    this.cancelPreview();
    this.exitTools();
    this.setImage('left', this.imageForStep(stepId));
    this.project.sourceStepId = stepId === 'orig' ? null : stepId;
    await this.persist();
    if (this.right?.stepId === stepId) this.setImage('right', null);
    this.renderAll();
    this.setStatus('Đã đưa ảnh này vào khung nguồn. Chọn công cụ để chỉnh tiếp.');
  }

  useResult() {
    if (this.right && !this.live) this.useStep(this.right.stepId);
  }

  backToOriginal() { this.useStep('orig'); }

  /* ----- quay lại / đặt lại ----- */

  snapshot() {
    return { left: this.left?.stepId ?? null, right: this.right?.stepId ?? null };
  }

  remember() {
    if (!this.project || !this.left) return;
    this.undoStack.push(this.snapshot());
    if (this.undoStack.length > 200) this.undoStack.shift();
  }

  async applySnapshot(snap) {
    this.cancelPreview();
    this.exitTools();
    this.setImage('left', this.imageForStep(snap.left || 'orig'));
    this.setImage('right', snap.right ? this.imageForStep(snap.right) : null);
    this.project.sourceStepId = !snap.left || snap.left === 'orig' ? null : snap.left;
    this.resetAdjustInputs();
    await this.persist();
    this.renderAll();
  }

  async goBack() {
    if (this.busy || !this.project || !this.undoStack.length) return;
    await this.applySnapshot(this.undoStack.pop());
    this.setStatus('Đã quay lại bước trước. Các kết quả cũ vẫn nằm trong lịch sử dự án.');
  }

  async resetToOriginal() {
    if (this.busy || !this.project) return;
    if (this.left?.stepId === 'orig' && !this.right) return;
    this.remember();
    await this.applySnapshot({ left: 'orig', right: null });
    this.setStatus('Đã đưa ảnh về trạng thái gốc. Bấm "Quay lại" nếu muốn hoàn tác thao tác này.');
  }

  /* ----- hiển thị ----- */

  renderAll() {
    for (const side of ['left', 'right']) {
      const v = this.view[side];
      const image = this[side];
      const showImg = Boolean(image) && !(side === 'right' && this.live);
      v.img.hidden = !showImg;
      if (showImg && v.img.dataset.url !== image.url) { v.img.src = image.url; v.img.dataset.url = image.url; }
      if (!image) { v.img.removeAttribute('src'); delete v.img.dataset.url; }
      const visible = side === 'right' ? (Boolean(image) || this.live) : Boolean(image);
      v.empty.hidden = visible;
      v.frame.hidden = !visible;
      this.q(`[data-zoombar="${side}"]`).hidden = !visible;
    }
    const L = this.left;
    const R = this.right;
    this.view.left.meta.textContent = L ? `${L.label} · ${L.width} × ${L.height}` : 'Chưa có ảnh';
    this.view.right.meta.textContent = this.live
      ? 'Xem trước điều chỉnh (chưa áp dụng)'
      : (R ? `${R.label} · ${R.width} × ${R.height}` : 'Chưa có kết quả');
    this.q('[data-act="to-original"]').hidden = !L || L.stepId === 'orig';
    this.q('[data-act="use-result"]').hidden = !R || this.live;
    this.q('.is-pane-actions [data-act="download-result"]').hidden = !R || this.live;
    this.root.querySelector('[data-side="right"]').classList.toggle('is-live', this.live);
    this.q('[data-project-title]').textContent = this.project ? `${this.project.name} · ${fmtDateTime(this.project.createdAt)}` : 'Chưa có dự án';
    this.renderHistory();
    this.updateControls();
    this.layout();
    this.updateZoomUi();
  }

  fitScale(side) {
    const dims = side === 'right' && this.live ? this.left : this[side];
    const vp = this.view[side].viewport;
    if (!dims) return 1;
    const vw = vp.clientWidth - 28;
    const vh = vp.clientHeight - 28;
    if (vw <= 0 || vh <= 0) return 0;
    return Math.min(vw / dims.width, vh / dims.height, 2);
  }

  layout() {
    for (const side of ['left', 'right']) {
      const v = this.view[side];
      const dims = side === 'right' && this.live ? this.left : this[side];
      if (!dims) continue;
      const fit = this.fitScale(side);
      if (fit <= 0) continue;
      const scale = Math.min(fit * this.zoomLevel, MAX_FRAME_EDGE / Math.max(dims.width, dims.height));
      v.frame.style.width = `${Math.max(1, Math.round(dims.width * scale))}px`;
      v.frame.style.height = `${Math.max(1, Math.round(dims.height * scale))}px`;
      v.viewport.classList.toggle('is-zoomed', this.zoomLevel > 1);
    }
  }

  syncScroll(from) {
    if (this.syncing || this.zoomLevel === 1) return;
    const a = this.view[from].viewport;
    const b = this.view[from === 'left' ? 'right' : 'left'].viewport;
    const ratioX = a.scrollLeft / Math.max(1, a.scrollWidth - a.clientWidth);
    const ratioY = a.scrollTop / Math.max(1, a.scrollHeight - a.clientHeight);
    this.syncing = true;
    b.scrollLeft = ratioX * (b.scrollWidth - b.clientWidth);
    b.scrollTop = ratioY * (b.scrollHeight - b.clientHeight);
    window.requestAnimationFrame(() => { this.syncing = false; });
  }

  /* ----- zoom nhanh: lăn chuột, kéo để di chuyển, nhấp đúp về vừa khung ----- */

  updateZoomUi() {
    const label = this.zoomLevel === 1 ? 'Vừa khung' : `${Math.round(this.zoomLevel * 100)}%`;
    this.root.querySelectorAll('[data-zoom-out]').forEach((out) => { out.value = label; });
    const select = this.q('[data-zoom]');
    if (select) {
      const known = [...select.options].find((o) => o.value !== 'custom' && (o.value === 'fit' ? 1 : Number(o.value)) === this.zoomLevel);
      select.value = known ? known.value : 'custom';
    }
  }

  /** anchor: { side, clientX, clientY } - điểm ảnh dưới con trỏ được giữ nguyên chỗ khi zoom. */
  setZoom(level, anchor = null) {
    const next = Math.min(MAX_ZOOM, Math.max(1, Math.round(level * 1000) / 1000));
    if (next === this.zoomLevel) return;
    const side = anchor?.side || 'left';
    const vp = this.view[side].viewport;
    const frame = this.view[side].frame;
    const vpRect = vp.getBoundingClientRect();
    const cx = anchor ? anchor.clientX : vpRect.left + vp.clientWidth / 2;
    const cy = anchor ? anchor.clientY : vpRect.top + vp.clientHeight / 2;
    const before = frame.getBoundingClientRect();
    const fx = before.width ? Math.min(1, Math.max(0, (cx - before.left) / before.width)) : 0.5;
    const fy = before.height ? Math.min(1, Math.max(0, (cy - before.top) / before.height)) : 0.5;
    this.zoomLevel = next;
    this.layout();
    if (next === 1) {
      for (const s of ['left', 'right']) { this.view[s].viewport.scrollLeft = 0; this.view[s].viewport.scrollTop = 0; }
    } else {
      const after = frame.getBoundingClientRect();
      vp.scrollLeft += after.left + fx * after.width - cx;
      vp.scrollTop += after.top + fy * after.height - cy;
      this.syncing = false;
      this.syncScroll(side);
    }
    this.updateZoomUi();
  }

  zoomBy(factor) { this.setZoom(this.zoomLevel * factor); }

  onWheel(side, event) {
    if (!this[side]) return;
    event.preventDefault();
    const unit = event.deltaMode === 1 ? 0.05 : 0.0016;
    let next = this.zoomLevel * Math.exp(-event.deltaY * unit);
    if (Math.abs(next - 1) < 0.04) next = 1;
    this.setZoom(next, { side, clientX: event.clientX, clientY: event.clientY });
  }

  panDown(side, event) {
    if (this.zoomLevel <= 1 || !this[side]) return;
    const onTool = event.target.closest('[data-crop-layer]') || (this.maskMode && event.target === this.maskCanvas);
    if ((onTool && event.button !== 1) || (event.button !== 0 && event.button !== 1)) return;
    const vp = this.view[side].viewport;
    const rect = vp.getBoundingClientRect();
    if (event.clientX > rect.left + vp.clientWidth || event.clientY > rect.top + vp.clientHeight) return;
    event.preventDefault();
    this.panDrag = { side, id: event.pointerId, x: event.clientX, y: event.clientY, left: vp.scrollLeft, top: vp.scrollTop };
    vp.setPointerCapture(event.pointerId);
    vp.classList.add('is-panning');
  }

  panMove(event) {
    const drag = this.panDrag;
    if (!drag || event.pointerId !== drag.id) return;
    const vp = this.view[drag.side].viewport;
    vp.scrollLeft = drag.left - (event.clientX - drag.x);
    vp.scrollTop = drag.top - (event.clientY - drag.y);
  }

  panUp(event) {
    const drag = this.panDrag;
    if (!drag || event.pointerId !== drag.id) return;
    const vp = this.view[drag.side].viewport;
    if (vp.hasPointerCapture(event.pointerId)) vp.releasePointerCapture(event.pointerId);
    vp.classList.remove('is-panning');
    this.panDrag = null;
  }

  renderHistory() {
    this.filmUrls.forEach((u) => URL.revokeObjectURL(u));
    this.filmUrls = [];
    const head = this.q('[data-history-head]');
    const film = this.q('[data-film]');
    const p = this.project;
    if (!p) {
      head.innerHTML = '<strong>Lịch sử dự án</strong><span>Chưa có dự án nào đang mở.</span>';
      film.innerHTML = '';
      return;
    }
    const tools = [...new Set(p.steps.map((s) => s.label))];
    head.innerHTML = `<strong>${esc(p.name)}</strong>
      <span>Tạo lúc ${fmtDateTime(p.createdAt)}</span>
      <span>${p.width} × ${p.height} · ${p.steps.length} kết quả</span>
      <span class="is-tools-used">Công cụ đã dùng: ${tools.length ? tools.map(esc).join(' · ') : 'chưa dùng'}</span>`;
    const card = (id, title, sub, blob, extra = '') => {
      const url = URL.createObjectURL(blob);
      this.filmUrls.push(url);
      const onRight = this.right?.stepId === id && !this.live;
      const isSource = this.left?.stepId === id;
      return `<article class="is-card${onRight ? ' is-shown' : ''}${isSource ? ' is-source' : ''}">
        <button type="button" class="is-thumb" data-act="card-show" data-step="${id}" title="Xem ở khung kết quả"><img src="${url}" alt="${esc(title)}" draggable="false"></button>
        <div class="is-card-info"><strong>${esc(title)}</strong><span>${sub}</span>${extra}</div>
        <div class="is-card-actions">
          <button type="button" data-act="card-use" data-step="${id}" title="Đưa vào khung nguồn">←</button>
          <button type="button" data-act="card-dl" data-step="${id}" title="Tải xuống">↓</button>
        </div>
        ${isSource ? '<span class="is-badge">Nguồn</span>' : ''}
      </article>`;
    };
    film.innerHTML = card('orig', 'Ảnh gốc', `${fmtTime(p.createdAt)} · ${p.width}×${p.height}`, p.original)
      + p.steps.map((s) => card(s.id, s.label, `${fmtTime(s.at)} · ${s.width}×${s.height}`, s.blob)).join('');
  }

  async refreshProjects() {
    if (this.destroyed) return;
    const list = await listProjects();
    if (this.destroyed) return;
    this.q('[data-project-count]').textContent = list.length ? String(list.length) : '';
    const holder = this.q('[data-projects]');
    this.listUrls.forEach((u) => URL.revokeObjectURL(u));
    this.listUrls = [];
    if (!list.length) {
      holder.innerHTML = '<div class="is-projects-empty">Chưa có dự án. Mở một ảnh để tạo dự án đầu tiên.</div>';
      return;
    }
    const note = isPersistent() ? '' : '<div class="is-projects-note">Trình duyệt không cho lưu lâu dài — dự án chỉ giữ đến khi đóng trang.</div>';
    holder.innerHTML = note + list.map((p) => {
      const url = URL.createObjectURL(p.original);
      this.listUrls.push(url);
      const tools = [...new Set(p.steps.map((s) => s.label))];
      return `<article class="is-project${this.project?.id === p.id ? ' is-current' : ''}">
        <img src="${url}" alt="" draggable="false">
        <div class="is-project-info">
          <strong title="${esc(p.name)}">${esc(p.name)}</strong>
          <span>${fmtDateTime(p.createdAt)}</span>
          <span>${p.steps.length} kết quả${tools.length ? ' · ' + esc(tools.slice(0, 3).join(', ')) + (tools.length > 3 ? '…' : '') : ''}</span>
        </div>
        <div class="is-project-actions">
          <button type="button" class="btn btn-secondary btn-sm" data-act="project-open" data-id="${p.id}">Mở</button>
          <button type="button" class="is-link" data-act="project-delete" data-id="${p.id}">Xóa</button>
        </div>
      </article>`;
    }).join('');
  }

  /* ----- công cụ cục bộ ----- */

  /* ----- cắt ảnh kiểu Snipping Tool ----- */

  exitTools() {
    this.exitMaskMode(true);
    this.exitCropMode(true);
  }

  cropValid() {
    const r = this.cropRect;
    return Boolean(r) && r.w >= CROP_MIN && r.h >= CROP_MIN;
  }

  enterCropMode(ratio = 'free') {
    if (!this.left || this.busy) return;
    this.exitMaskMode(true);
    this.cancelPreview();
    this.cropMode = true;
    this.cropRatio = ratio;
    this.cropRect = ratio === 'free' ? null : this.fitRatioRect(Number(ratio), null);
    this.cropLayer.hidden = false;
    this.drawCrop();
    this.setStatus(ratio === 'free'
      ? 'Kéo chuột trên ảnh nguồn để chọn vùng cần cắt, rồi bấm "Cắt" (hoặc Enter). Esc để thoát.'
      : 'Kéo khung để di chuyển, kéo góc để đổi kích thước, rồi bấm "Cắt" (hoặc Enter). Esc để thoát.');
    this.updateControls();
  }

  exitCropMode(silent = false) {
    if (!this.cropMode && this.cropLayer.hidden) return;
    this.cropMode = false;
    this.cropRect = null;
    this.cropDrag = null;
    this.cropLayer.hidden = true;
    this.cropSel.hidden = true;
    this.q('[data-crop-info]').textContent = 'Bấm "Cắt ảnh" hoặc chọn tỉ lệ';
    if (!silent) this.setStatus('Đã thoát chế độ cắt ảnh.');
    this.updateControls();
  }

  setCropRatio(ratio) {
    if (!this.left || this.busy) return;
    if (!this.cropMode) { this.enterCropMode(ratio); return; }
    this.cropRatio = ratio;
    if (ratio !== 'free') this.cropRect = this.fitRatioRect(Number(ratio), this.cropRect);
    this.drawCrop();
    this.updateControls();
    this.setStatus(ratio === 'free' ? 'Cắt tự do: kéo chuột để chọn vùng bất kỳ.' : 'Khung cắt tỉ lệ cố định. Kéo để di chuyển, kéo góc để đổi cỡ.');
  }

  /** Khung lớn nhất theo tỉ lệ r (rộng/cao) nằm trọn trong bounds (mặc định cả ảnh), căn giữa. */
  fitRatioRect(r, bounds) {
    const W = this.left.width;
    const H = this.left.height;
    const b = bounds && bounds.w >= CROP_MIN && bounds.h >= CROP_MIN ? bounds : { x: 0, y: 0, w: W, h: H };
    let w = b.w;
    let h = w / r;
    if (h > b.h) { h = b.h; w = h * r; }
    return { x: b.x + (b.w - w) / 2, y: b.y + (b.h - h) / 2, w, h };
  }

  drawCrop() {
    const W = this.left?.width || 1;
    const H = this.left?.height || 1;
    const r = this.cropRect;
    this.cropLayer.classList.toggle('is-no-sel', !r);
    this.cropSel.hidden = !r;
    this.cropSel.classList.toggle('is-ratio', this.cropRatio !== 'free');
    const info = this.q('[data-crop-info]');
    if (!r) {
      this.cropDim.style.clipPath = 'none';
      info.textContent = 'Kéo chuột trên ảnh để chọn vùng';
      return;
    }
    const x1 = (r.x / W) * 100;
    const y1 = (r.y / H) * 100;
    const x2 = ((r.x + r.w) / W) * 100;
    const y2 = ((r.y + r.h) / H) * 100;
    Object.assign(this.cropSel.style, { left: `${x1}%`, top: `${y1}%`, width: `${x2 - x1}%`, height: `${y2 - y1}%` });
    this.cropDim.style.clipPath = `polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${x1}% ${y1}%, ${x1}% ${y2}%, ${x2}% ${y2}%, ${x2}% ${y1}%, ${x1}% ${y1}%)`;
    const text = `${Math.round(r.w)} × ${Math.round(r.h)} px`;
    this.q('[data-crop-label]').textContent = text;
    info.textContent = `Vùng chọn: ${text}`;
  }

  cropPoint(event) {
    const rect = this.view.left.frame.getBoundingClientRect();
    const W = this.left.width;
    const H = this.left.height;
    return {
      x: Math.min(W, Math.max(0, ((event.clientX - rect.left) / rect.width) * W)),
      y: Math.min(H, Math.max(0, ((event.clientY - rect.top) / rect.height) * H)),
    };
  }

  rectFromAnchor(ax, ay, px, py, ratio) {
    const W = this.left.width;
    const H = this.left.height;
    const sx = px >= ax ? 1 : -1;
    const sy = py >= ay ? 1 : -1;
    let w = Math.abs(px - ax);
    let h = Math.abs(py - ay);
    const maxW = sx > 0 ? W - ax : ax;
    const maxH = sy > 0 ? H - ay : ay;
    if (ratio) {
      if (w / ratio > h) h = w / ratio; else w = h * ratio;
      if (w > maxW) { w = maxW; h = w / ratio; }
      if (h > maxH) { h = maxH; w = h * ratio; }
    } else {
      w = Math.min(w, maxW);
      h = Math.min(h, maxH);
    }
    return { x: sx > 0 ? ax : ax - w, y: sy > 0 ? ay : ay - h, w, h };
  }

  cropDown(event) {
    if (!this.cropMode || this.busy || event.button !== 0) return;
    event.preventDefault();
    const p = this.cropPoint(event);
    const handle = event.target.dataset?.h;
    const r = this.cropRect;
    const inside = r && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;
    const drag = { id: event.pointerId, start: p, rect: r ? { ...r } : null, mode: 'new', handle: null, anchor: p };
    if (handle && r) {
      drag.mode = 'resize';
      drag.handle = handle;
      drag.anchor = {
        x: handle.includes('w') ? r.x + r.w : r.x,
        y: handle.includes('n') ? r.y + r.h : r.y,
      };
    } else if (inside) {
      drag.mode = 'move';
    } else {
      this.cropRect = null;
    }
    this.cropDrag = drag;
    this.cropLayer.setPointerCapture(event.pointerId);
    this.drawCrop();
  }

  cropMove(event) {
    const d = this.cropDrag;
    if (!d || event.pointerId !== d.id) return;
    const p = this.cropPoint(event);
    const W = this.left.width;
    const H = this.left.height;
    const ratio = this.cropRatio === 'free' ? null : Number(this.cropRatio);
    if (d.mode === 'new') {
      this.cropRect = this.rectFromAnchor(d.anchor.x, d.anchor.y, p.x, p.y, ratio);
    } else if (d.mode === 'move') {
      const r = d.rect;
      this.cropRect = {
        ...r,
        x: Math.min(W - r.w, Math.max(0, r.x + p.x - d.start.x)),
        y: Math.min(H - r.h, Math.max(0, r.y + p.y - d.start.y)),
      };
    } else if (ratio) {
      this.cropRect = this.rectFromAnchor(d.anchor.x, d.anchor.y, p.x, p.y, ratio);
    } else {
      const r = d.rect;
      let x1 = r.x;
      let y1 = r.y;
      let x2 = r.x + r.w;
      let y2 = r.y + r.h;
      if (d.handle.includes('w')) x1 = Math.min(x2 - CROP_MIN, Math.max(0, p.x));
      if (d.handle.includes('e')) x2 = Math.max(x1 + CROP_MIN, Math.min(W, p.x));
      if (d.handle.includes('n')) y1 = Math.min(y2 - CROP_MIN, Math.max(0, p.y));
      if (d.handle.includes('s')) y2 = Math.max(y1 + CROP_MIN, Math.min(H, p.y));
      this.cropRect = { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
    }
    this.drawCrop();
  }

  cropUp(event) {
    const d = this.cropDrag;
    if (!d || event.pointerId !== d.id) return;
    if (this.cropLayer.hasPointerCapture(event.pointerId)) this.cropLayer.releasePointerCapture(event.pointerId);
    this.cropDrag = null;
    if (this.cropRect && (this.cropRect.w < CROP_MIN || this.cropRect.h < CROP_MIN)) this.cropRect = d.mode === 'new' ? null : d.rect;
    this.drawCrop();
    this.updateControls();
  }

  applyCrop() {
    if (!this.cropMode || !this.cropValid() || this.busy) return;
    const W = this.left.width;
    const H = this.left.height;
    const r = this.cropRect;
    const x = Math.max(0, Math.round(r.x));
    const y = Math.max(0, Math.round(r.y));
    const rect = { x, y, w: Math.min(W - x, Math.round(r.w)), h: Math.min(H - y, Math.round(r.h)) };
    this.runTool('crop', { rect });
  }

  readFilters() {
    const f = { ...DEFAULT_FILTERS };
    this.root.querySelectorAll('[data-adjust]').forEach((input) => { f[input.dataset.adjust] = Number(input.value); });
    f.preset = this.q('[data-adjust-preset]').value;
    return f;
  }

  setFilters(f) {
    for (const [key, value] of Object.entries(f)) {
      const input = this.q(`[data-adjust="${key}"]`);
      if (!input) continue;
      input.value = value;
      this.setOut(key, key === 'hue' ? `${value}°` : key === 'blur' ? `${value} px` : `${value}%`);
    }
    this.q('[data-adjust-preset]').value = f.preset || 'none';
  }

  resetAdjustInputs() { this.setFilters({ ...DEFAULT_FILTERS }); }

  resetAdjust() {
    this.resetAdjustInputs();
    this.cancelPreview();
  }

  schedulePreview() {
    if (!this.left || this.previewFrame !== null) return;
    this.previewFrame = window.requestAnimationFrame(async () => {
      this.previewFrame = null;
      const filters = this.readFilters();
      const neutral = JSON.stringify(filters) === JSON.stringify(DEFAULT_FILTERS);
      if (neutral) { this.cancelPreview(); return; }
      try {
        if (!this.previewBitmap || this.previewKey !== this.left.url) {
          const key = this.left.url;
          const bitmap = await createImageBitmap(this.left.blob);
          if (!this.left || this.left.url !== key) { bitmap.close(); return; }
          this.previewBitmap?.close?.();
          this.previewBitmap = bitmap;
          this.previewKey = key;
        }
        const scale = Math.min(1, PREVIEW_EDGE / Math.max(this.previewBitmap.width, this.previewBitmap.height));
        const state = initialState();
        state.filters = this.readFilters();
        const canvas = drawImage(this.previewBitmap, state, scale);
        this.liveCanvas.width = canvas.width;
        this.liveCanvas.height = canvas.height;
        this.liveCanvas.getContext('2d').drawImage(canvas, 0, 0);
        freeCanvas(canvas);
        this.liveCanvas.hidden = false;
        this.live = true;
        this.renderAll();
      } catch (error) {
        this.setStatus(`Không tạo được bản xem trước: ${error.message}`, true);
      }
    });
  }

  cancelPreview() {
    if (this.previewFrame !== null) { window.cancelAnimationFrame(this.previewFrame); this.previewFrame = null; }
    if (!this.live) return;
    this.live = false;
    this.liveCanvas.hidden = true;
    if (!this.destroyed) this.renderAll();
  }

  async runLocal(tool, params) {
    const bitmap = await createImageBitmap(this.left.blob);
    if (tool === 'crop') {
      const r = params.rect;
      const canvas = document.createElement('canvas');
      canvas.width = r.w;
      canvas.height = r.h;
      try {
        canvas.getContext('2d').drawImage(bitmap, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h);
        return { blob: await canvasBlob(canvas, 'image/png', 1), width: r.w, height: r.h };
      } finally {
        bitmap.close();
        freeCanvas(canvas);
      }
    }
    const state = initialState();
    if (tool === 'rotate_left') state.rotation = 3;
    else if (tool === 'rotate_right') state.rotation = 1;
    else if (tool === 'flip_x') state.flipX = true;
    else if (tool === 'flip_y') state.flipY = true;
    else if (tool === 'adjust') state.filters = { ...params.filters };
    let canvas;
    try {
      canvas = drawImage(bitmap, state, 1);
      const blob = await canvasBlob(canvas, 'image/png', 1);
      return { blob, width: canvas.width, height: canvas.height };
    } finally {
      bitmap.close();
      freeCanvas(canvas);
    }
  }

  /* ----- công cụ AI trên máy chủ ----- */

  ensureConsent() {
    if (storageGet(CONSENT_KEY) === '1') return Promise.resolve(true);
    return new Promise((resolve) => {
      this.consentResolver = resolve;
      if (typeof this.dialog.showModal === 'function') this.dialog.showModal();
      else resolve(window.confirm('Công cụ AI sẽ gửi ảnh nguồn lên máy chủ PM Tools để xử lý (lưu tạm tối đa 24 giờ). Tiếp tục?'));
    });
  }

  async api(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    let payload;
    try { payload = await response.json(); } catch { throw new Error(`Máy chủ trả phản hồi không hợp lệ (HTTP ${response.status}).`); }
    if (!response.ok) throw new Error(payload.error || `Yêu cầu thất bại (HTTP ${response.status}).`);
    return payload;
  }

  async ensureModel(tool, signal) {
    const key = AI_MODEL_KEY[tool];
    this.aiModels = await this.api('/api/image/ai/models', { signal });
    if (!this.aiModels.runtime_available) throw new Error('Máy chủ chưa sẵn sàng ONNX Runtime.');
    if (this.aiModels.models[key]?.available) return;
    const label = this.aiModels.models[key]?.label || key;
    this.setStatus(`Đang tải model "${label}" lần đầu…`);
    await this.api(`/api/image/ai/models/${encodeURIComponent(key)}`, { method: 'POST', signal });
    const deadline = Date.now() + 60 * 60 * 1000;
    while (Date.now() < deadline) {
      await delay(1500);
      if (signal.aborted) throw new DOMException('Đã hủy', 'AbortError');
      this.aiModels = await this.api('/api/image/ai/models', { signal });
      const m = this.aiModels.models[key];
      if (m.available) return;
      if (m.status === 'error') throw new Error(m.error || 'Tải model thất bại.');
      this.setRing(Number(m.progress) > 0 ? Number(m.progress) : null);
      this.setStatus(`Đang tải model "${label}"… ${Math.round(m.progress || 0)}%`);
    }
    throw new Error('Tải model quá thời hạn 60 phút.');
  }

  async buildMask() {
    const src = this.maskCanvas;
    const data = this.maskCtx.getImageData(0, 0, src.width, src.height);
    const out = new ImageData(src.width, src.height);
    for (let i = 0; i < data.data.length; i += 4) {
      const on = data.data[i + 3] > 20 ? 255 : 0;
      out.data[i] = on; out.data[i + 1] = on; out.data[i + 2] = on; out.data[i + 3] = 255;
    }
    const canvas = document.createElement('canvas');
    canvas.width = src.width;
    canvas.height = src.height;
    canvas.getContext('2d').putImageData(out, 0, 0);
    try { return await canvasBlob(canvas, 'image/png', 1); } finally { freeCanvas(canvas); }
  }

  async runServer(tool, params, signal) {
    let maskBlob = null;
    if (tool === 'erase') {
      if (!this.maskHasContent) throw new Error('Hãy vẽ lên vùng cần xóa trước.');
      maskBlob = await this.buildMask();
    }
    if (tool !== 'upscale') await this.ensureModel(tool, signal);

    const src = this.left.blob;
    const type = ALLOWED_TYPES.has(src.type) ? src.type : 'image/png';
    const form = new FormData();
    form.append('image', new File([src], `source.${EXT_BY_TYPE[type]}`, { type }));
    this.setStatus(`Đang gửi ảnh nguồn lên máy chủ (${fmtBytes(src.size)})…`);
    const uploaded = await this.api('/api/image/upload', { method: 'POST', body: form, signal });

    let started;
    if (tool === 'upscale') {
      started = await this.api('/api/image/process', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
        body: JSON.stringify({ job_id: uploaded.job_id, scale: params.scale, model: params.model }),
      });
    } else {
      const toolForm = new FormData();
      toolForm.append('job_id', uploaded.job_id);
      if (tool === 'background') {
        const choice = this.q('[data-ai-background]').value;
        toolForm.append('background', choice === 'custom' ? this.q('[data-ai-background-color]').value : 'transparent');
      }
      if (maskBlob) toolForm.append('mask', new File([maskBlob], 'mask.png', { type: 'image/png' }));
      started = await this.api(`/api/image/ai/${encodeURIComponent(tool)}`, { method: 'POST', body: toolForm, signal });
    }

    const progress = this.progressEl.querySelector('progress');
    const deadline = Date.now() + 60 * 60 * 1000;
    let job;
    while (Date.now() < deadline) {
      await delay(1000);
      if (signal.aborted) throw new DOMException('Đã hủy', 'AbortError');
      job = await this.api(`/api/job/${encodeURIComponent(started.job_id)}`, { signal });
      if (Number(job.progress) > 0) progress.value = Math.min(100, Number(job.progress));
      this.setRing(Number(job.progress) > 0 ? Number(job.progress) : null);
      if (job.message) this.setStatus(job.message);
      if (job.status === 'completed') break;
      if (job.status === 'failed') throw new Error(job.message || 'Máy chủ không xử lý được ảnh.');
    }
    if (!job || job.status !== 'completed') throw new Error('Tác vụ vượt quá 60 phút.');
    const result = job.result;
    const response = await fetch(result.enhanced_path, { credentials: 'same-origin', signal });
    if (!response.ok) throw new Error(`Không tải được kết quả (HTTP ${response.status}).`);
    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) throw new Error('Máy chủ không trả về ảnh hợp lệ.');
    return { blob, width: result.width, height: result.height, info: result.engine };
  }

  async runTool(tool, params = {}) {
    if (this.busy || !this.left || !this.project) return;
    const isServer = !LOCAL_TOOLS.has(tool);
    if (isServer && !(await this.ensureConsent())) { this.setStatus('Đã hủy: chưa đồng ý gửi ảnh lên máy chủ.'); return; }
    this.cancelPreview();
    const session = this.session;
    const controller = new AbortController();
    this.controller = controller;
    this.setBusy(true, `${TOOLS[tool]}…`);
    if (isServer) this.showOverlay(TOOLS[tool]);
    try {
      const out = isServer ? await this.runServer(tool, params, controller.signal) : await this.runLocal(tool, params);
      if (session !== this.session || this.destroyed) return;
      await this.commitStep(tool, params, out.blob, out.width, out.height, out.info);
      if (isServer) this.finishOverlay(true, `${out.width} × ${out.height} · đã lưu vào dự án`);
      if (tool === 'erase') this.exitMaskMode(true);
      if (tool === 'crop') this.exitCropMode(true);
      if (tool === 'adjust') this.resetAdjustInputs();
    } catch (error) {
      if (this.destroyed) return;
      if (error.name === 'AbortError') { this.hideOverlay(); this.setStatus('Đã hủy tác vụ.'); }
      else if (session === this.session) {
        this.setStatus(`${TOOLS[tool]} thất bại: ${error.message}`, true);
        if (isServer) this.finishOverlay(false, error.message);
      }
    } finally {
      if (!this.destroyed && session === this.session) { this.controller = null; this.setBusy(false); }
    }
  }

  /* ----- vẽ vùng xóa ----- */

  toggleMaskMode() {
    if (this.maskMode) this.exitMaskMode(); else this.enterMaskMode();
  }

  enterMaskMode() {
    if (!this.left) return;
    this.cancelPreview();
    this.exitCropMode(true);
    const scale = Math.min(1, MASK_EDGE / Math.max(this.left.width, this.left.height));
    this.maskCanvas.width = Math.max(1, Math.round(this.left.width * scale));
    this.maskCanvas.height = Math.max(1, Math.round(this.left.height * scale));
    this.maskHasContent = false;
    this.maskMode = true;
    this.maskCanvas.hidden = false;
    this.maskCanvas.classList.add('is-drawing');
    this.setStatus('Tô lên vật thể cần xóa trong khung nguồn, rồi bấm "Xóa vật thể". Nhấn Esc để thoát.');
    this.updateControls();
  }

  exitMaskMode(silent = false) {
    this.maskMode = false;
    this.maskDrawing = false;
    this.maskHasContent = false;
    this.maskCanvas.hidden = true;
    this.maskCanvas.classList.remove('is-drawing');
    if (this.maskCtx) this.maskCtx.clearRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
    if (!silent) this.setStatus('Đã thoát chế độ vẽ vùng xóa.');
    this.updateControls();
  }

  clearMask() {
    this.maskCtx.clearRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
    this.maskHasContent = false;
    this.updateControls();
  }

  maskPoint(event) {
    const rect = this.maskCanvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * this.maskCanvas.width / rect.width,
      y: (event.clientY - rect.top) * this.maskCanvas.height / rect.height,
      k: this.maskCanvas.width / rect.width,
    };
  }

  maskDown(event) {
    if (!this.maskMode || this.busy) return;
    event.preventDefault();
    this.maskPointer = event.pointerId;
    this.maskCanvas.setPointerCapture(event.pointerId);
    const p = this.maskPoint(event);
    const ctx = this.maskCtx;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = 'rgba(253, 91, 56, 0.6)';
    ctx.lineWidth = Number(this.q('[data-brush]').value) * p.k;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x + 0.01, p.y + 0.01);
    ctx.stroke();
    this.maskDrawing = true;
    this.maskHasContent = true;
  }

  maskMove(event) {
    if (!this.maskDrawing || event.pointerId !== this.maskPointer) return;
    const p = this.maskPoint(event);
    this.maskCtx.lineTo(p.x, p.y);
    this.maskCtx.stroke();
  }

  maskUp(event) {
    if (event.pointerId !== this.maskPointer) return;
    if (this.maskCanvas.hasPointerCapture(event.pointerId)) this.maskCanvas.releasePointerCapture(event.pointerId);
    this.maskDrawing = false;
    this.maskPointer = null;
    this.updateControls();
  }

  /* ----- tải xuống ----- */

  async downloadImage(image) {
    const target = image || (this.right && !this.live ? this.right : null);
    if (!target) return;
    const type = this.q('[data-export="format"]').value;
    const quality = Number(this.q('[data-export="quality"]').value) / 100;
    let blob = target.blob;
    let canvas;
    try {
      if (blob.type !== type) {
        const bitmap = await createImageBitmap(blob);
        canvas = document.createElement('canvas');
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        const ctx = canvas.getContext('2d');
        if (type === 'image/jpeg') { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); }
        ctx.drawImage(bitmap, 0, 0);
        bitmap.close();
        blob = await canvasBlob(canvas, type, quality);
        if (blob.type !== type) throw new Error(`Trình duyệt không hỗ trợ xuất ${type.split('/')[1].toUpperCase()}.`);
      }
      const ext = EXT_BY_TYPE[blob.type] || 'png';
      const base = (this.project?.name || 'anh').replace(/\.[^.]+$/, '');
      const tag = target.stepId === 'orig' ? 'goc' : (this.project?.steps.find((s) => s.id === target.stepId)?.tool || 'ketqua');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${base}-${tag}-${stamp(Date.now())}.${ext}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
      this.setStatus(`Đã tải ${link.download} (${fmtBytes(blob.size)}).`);
    } catch (error) {
      this.setStatus(`Không thể tải ảnh: ${error.message}`, true);
    } finally {
      freeCanvas(canvas);
    }
  }

  destroy() {
    this.destroyed = true;
    this.session += 1;
    this.controller?.abort();
    this.resizeObserver?.disconnect();
    document.removeEventListener('paste', this.onPaste);
    document.removeEventListener('keydown', this.onKey);
    if (this.previewFrame !== null) window.cancelAnimationFrame(this.previewFrame);
    this.previewBitmap?.close?.();
    for (const side of ['left', 'right']) if (this[side]?.url) URL.revokeObjectURL(this[side].url);
    [...this.listUrls, ...this.filmUrls].forEach((u) => URL.revokeObjectURL(u));
    window.clearTimeout(this.overlayTimer);
    this.consentResolver?.(false);
    if (this.dialog.open) this.dialog.close();
    this.container.innerHTML = '';
  }
}

export function mountImageWorkspace(containerEl) {
  mountedStudios.get(containerEl)?.destroy();
  mountedStudios.set(containerEl, new ImageStudio(containerEl));
}

export function unmountImageWorkspace(containerEl) {
  mountedStudios.get(containerEl)?.destroy();
  mountedStudios.delete(containerEl);
}
