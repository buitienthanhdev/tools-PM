/* Lưới an toàn khi server đang khởi động lại: giữ bản giao diện gần nhất để trang vẫn mở được
   thay vì trang lỗi 502 của Cloudflare. Không bao giờ cache API, file tải lên hay tác vụ. */
const CACHE = 'pm-shell-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

const isOk = (res) => res && res.ok && res.type === 'basic';

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin || /^\/(api|uploads)\//.test(url.pathname)) return;

  if (req.mode === 'navigate') {
    // Luôn ưu tiên mạng (bản mới nhất); chỉ dùng bản lưu khi server không trả lời được
    e.respondWith(fetch(req).then((res) => {
      if (isOk(res)) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put('/', copy)); return res; }
      if (res.status >= 500) return caches.match('/').then((hit) => hit || res);
      return res;
    }, () => caches.match('/').then((hit) => hit || Response.error())));
    return;
  }

  // JS/CSS có phiên bản (/v/<mã>/…) không bao giờ đổi nội dung → lưu lại, dùng khi mạng lỗi
  if (url.pathname.startsWith('/v/')) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (isOk(res)) {
        const copy = res.clone();
        const ver = url.pathname.split('/')[2];
        caches.open(CACHE).then(async (c) => {
          await c.put(req, copy);
          // Bỏ file của các phiên bản cũ để bộ nhớ không phình theo mỗi lần deploy
          for (const old of await c.keys()) {
            const p = new URL(old.url).pathname;
            if (p.startsWith('/v/') && p.split('/')[2] !== ver) c.delete(old);
          }
        });
      }
      return res;
    })));
  }
});
