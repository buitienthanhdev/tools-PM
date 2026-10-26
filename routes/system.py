"""Tình trạng hệ thống, file tải lên, giao diện SPA, xử lý lỗi chung."""

import gzip
import mimetypes
import os
import re
import threading
import time
import traceback
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory

from core import analytics, assets, gpu
from core import config as hubcfg
from core.jobs import UPLOAD_DIR
from routes import image, speech

bp = Blueprint("system", __name__)
STATIC_DIR = os.path.join(hubcfg.BASE_DIR, "static")
SERVER_START_TIME = time.time()


# ── API: Tình trạng từng công cụ + GPU ───────────────────────
def _tools_health():
    from core import llm

    out = {}
    out["whisper"] = {
        "ok": True,
        "detail": f"đã nạp: {', '.join(speech._wmodel) or 'chưa nạp model nào'}",
    }
    vox_dir = Path(__file__).resolve().parent.parent / "voxcpm"
    out["voxcpm"] = {
        "ok": vox_dir.is_dir(),
        "detail": "mã nguồn có sẵn" if vox_dir.is_dir() else "thiếu mã nguồn VoxCPM",
    }
    exe, _ = image._esrgan_exe()
    out["image"] = {
        "ok": bool(exe),
        "detail": "Real-ESRGAN sẵn sàng" if exe else "thiếu realesrgan-ncnn-vulkan.exe",
    }
    for tool in ("genreport", "legal", "reviewingcv"):
        key = "cv" if tool == "reviewingcv" else tool
        st = llm.status(hubcfg.model(key))
        out[tool] = {
            "ok": st["ok"],
            "detail": st.get("error") or f"AI local: {st['model']}",
        }
    try:
        import urllib.request

        urllib.request.urlopen("http://127.0.0.1:4174/", timeout=3)
        out["spacet"] = {"ok": True, "detail": "cổng SpaceT đang chạy"}
    except Exception as e:
        out["spacet"] = {
            "ok": False,
            "detail": f"cổng SpaceT không phản hồi ({type(e).__name__})",
        }
    if current_app.config.get("FEATURES", {}).get("accounting"):
        from modules.accounting import health as accounting_health

        out["accounting"] = accounting_health.status()
    if current_app.config.get("FEATURES", {}).get("video"):
        from modules.video_workspace import models as video_models

        caps = video_models.capabilities() or {}
        probs = video_models.env_problems() + ([caps["error"]] if caps.get("error") else [])
        out["video"] = {"ok": bool(caps.get("ok")) and not probs,
                        "detail": "; ".join(probs) if probs else (f"RVE PyTorch {caps.get('torch')} · {', '.join(caps.get('gpus') or [])}"
                                                                  if caps else "đang kiểm tra GPU…")}
    return out


@bp.route("/api/health/tools")
def api_health_tools():
    return jsonify({"tools": _tools_health(), "gpu": gpu.status()})


@bp.route("/api/gpu/status")
def api_gpu_status():
    return jsonify(gpu.status())


def _gzip_json(response):
    """Nén JSON lớn (bảng kế toán, dashboard admin); bỏ qua stream/SSE và file gửi trực tiếp."""
    if (response.status_code != 200 or response.direct_passthrough or response.is_streamed
            or response.mimetype != "application/json" or "Content-Encoding" in response.headers
            or "gzip" not in request.headers.get("Accept-Encoding", "")):
        return
    data = response.get_data()
    if len(data) < 2048:
        return
    response.set_data(gzip.compress(data, 5))
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Vary"] = "Accept-Encoding"


# ── Cache-Control for all responses ──────────────────────────
@bp.after_app_request
def no_cache(response):
    if getattr(response, "_static_cached", False):
        return response
    _gzip_json(response)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ── API: Health ───────────────────────────────────────────────
@bp.route("/api/health")
def api_health():
    try:
        import torch

        import whisper as wh

        uptime = time.time() - SERVER_START_TIME
        image_ai_runtime_available, _ = image._onnx_runtime_available()
        return jsonify(
            {
                "status": "ok",
                "domain": "https://sonxit.io.vn",
                "uptime_seconds": round(uptime, 2),
                "image_ai_runtime_available": image_ai_runtime_available,
                "cuda": torch.cuda.is_available(),
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "whisper": getattr(wh, "__version__", "loaded"),
                "modules": [
                    "whisper",
                    "voxcpm",
                    "image",
                    "genreport",
                    "legal",
                    "spacet",
                    "reviewingcv",
                ]
                + (["accounting"] if current_app.config.get("FEATURES", {}).get("accounting") else [])
                + (["video"] if current_app.config.get("FEATURES", {}).get("video") else []),
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Serve Uploads ─────────────────────────────────────────────
@bp.route("/uploads/<path:filename>")
def serve_uploads(filename):
    image_access = image.authorize_image_upload(filename)
    if image_access is not None:
        return image_access
    as_attachment = request.args.get("download", "0") == "1"
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=as_attachment)


# ── Static files: gzip + revalidation cache ──────────────────
# Mã nguồn (html/js/css) luôn hỏi lại máy chủ (ETag → 304, gần như 0 byte) nên
# deploy xong là có hiệu lực ngay; ảnh/font ít đổi được giữ 1 ngày.
_TEXT_EXT = {".html", ".js", ".mjs", ".css", ".json", ".svg", ".txt", ".map"}
_LONG_EXT = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".avif", ".woff", ".woff2", ".ttf"}
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("font/woff2", ".woff2")
_static_cache = {}  # path -> (mtime_ns, size, etag, raw, gz)
_static_lock = threading.Lock()


