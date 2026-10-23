"""
Theo dõi hoạt động toàn Hub cho trang quản trị: request API, lượt xem trang, người đang online, sự kiện
tài khoản, lỗi máy chủ và lỗi trình duyệt.

- Ghi vào SQLite riêng <DATA_DIR>/analytics/analytics.db qua hàng đợi + luồng nền (gom lô) → không làm chậm request.
- KHÔNG ghi nội dung request/response, mật khẩu, nội dung file; chuỗi truy vấn chỉ giữ tên tham số.
- Đường dẫn được chuẩn hoá (UUID/số → :id) để gom nhóm; IP lấy từ CF-Connecting-IP (Cloudflare Tunnel).
- Bỏ qua file tĩnh và các GET thăm dò định kỳ thành công (trạng thái task/job/health) — chỉ là nhiễu.
- Giữ dữ liệu `analytics.retention_days` ngày (mặc định 90), dọn mỗi ngày.
"""

import json
import os
import queue
import re
import sqlite3
import threading
import time
import traceback
from collections import deque

from flask import g, request

from . import config

DB_PATH = os.path.join(config.DATA_DIR, "analytics", "analytics.db")
ONLINE_WINDOW = 300  # giây: còn hoạt động trong 5 phút = đang online

_q = queue.Queue(maxsize=50000)
_conn = None
_conn_lock = threading.Lock()
_started = False
_live = {}  # visitor/user key → {user, path, ts, ip, country, device, browser}
_live_lock = threading.Lock()
_rate = {}  # ip → deque[timestamps] cho beacon công khai
dropped = 0

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, method TEXT, path TEXT, route TEXT, query_keys TEXT, module TEXT,
  status INTEGER, ms REAL, bytes INTEGER, user TEXT, ip TEXT, country TEXT, browser TEXT, os TEXT, device TEXT,
  ref TEXT, error TEXT);
CREATE INDEX IF NOT EXISTS ix_req_ts ON requests(ts);
CREATE INDEX IF NOT EXISTS ix_req_user ON requests(user, ts);
CREATE INDEX IF NOT EXISTS ix_req_ip ON requests(ip, ts);
CREATE TABLE IF NOT EXISTS pageviews (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, vid TEXT, sid TEXT, user TEXT, path TEXT, title TEXT, ref TEXT,
  screen TEXT, ip TEXT, country TEXT, browser TEXT, os TEXT, device TEXT, dur REAL);
CREATE INDEX IF NOT EXISTS ix_pv_ts ON pageviews(ts);
CREATE INDEX IF NOT EXISTS ix_pv_vid ON pageviews(vid, ts);
CREATE INDEX IF NOT EXISTS ix_pv_user ON pageviews(user, ts);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL, user TEXT, actor TEXT, ip TEXT, country TEXT,
  detail TEXT);
CREATE INDEX IF NOT EXISTS ix_ev_ts ON events(ts);
CREATE INDEX IF NOT EXISTS ix_ev_kind ON events(kind, ts);
CREATE INDEX IF NOT EXISTS ix_ev_user ON events(user, ts);
CREATE TABLE IF NOT EXISTS errors (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, source TEXT NOT NULL, kind TEXT, message TEXT, where_ TEXT,
  stack TEXT, path TEXT, user TEXT, ip TEXT, browser TEXT);
CREATE INDEX IF NOT EXISTS ix_err_ts ON errors(ts);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

STATIC_EXT = re.compile(r"\.(js|mjs|css|map|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|mp4|webm|json|txt)$", re.I)
# GET thăm dò định kỳ: chỉ ghi khi lỗi
POLL = re.compile(r"^/api/(health|gpu/status|jobs?/[^/]+$|job/|accounting/o/[^/]+/(tasks/[^/]+$|review-count|overview)|"
                  r"admin/analytics/live|track/)")
# Đường dẫn máy quét lỗ hổng hay thử (SPA trả 200 cho mọi đường dẫn lạ nên phải nhận diện theo mẫu)
SCAN = re.compile(r"\.(php\d?|aspx?|jsp|cgi|env|git|svn|bak|sql|ini|log|yml|yaml|config)(/|$)|/wp-|/wordpress|phpmyadmin|/\.|"
                  r"/(cgi-bin|vendor|actuator|console|server-status|xmlrpc|boaform|HNAP1|owa|autodiscover)", re.I)
