/* ============================================================
   PM Tools Hub — Landing page (route "/"), bố cục theo Webfolio.
   Ảnh xem trước module: static/assets/previews/<id>.webp
   (chụp lại bằng script khi giao diện module thay đổi).
   CSS: static/styles/home.css
   ============================================================ */

import { moduleRegistry } from '../../js/moduleRegistry.js';
import { router } from '../../js/router.js';
import { svgIcon } from '../../components/icons.js';
import { authStore } from '../../stores/authStore.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const preview = (id) => `/assets/previews/${id}.webp`;
// Máy yếu (class .lite do index.html đặt): bỏ bộ ảnh trang trí ở hero và phần nổi — không tải luôn
const LITE = document.documentElement.classList.contains('lite');
const num = (i) => String(i + 1).padStart(2, '0');

const BAND = ['Chạy trên GPU riêng', 'Không cần cài đặt', 'Tự giám sát 24/7', 'Hỗ trợ tiếng Việt'];

export const catalogModule = {
  id: 'catalog',
  name: 'Trang chủ Hub',
  route: '/',
  icon: '🏠',
  category: 'Platform',
  description: 'Trung tâm tổng hợp & điều phối các công cụ AI',
  status: 'active',

  _cleanup: null,

  render(containerEl) {
    this.unmount(containerEl);
    document.body.classList.add('route-home');

    const modules = moduleRegistry.getAllModules().filter((m) => m.id !== 'catalog' && !m.hidden);
    const ids = modules.map((m) => m.id);
    const band = [...BAND, ...BAND].map((t) => `<span>${esc(t)}</span>`).join('');

    containerEl.innerHTML = `
    <div class="wfl">
      <nav class="wfl-nav" id="wfl-nav">
        <div class="wfl-container wfl-nav-in">
          <div class="wfl-nav-links">
            <a href="#wfl-tools" data-jump="wfl-tools">Công cụ</a>
            <a href="#wfl-features" data-jump="wfl-features">Tính năng</a>
            <a href="#wfl-devices" data-jump="wfl-devices">Thiết bị</a>
            <a href="/login" id="wfl-login" data-route="/login">${authStore.user ? esc(authStore.user.name || authStore.user.email) : 'Đăng nhập'}</a>
          </div>
          <div class="wfl-nav-cta">
            <button class="wfl-btn" type="button" data-jump="wfl-tools">${svgIcon('arrow', 18, 2)} Bắt đầu ngay</button>
            <a class="gh-ava" href="https://github.com/buitienthanhdev" target="_blank" rel="noopener" title="GitHub · buitienthanhdev"><span class="gh-ring"></span><img src="https://github.com/buitienthanhdev.png?size=96" alt="buitienthanhdev" loading="lazy" decoding="async" width="40" height="40" /></a>
          </div>
        </div>
      </nav>

      <header class="wfl-hero wfl-noise">
        <div class="wfl-iso" aria-hidden="true">
          ${(LITE ? [] : ['voxcpm', 'spacet', 'whisper', 'reviewingcv', 'genreport', 'image']).filter((id) => ids.includes(id)).map((id) => `<img src="${preview(id)}" alt="" loading="eager" />`).join('')}
        </div>
        <div class="wfl-container wfl-hero-c">
          <h1>Bộ công cụ <span class="thin">AI Workspace</span> mạnh mẽ nhất đã sẵn sàng</h1>
          <div class="wfl-hero-word" aria-hidden="true">PM Tools</div>
        </div>
      </header>

      <section class="wfl-demos" id="wfl-tools">
        <div class="wfl-demos-box">
          <h2 class="wfl-demos-title wfl-reveal">Bộ <b>${modules.length}</b> công cụ AI</h2>
          <div class="wfl-grid">
            ${modules.map((m, i) => `
              <button class="wfl-card wfl-reveal" type="button" data-route="${esc(m.route)}" title="${esc(m.description)}">
                <div class="wfl-card-img">
                  <img src="${preview(m.id)}" alt="${esc(m.name)}" loading="lazy" onerror="this.parentNode.style.background='#161616'" />
                  <span class="wfl-card-no">${num(i)}</span>
                  ${authStore.can(m.id) ? '' : `<span class="wfl-lock">${svgIcon('lock', 12, 2)} ${authStore.user ? 'Chưa cấp quyền' : 'Đăng nhập'}</span>`}
                  <span class="wfl-card-go">Mở</span>
                </div>
                <div class="wfl-card-cap"><h3>${esc(m.name)}</h3><small>${esc(m.category)}</small></div>
              </button>`).join('')}
          </div>
        </div>
      </section>

      <section class="wfl-pages" id="wfl-features">
        <div class="wfl-container wfl-reveal">
          <span class="wfl-eyebrow">Tính năng nổi bật</span>
          <h2>Mọi công cụ chạy ngay trong trình duyệt, không cần cài đặt</h2>
        </div>
        <div class="wfl-collage" aria-hidden="true">
          <div class="wfl-collage-in">
            ${[...ids, 'mobile', ...ids].slice(0, 12).map((id) => `<img src="${preview(id)}" alt="" loading="lazy" />`).join('')}
          </div>
        </div>
        <div class="wfl-container wfl-counters">
          <div class="wfl-counter"><b>${modules.length}+</b><small>Công cụ AI</small></div>
          <div class="wfl-counter"><b>24/7</b><small>Tự giám sát</small></div>
        </div>
      </section>

      <section class="wfl-resp" id="wfl-devices">
        <div class="wfl-container wfl-resp-in">
          <div class="wfl-devices wfl-reveal" aria-hidden="true">
            <div class="wfl-tablet"><img src="${preview(ids.includes('reviewingcv') ? 'reviewingcv' : ids[0])}" alt="" loading="lazy" /></div>
            <div class="wfl-phone"><img src="${preview('mobile')}" alt="" loading="lazy" /></div>
          </div>
          <div class="wfl-resp-text wfl-reveal">
            <span class="wfl-eyebrow">Trên mọi thiết bị</span>
            <h2>Dùng mượt <span class="thin">trên mọi</span> thiết bị</h2>
            <p>Giao diện tự nhận kích thước màn hình và co giãn nội dung, dùng tốt trên máy tính, máy tính bảng lẫn điện thoại.</p>
            <button class="wfl-more" type="button" data-jump="wfl-tools">Khám phá ngay <span>${svgIcon('arrow', 16, 2)}</span></button>
          </div>
        </div>
      </section>

      <section class="wfl-band" aria-hidden="true">
        <div class="wfl-band-track">${band}${band}</div>
      </section>

      <section class="wfl-cta wfl-noise">
        ${(LITE ? [] : ['image', 'voxcpm', 'whisper', 'genreport', 'reviewingcv', 'legal']).filter((id) => ids.includes(id)).map((id, i) => `<img class="wfl-float f${i + 1}" src="${preview(id)}" alt="" loading="lazy" />`).join('')}
        <div class="wfl-cta-in wfl-reveal">
          <span class="wfl-tag">Sẵn sàng cho bạn!</span>
          <h2 class="wfl-glass">Bắt đầu làm việc cùng<br>AI ngay hôm nay!</h2>
          <p>Không cần tài khoản, không cần cài đặt<br>Chọn một công cụ và bắt đầu trong vài giây!</p>
          <button class="wfl-btn pill" type="button" data-jump="wfl-tools">Chọn công cụ</button>
        </div>
      </section>

      <button class="wfl-top" id="wfl-top" type="button" title="Lên đầu trang">${svgIcon('down', 18, 2).replace('<svg', '<svg style="transform:rotate(180deg)"')}</button>
    </div>`;

    const scroller = document.getElementById('mainWorkspaceViewport') || containerEl;
    const nav = containerEl.querySelector('#wfl-nav');
    const topBtn = containerEl.querySelector('#wfl-top');

    containerEl.querySelectorAll('[data-route]').forEach((el) => {
      el.addEventListener('click', () => router.navigate(el.getAttribute('data-route')));
    });
    containerEl.querySelectorAll('[data-jump]').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        containerEl.querySelector('#' + el.dataset.jump)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    topBtn.addEventListener('click', () => scroller.scrollTo({ top: 0, behavior: 'smooth' }));

    const onScroll = () => {
      const y = scroller.scrollTop;
      nav.classList.toggle('is-solid', y > 40);
      topBtn.classList.toggle('show', y > 600);
    };
    scroller.addEventListener('scroll', onScroll, { passive: true });
    scroller.scrollTop = 0;
    onScroll();

    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add('in');
          io.unobserve(en.target);
        }
      });
    }, { root: scroller, threshold: 0.12 });
    containerEl.querySelectorAll('.wfl-reveal').forEach((el) => io.observe(el));

    this._cleanup = () => {
      scroller.removeEventListener('scroll', onScroll);
      io.disconnect();
    };
  },

  unmount(containerEl) {
    if (this._cleanup) this._cleanup();
    this._cleanup = null;
    document.body.classList.remove('route-home');
    if (containerEl) containerEl.innerHTML = '';
  },
};
