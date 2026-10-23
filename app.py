"""
PM Tools Hub — Unified Flask Backend
Single server serving Dashboard + Whisper STT + VoxCPM TTS + GenReport APIs
"""

import os
import sys

# Log ra file dùng cp1252 trên Windows → tiếng Việt/emoji trong print làm sập server
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from flask import Flask, jsonify, request
from flask_cors import CORS

from core import auth

# ── Path Setup ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import torchaudio

try:
    if "soundfile" in torchaudio.list_audio_backends():
        torchaudio.set_audio_backend("soundfile")
except Exception:
    pass

# ── FFmpeg ───────────────────────────────────────────────────
try:
    import shutil

    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    target_ff = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(target_ff):
        shutil.copyfile(ffmpeg_exe, target_ff)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    print(f"[FFmpeg] OK: {target_ff}")
except Exception as e:
    print(f"[FFmpeg] Warning: {e}")

# ── Flask App ─────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024
_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "PM_ALLOWED_ORIGINS",
        "https://sonxit.io.vn,http://localhost:5000,http://127.0.0.1:5000",
    ).split(",")
    if o.strip()
]
CORS(app, origins=_ORIGINS, supports_credentials=True)
auth.init_app(app)


@app.before_request
def _csrf_origin_check():
    """Chặn CSRF: request ghi dữ liệu có header Origin thì phải thuộc danh sách cho phép."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin")
        if origin and origin not in _ORIGINS:
            return jsonify({"error": "Origin không hợp lệ", "code": "bad_origin"}), 403


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


from core.jobs import start_cleanup  # noqa: E402
from modules.legal_rag.api import bp as legal_bp  # noqa: E402
from modules.reviewingcv.api import bp as cv_bp  # noqa: E402
from routes import genreport, image, jobs, speech, system  # noqa: E402

for _bp in (
    legal_bp,
    cv_bp,
    speech.bp,
    genreport.bp,
    image.bp,
    jobs.bp,
    system.bp,
):
    app.register_blueprint(_bp)

# Accounting AI (/accounting): chỉ gắn khi được bật (data/config.json "accounting.enabled" hoặc PM_ACCOUNTING=1)
from modules.accounting import settings as accounting_settings  # noqa: E402

app.config["FEATURES"] = {"accounting": bool(accounting_settings.get()["enabled"])}
if app.config["FEATURES"]["accounting"]:
    from modules.accounting.api import init_app as accounting_init  # noqa: E402

    accounting_init(app)

start_cleanup()

if __name__ == "__main__":
    print("=" * 60)
    print("  PM Tools Hub — Dev Server")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.environ.get("PM_DEBUG") == "1",
        threaded=True,
    )
