"""Tình trạng hệ thống, file tải lên, giao diện SPA, xử lý lỗi chung."""

import os
import time
import traceback
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from core import analytics, gpu
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
    return out


@bp.route("/api/health/tools")
def api_health_tools():
    return jsonify({"tools": _tools_health(), "gpu": gpu.status()})


@bp.route("/api/gpu/status")
def api_gpu_status():
    return jsonify(gpu.status())


# ── Cache-Control for all responses ──────────────────────────
@bp.after_app_request
def no_cache(response):
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
                + (["accounting"] if current_app.config.get("FEATURES", {}).get("accounting") else []),
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


# ── SPA Fallback & Route Handling ─────────────────────────────
@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def serve_spa(path):
    if path:
        full = Path(STATIC_DIR) / path
        if full.exists() and full.is_file():
            return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


@bp.app_errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": f"API route not found: {request.path}"}), 404
    return send_from_directory(STATIC_DIR, "index.html")


@bp.app_errorhandler(Exception)
def handle_500(e):
    traceback.print_exc()
    analytics.server_error(e)
    if request.path.startswith("/api/"):
        return jsonify({"error": "Lỗi máy chủ, vui lòng thử lại"}), 500
    return send_from_directory(STATIC_DIR, "index.html")