ID_SEG = re.compile(r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{16,}|\d+|"
                    r"[A-Za-z0-9_-]{22,})(\.\w+)?$")
MODULE_PREFIX = [
    ("/api/transcribe", "whisper"), ("/api/voxcpm", "voxcpm"), ("/api/image", "image"), ("/api/genreport", "genreport"),
    ("/api/legal", "legal"), ("/api/cv", "reviewingcv"), ("/api/accounting", "accounting"), ("/api/auth", "auth"),
    ("/api/admin", "admin"), ("/api/job", "jobs"), ("/api/export", "export"), ("/uploads", "uploads"),
]
PAGE_MODULE = {"/whisper": "whisper", "/voxcpm": "voxcpm", "/image": "image", "/genreport": "genreport", "/legal": "legal",
               "/spacet": "spacet", "/reviewingcv": "reviewingcv", "/accounting": "accounting", "/admin": "admin",
               "/login": "auth", "/": "catalog"}


# ── Lưu trữ ──────────────────────────────────────────────────
def _db():
    global _conn
    with _conn_lock:
        if _conn is None:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.executescript(SCHEMA)
            _conn = c
        return _conn


def query(sql, args=()):
    """Đọc cho trang quản trị (luồng request) — kết nối đọc riêng, không chặn luồng ghi."""
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, args)]
    finally:
        c.close()


def _writer():
    last_prune = 0.0
    while True:
        batch = [_q.get()]
        t_end = time.time() + 1.0
        while len(batch) < 500:
            try:
                batch.append(_q.get(timeout=max(0.0, t_end - time.time())))
            except queue.Empty:
                break
        try:
            c = _db()
            with _conn_lock:
                for table, row in batch:
                    if table == "__dur":
                        c.execute("UPDATE pageviews SET dur=? WHERE vid=? AND id=(SELECT max(id) FROM pageviews WHERE vid=? AND path=?)",
                                  (row["dur"], row["vid"], row["vid"], row["path"]))
                        continue
                    cols = ",".join(row)
                    c.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
                c.commit()
            if time.time() - last_prune > 86400:
                last_prune = time.time()
                _prune()
        except Exception as e:  # không bao giờ làm sập luồng ghi
            print(f"[analytics] ghi lỗi: {type(e).__name__}: {e}")
        finally:
            for _ in batch:
                _q.task_done()


def _prune():
    days = float((config.get().get("analytics") or {}).get("retention_days", 90))
    cut = time.time() - days * 86400
    c = _db()
    with _conn_lock:
        for t in ("requests", "pageviews", "events", "errors"):
            c.execute(f"DELETE FROM {t} WHERE ts < ?", (cut,))
        c.commit()


def _put(table, row):
    global dropped
    try:
        _q.put_nowait((table, row))
    except queue.Full:
        dropped += 1


def reset_for_tests(path):
    """Kiểm thử: chuyển sang file DB khác, xoá trạng thái trong bộ nhớ."""
    global _conn, DB_PATH
    flush()
    with _conn_lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        DB_PATH = path
    with _live_lock:
        _live.clear()
    _rate.clear()


def flush():
    """Chờ ghi hết hàng đợi (dùng cho kiểm thử / trước khi tắt)."""
    if _started:
        _q.join()


def start():
    global _started
    if _started or (config.get().get("analytics") or {}).get("enabled") is False:
        return
    _started = True
    _db()
    threading.Thread(target=_writer, name="analytics-writer", daemon=True).start()


# ── Nhận diện client ─────────────────────────────────────────
def client_ip():
    return (request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "?")


