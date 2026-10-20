/**
 * SpaceT — God's Eye View (quả địa cầu 3D thời gian thực) nhúng vào Hub tại /SpaceT.
 *
 * Ứng dụng đầy đủ chạy riêng ở https://spacet.sonxit.io.vn (cùng tên miền gốc với Hub nên
 * dùng chung cache trình duyệt); module này chỉ nhúng nó vào khung làm việc, tràn viền,
 * và tắt các hiệu ứng động của Hub khi đang ở trang này để nhường GPU cho quả cầu.
 */

const SPACET_ORIGIN = 'https://spacet.sonxit.io.vn';
const ROUTE_CLASS = 'route-spacet';
const STYLE_ID = 'spacet-route-style';
const SLOW_LOAD_MS = 30000;

// Hub chrome only: the app inside the iframe is a separate document and is untouched.
const ROUTE_CSS = `
.${ROUTE_CLASS} .workspace-container { padding: 72px 0 0; overflow: hidden; display: flex; }
.${ROUTE_CLASS} .workspace-content { max-width: none; width: 100%; margin: 0; gap: 0; flex: 1; min-height: 0; }
.${ROUTE_CLASS} .app-topnav { backdrop-filter: none; -webkit-backdrop-filter: none; }
.${ROUTE_CLASS} *, .${ROUTE_CLASS} *::before, .${ROUTE_CLASS} *::after { animation: none !important; }
`;

export const spacetModule = {
  id: 'spacet',
  name: 'SpaceT',
  route: '/SpaceT',
  icon: '🌐',
  category: 'Geospatial',
  description: "Quả địa cầu 3D thời gian thực: máy bay, vệ tinh, động đất, thời tiết (God's Eye View).",
  status: 'active',

  _cleanup: null,

  render(el) {
    this.unmount();

    if (!document.getElementById(STYLE_ID)) {
      const style = document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = ROUTE_CSS;
      document.head.appendChild(style);
    }
    document.body.classList.add(ROUTE_CLASS);

    el.innerHTML = `
      <div style="position:relative;flex:1;min-height:0;background:#05070d;">
        <iframe id="st-frame" src="${SPACET_ORIGIN}/" title="SpaceT — God's Eye View"
          allow="fullscreen; geolocation; clipboard-write" referrerpolicy="strict-origin-when-cross-origin"
          style="position:absolute;inset:0;width:100%;height:100%;border:0;"></iframe>
        <div id="st-status" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:1rem;color:#cbd5e1;background:#05070d;pointer-events:none;transition:opacity .25s;">
          Đang tải quả địa cầu…
        </div>
      </div>`;

    const frame = el.querySelector('#st-frame');
    const status = el.querySelector('#st-status');

    const onLoad = () => {
      clearTimeout(slowTimer);
      status.style.opacity = '0';
      setTimeout(() => { status.style.display = 'none'; }, 300);
    };
    const slowTimer = setTimeout(() => {
      status.innerHTML = `Đang tải lâu hơn bình thường…<br><a href="${SPACET_ORIGIN}/" target="_blank" rel="noopener" style="pointer-events:auto;color:#7dd3fc;">Mở trực tiếp ${SPACET_ORIGIN.replace('https://', '')}</a>`;
    }, SLOW_LOAD_MS);
    frame.addEventListener('load', onLoad, { once: true });

    this._cleanup = () => {
      clearTimeout(slowTimer);
      document.body.classList.remove(ROUTE_CLASS);
    };
  },

  unmount() {
    if (this._cleanup) {
      this._cleanup();
      this._cleanup = null;
    }
  },
};
