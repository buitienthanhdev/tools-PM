/* Theo dõi lượt xem trang, thời gian ở lại, người đang online và lỗi JavaScript — gửi về /api/track/* (cùng máy chủ).
   Mã khách (vid) là số ngẫu nhiên lưu trong trình duyệt; không gửi nội dung trang hay dữ liệu nhập. */

const SEND = (kind, data) => {
  try {
    const body = JSON.stringify({ vid, sid, ...data });
    if (navigator.sendBeacon && navigator.sendBeacon(`/api/track/${kind}`, body)) return;
    fetch(`/api/track/${kind}`, { method: 'POST', body, keepalive: true, credentials: 'same-origin' }).catch(() => {});
  } catch { /* không bao giờ ảnh hưởng trang */ }
};

const rid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`);
let vid;
try { vid = localStorage.getItem('pm_vid') || rid(); localStorage.setItem('pm_vid', vid); } catch { vid = rid(); }
let sid;
try { sid = sessionStorage.getItem('pm_sid') || rid(); sessionStorage.setItem('pm_sid', sid); } catch { sid = rid(); }

let current = null; // { path, since, visibleMs, lastShown }
const visibleNow = () => document.visibilityState === 'visible';

function flush() {
  if (!current) return;
  const ms = current.visibleMs + (current.lastShown ? Date.now() - current.lastShown : 0);
  SEND('leave', { path: current.path, dur: Math.round(ms / 100) / 10 });
}

export const tracker = {
  page(path) {
    if (current && current.path === path) return;
    flush();
    current = { path, visibleMs: 0, lastShown: visibleNow() ? Date.now() : 0 };
    SEND('pv', { path, title: document.title, ref: document.referrer || '', screen: `${screen.width}x${screen.height}` });
  },
};

document.addEventListener('visibilitychange', () => {
  if (!current) return;
  if (visibleNow()) current.lastShown = Date.now();
  else {
    if (current.lastShown) current.visibleMs += Date.now() - current.lastShown;
    current.lastShown = 0;
    flush(); // trình duyệt di động có thể đóng tab mà không có pagehide
    current.visibleMs = 0;
  }
});
window.addEventListener('pagehide', flush);

// Đang online: nhịp 60 giây khi tab đang hiển thị
setInterval(() => { if (visibleNow() && current) SEND('ping', { path: current.path }); }, 60000);

// Lỗi JavaScript (giới hạn 20 lỗi mỗi lần tải trang để tránh bão lỗi)
let errCount = 0;
const reportError = (kind, msg, src, stack) => {
  if (++errCount > 20) return;
  SEND('err', { kind, msg: String(msg || '').slice(0, 500), src: String(src || '').slice(0, 300), stack: String(stack || '').slice(0, 3000), path: location.pathname });
};
window.addEventListener('error', (e) => {
  if (e.target && e.target !== window && (e.target.src || e.target.href)) {
    reportError('ResourceError', `Không tải được ${e.target.tagName?.toLowerCase()}`, e.target.src || e.target.href);
  } else reportError(e.error?.name || 'Error', e.message, `${e.filename}:${e.lineno}:${e.colno}`, e.error?.stack);
}, true);
window.addEventListener('unhandledrejection', (e) => {
  const r = e.reason;
  reportError(r?.name || 'UnhandledRejection', r?.message || String(r), '', r?.stack);
});