def parse_ua(ua):
    ua = ua or ""
    low = ua.lower()
    if re.search(r"bot|crawl|spider|slurp|curl|wget|python-requests|httpx|go-http|scanner|headless", low):
        device = "bot"
    elif re.search(r"ipad|tablet", low):
        device = "tablet"
    elif re.search(r"mobi|android|iphone", low):
        device = "mobile"
    else:
        device = "desktop"
    for name, pat in (("Edge", r"edg/"), ("Opera", r"opr/|opera"), ("Cốc Cốc", r"coc_coc|coccoc"), ("Samsung", r"samsungbrowser"),
                      ("Zalo", r"zalo"), ("Facebook", r"fban|fbav"), ("Chrome", r"chrome/|crios"), ("Firefox", r"firefox|fxios"),
                      ("Safari", r"safari")):
        if re.search(pat, low):
            browser = name
            break
    else:
        browser = "Khác" if device != "bot" else (re.split(r"[/ ;]", ua)[0][:30] or "bot")
    for name, pat in (("Windows", r"windows"), ("Android", r"android"), ("iOS", r"iphone|ipad|ios"), ("macOS", r"mac os"),
                      ("Linux", r"linux")):
        if re.search(pat, low):
            os_ = name
            break
    else:
        os_ = "Khác"
    return browser, os_, device


def norm_path(path):
    parts = [":id" if ID_SEG.match(p) else p for p in path.split("/")]
    return "/".join(parts)[:200]


def module_of(path):
    for prefix, m in MODULE_PREFIX:
        if path.startswith(prefix):
            return m
    if not path.startswith("/api/"):
        return PAGE_MODULE.get("/" + path.strip("/").split("/")[0] if path.strip("/") else "/", "page")
    return "other"


def _user_email():
    try:
        from flask import session

        return session.get("email")
    except Exception:
        return None


def _touch_live(key, **info):
    with _live_lock:
        cur = _live.get(key, {})
        cur.update({k: v for k, v in info.items() if v is not None}, ts=time.time())
        _live[key] = cur
        if len(_live) > 5000:  # dọn khách đã rời
            cut = time.time() - ONLINE_WINDOW
            for k in [k for k, v in _live.items() if v["ts"] < cut]:
                _live.pop(k, None)


def live():
    cut = time.time() - ONLINE_WINDOW
    with _live_lock:
        rows = [{"key": k, **v} for k, v in _live.items() if v["ts"] >= cut]
    # Gộp theo người dùng (một người nhiều tab) — khách vãng lai theo mã trình duyệt
    merged = {}
    for r in sorted(rows, key=lambda r: r["ts"]):
        k = r.get("user") or r["key"]
        merged[k] = {**merged.get(k, {}), **r}
    return sorted(merged.values(), key=lambda r: -r["ts"])


# ── Hook Flask ───────────────────────────────────────────────
def init_app(app):
    start()

    @app.before_request
    def _an_start():
        g._an_t0 = time.perf_counter()

    @app.after_request
    def _an_log(resp):
        try:
            _log_request(resp)
        except Exception as e:
            print(f"[analytics] {type(e).__name__}: {e}")
        return resp


def _log_request(resp):
    if not _started:
        return
    p = request.path
    if request.method == "OPTIONS" or STATIC_EXT.search(p) or p.startswith(("/assets/", "/static/", "/styles/", "/modules/",
                                                                            "/components/", "/js/", "/stores/", "/services/")):
        return
    status = resp.status_code
    is_api = p.startswith(("/api/", "/uploads/"))
    if p.startswith("/api/track/") or (request.method == "GET" and status < 400 and p.startswith("/api/admin/analytics/")):
        return  # beacon đã ghi ở bảng riêng; admin xem dashboard không phải hoạt động cần theo dõi
    scan = not is_api and bool(SCAN.search(p))
    if request.method == "GET" and status < 400 and POLL.match(p):
        user = _user_email()
        if user:
            _touch_live(f"u:{user}", user=user)
        return
    if not is_api and not scan and request.method == "GET" and status < 400:
        return  # tải trang SPA được ghi bằng beacon lượt xem (có đường dẫn thật, thời gian ở lại)
    ms = (time.perf_counter() - g.get("_an_t0", time.perf_counter())) * 1000
    browser, os_, device = parse_ua(request.headers.get("User-Agent"))
    user = _user_email()
    ip = client_ip()
    ref = request.headers.get("Referer") or ""
    ref_host = re.sub(r"^https?://([^/]+).*$", r"\1", ref) if ref else None
    _put("requests", {
        "ts": time.time(), "method": request.method, "path": p[:300], "route": norm_path(p),
        "query_keys": ",".join(sorted(request.args.keys()))[:200] or None, "module": "scan" if scan else module_of(p), "status": status,
        "ms": round(ms, 1), "bytes": resp.calculate_content_length() if not resp.direct_passthrough else None,
        "user": user, "ip": ip, "country": request.headers.get("CF-IPCountry"), "browser": browser, "os": os_,
        "device": device, "ref": ref_host, "error": g.get("_an_error"),
    })
    if user:
        _touch_live(f"u:{user}", user=user, ip=ip, browser=browser, device=device,
                    country=request.headers.get("CF-IPCountry"), last_api=norm_path(p))