def _static_entry(full):
    st = full.stat()
    key = str(full)
    hit = _static_cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit
    raw = full.read_bytes()
    gz = gzip.compress(raw, 6) if full.suffix.lower() in _TEXT_EXT and len(raw) > 1024 else None
    entry = (st.st_mtime_ns, st.st_size, f'"{st.st_mtime_ns:x}-{st.st_size:x}"', raw, gz)
    with _static_lock:
        _static_cache[key] = entry
    return entry


def _serve_static(rel):
    full = Path(STATIC_DIR) / rel
    _, _, etag, raw, gz = _static_entry(full)
    ext = full.suffix.lower()
    if ext in _TEXT_EXT or ext not in _LONG_EXT:
        cache = "no-cache"
    else:
        cache = "public, max-age=86400"
    if etag in request.headers.get("If-None-Match", ""):
        resp = Response(status=304)
    else:
        mime = mimetypes.guess_type(full.name)[0] or "application/octet-stream"
        if ext in (".js", ".mjs"):
            mime = "text/javascript"
        if mime.startswith("text/") or ext in (".js", ".mjs", ".json", ".svg"):
            mime += "; charset=utf-8"
        use_gz = gz is not None and "gzip" in request.headers.get("Accept-Encoding", "")
        resp = Response(gz if use_gz else raw, content_type=mime)
        if use_gz:
            resp.headers["Content-Encoding"] = "gzip"
    if gz is not None:
        resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = cache
    resp._static_cached = True
    return resp


# ── Đường dẫn có phiên bản: /v/<mã>/js/main.js ────────────────
# index.html trỏ JS/CSS lõi vào /v/<mã>/…; import tương đối trong JS tự kế thừa tiền tố
# nên mọi module được cache vĩnh viễn (0 request khi vào lại). Sửa bất kỳ file JS/CSS
# nào → mã đổi → trình duyệt tải bản mới, không cần khởi động lại server.
# Có static/dist/ (scripts/build_frontend.py) với STAMP khớp mã nguồn → phục vụ bản gộp.
_VERSIONED = re.compile(r"""(["'])/((?:dist|js|styles|stores|services|layouts|components|modules|fonts)/[^"'?]+\.(?:js|css))\1""")
_ver = {"at": 0.0, "sig": None, "value": "", "dist": False}


def _asset_version():
    now = time.monotonic()
    if now - _ver["at"] > 2:
        sig = assets.signature(STATIC_DIR)
        if sig != _ver["sig"]:
            ver = assets.source_hash(STATIC_DIR)
            try:
                stamp = (Path(STATIC_DIR) / assets.DIST / "STAMP").read_text("ascii").strip()
            except OSError:
                stamp = ""
            if stamp and stamp != ver:
                print(f"[static] dist/ cũ (STAMP {stamp} ≠ {ver}) → dùng mã nguồn chưa gộp; chạy scripts/build_frontend.py")
            _ver.update(sig=sig, value=ver, dist=stamp == ver)
        _ver["at"] = now
    return _ver["value"]


_index_cache = {}


def _serve_index():
    ver = _asset_version()
    index = Path(STATIC_DIR) / (f"{assets.DIST}/index.html" if _ver["dist"] else "index.html")
    _, _, etag, raw, _ = _static_entry(index)
    key = (ver, etag)
    if key not in _index_cache:
        html = _VERSIONED.sub(lambda m: f"{m[1]}/v/{ver}/{m[2]}{m[1]}", raw.decode("utf-8")).encode("utf-8")
        _index_cache.clear()
        _index_cache[key] = (html, gzip.compress(html, 6), f'"{ver}-{etag.strip(chr(34))}"')
    html, gz, tag = _index_cache[key]
    if tag in request.headers.get("If-None-Match", ""):
        resp = Response(status=304)
    else:
        use_gz = "gzip" in request.headers.get("Accept-Encoding", "")
        resp = Response(gz if use_gz else html, content_type="text/html; charset=utf-8")
        if use_gz:
            resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["ETag"] = tag
    resp.headers["Cache-Control"] = "no-cache"
    resp._static_cached = True
    return resp


# ── SPA Fallback & Route Handling ─────────────────────────────
@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def serve_spa(path):
    immutable = False
    m = re.match(r"v/([0-9a-f]{10})/(.+)", path)
    if m:
        path = m[2]
        # Trang cũ xin phiên bản cũ → vẫn trả file hiện tại nhưng không cho cache lâu
        immutable = m[1] == _asset_version()
    if path and path != "index.html":
        full = (Path(STATIC_DIR) / path).resolve()
        if full.is_file() and full.is_relative_to(Path(STATIC_DIR).resolve()):
            resp = _serve_static(path)
            if immutable:
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
    return _serve_index()


@bp.app_errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": f"API route not found: {request.path}"}), 404
    return _serve_index()


@bp.app_errorhandler(Exception)
def handle_500(e):
    traceback.print_exc()
    analytics.server_error(e)
    if request.path.startswith("/api/"):
        return jsonify({"error": "Lỗi máy chủ, vui lòng thử lại"}), 500
    return send_from_directory(STATIC_DIR, "index.html")
