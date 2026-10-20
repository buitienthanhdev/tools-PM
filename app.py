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

from flask import Flask
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

# Whisper module path
WHISPER_SRC = os.path.join(BASE_DIR, "modules", "whisper", "whisper-source")
if os.path.isdir(WHISPER_SRC):
    sys.path.insert(0, WHISPER_SRC)

# VoxCPM module paths
VOXCPM_SRC = os.path.join(
    BASE_DIR, "modules", "voxcpm", "VoxCPM-source", "VoxCPM-main", "src"
)
VOXCPM_APP = os.path.join(BASE_DIR, "modules", "voxcpm", "VoxCPM-source", "VoxCPM-main")
if os.path.isdir(VOXCPM_SRC):
    sys.path.insert(0, VOXCPM_SRC)
if os.path.isdir(VOXCPM_APP):
    sys.path.insert(0, VOXCPM_APP)

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
CORS(app)
auth.init_app(app)

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

start_cleanup()

if __name__ == "__main__":
    print("=" * 60)
    print("  PM Tools Hub — Dev Server")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