def server_error(exc):
    """Gọi từ errorhandler 500: lưu loại lỗi, thông điệp, traceback (cắt ngắn)."""
    if not _started:
        return
    try:
        g._an_error = type(exc).__name__
    except Exception:
        pass
    tb = traceback.format_exc()
    frames = [ln.strip() for ln in tb.splitlines() if ln.strip().startswith("File ")]
    _put("errors", {"ts": time.time(), "source": "server", "kind": type(exc).__name__, "message": str(exc)[:500],
                    "where_": (frames[-1] if frames else "")[:300], "stack": tb[-4000:], "path": request.path[:300],
                    "user": _user_email(), "ip": client_ip(), "browser": parse_ua(request.headers.get("User-Agent"))[0]})


def event(kind, user=None, actor=None, **detail):
    """Sự kiện nghiệp vụ: login_ok, login_fail, register, logout, password_change, admin_update, admin_delete…"""
    if not _started:
        return
    try:
        ip, country = client_ip(), request.headers.get("CF-IPCountry")
    except RuntimeError:
        ip = country = None
    _put("events", {"ts": time.time(), "kind": kind, "user": user, "actor": actor or _user_email(), "ip": ip,
                    "country": country, "detail": json.dumps(detail, ensure_ascii=False, default=str)[:2000] if detail else None})


# ── Beacon từ trình duyệt (công khai, giới hạn tốc độ) ──────
def rate_ok(limit=120, window=60):
    ip = client_ip()
    now = time.time()
    dq = _rate.setdefault(ip, deque())
    while dq and dq[0] < now - window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    if len(_rate) > 20000:
        _rate.clear()
    return True


def _clean(v, n):
    return re.sub(r"[\x00-\x1f]", " ", str(v))[:n] if v not in (None, "") else None


def beacon(kind, d):
    if not _started:
        return
    browser, os_, device = parse_ua(request.headers.get("User-Agent"))
    ip, country, user = client_ip(), request.headers.get("CF-IPCountry"), _user_email()
    vid = _clean(d.get("vid"), 40) or f"ip:{ip}"
    path = _clean(d.get("path"), 300) or "/"
    if kind == "pv":
        ref = _clean(d.get("ref"), 300)
        ref_host = re.sub(r"^https?://([^/]+).*$", r"\1", ref) if ref else None
        if ref_host and ref_host.endswith(("sonxit.io.vn", "localhost:5000", "127.0.0.1:5000")):
            ref_host = None  # điều hướng nội bộ
        _put("pageviews", {"ts": time.time(), "vid": vid, "sid": _clean(d.get("sid"), 40), "user": user, "path": path,
                           "title": _clean(d.get("title"), 120), "ref": ref_host, "screen": _clean(d.get("screen"), 20),
                           "ip": ip, "country": country, "browser": browser, "os": os_, "device": device, "dur": None})
    elif kind == "leave":
        try:
            dur = max(0.0, min(float(d.get("dur") or 0), 6 * 3600))
        except (TypeError, ValueError):
            dur = 0.0
        _put("__dur", {"vid": vid, "path": path, "dur": round(dur, 1)})
    elif kind == "err":
        _put("errors", {"ts": time.time(), "source": "client", "kind": _clean(d.get("kind"), 60) or "Error",
                        "message": _clean(d.get("msg"), 500), "where_": _clean(d.get("src"), 300),
                        "stack": _clean(d.get("stack"), 3000), "path": path, "user": user, "ip": ip, "browser": browser})
    _touch_live(f"u:{user}" if user else f"v:{vid}", user=user, path=path, ip=ip, country=country, browser=browser,
                device=device, vid=vid)
