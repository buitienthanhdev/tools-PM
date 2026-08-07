"""
Whisper Web UI - Flask Backend
Provides REST API endpoints for speech recognition using OpenAI Whisper
"""

import json
import os
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)
from flask_cors import CORS

# Add whisper directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure FFmpeg is available in PATH for Whisper audio loading
try:
    import shutil

    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    target_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(target_ffmpeg):
        shutil.copyfile(ffmpeg_exe, target_ffmpeg)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    print(f"[FFmpeg] Configured FFmpeg executable: {target_ffmpeg}")
except Exception as e:
    print(f"[FFmpeg Warning] Could not locate/setup FFmpeg via imageio_ffmpeg: {e}")

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Results storage (in-memory)
jobs_store = {}

# Global model cache
_model_cache = {}
_model_lock = threading.Lock()

SUPPORTED_FORMATS = {
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".wav",
    ".webm",
    ".ogg",
    ".flac",
}

MODELS = [
    {
        "id": "tiny",
        "name": "Tiny",
        "params": "39M",
        "vram": "~1 GB",
        "speed": "~10x",
        "description": "Fastest model, good for testing",
    },
    {
        "id": "base",
        "name": "Base",
        "params": "74M",
        "vram": "~1 GB",
        "speed": "~7x",
        "description": "Good balance for quick tasks",
    },
    {
        "id": "small",
        "name": "Small",
        "params": "244M",
        "vram": "~2 GB",
        "speed": "~4x",
        "description": "Better accuracy, reasonable speed",
    },
    {
        "id": "medium",
        "name": "Medium",
        "params": "769M",
        "vram": "~5 GB",
        "speed": "~2x",
        "description": "High accuracy, supports translation",
    },
    {
        "id": "large",
        "name": "Large",
        "params": "1550M",
        "vram": "~10 GB",
        "speed": "1x",
        "description": "Highest accuracy",
    },
    {
        "id": "turbo",
        "name": "Turbo",
        "params": "809M",
        "vram": "~6 GB",
        "speed": "~8x",
        "description": "Fast & accurate (recommended)",
    },
]

LANGUAGES = {
    "auto": "Auto Detect",
    "en": "English",
    "zh": "Chinese",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "ko": "Korean",
    "fr": "French",
    "ja": "Japanese",
    "pt": "Portuguese",
    "tr": "Turkish",
    "pl": "Polish",
    "nl": "Dutch",
    "ar": "Arabic",
    "sv": "Swedish",
    "it": "Italian",
    "id": "Indonesian",
    "hi": "Hindi",
    "fi": "Finnish",
    "vi": "Vietnamese",
    "he": "Hebrew",
    "uk": "Ukrainian",
    "el": "Greek",
    "ms": "Malay",
    "cs": "Czech",
    "ro": "Romanian",
    "da": "Danish",
    "hu": "Hungarian",
    "ta": "Tamil",
    "no": "Norwegian",
    "th": "Thai",
    "ur": "Urdu",
    "hr": "Croatian",
    "bg": "Bulgarian",
    "lt": "Lithuanian",
    "sk": "Slovak",
    "cy": "Welsh",
}


def get_whisper_model(model_name: str):
    """Load and cache a Whisper model"""
    with _model_lock:
        if model_name not in _model_cache:
            import whisper

            print(f"[Whisper] Loading model: {model_name}")
            _model_cache[model_name] = whisper.load_model(model_name)
            print(f"[Whisper] Model {model_name} ready")
        return _model_cache[model_name]


def transcribe_audio(job_id: str, audio_path: str, options: dict):
    """Background transcription task"""
    jobs_store[job_id]["status"] = "processing"
    jobs_store[job_id]["progress"] = 10

    try:
        model_name = options.get("model", "turbo")
        language = options.get("language", "auto")
        task = options.get("task", "transcribe")
        word_timestamps = options.get("word_timestamps", False)
        temperature = float(options.get("temperature", 0.0))

        jobs_store[job_id]["progress"] = 20
        jobs_store[job_id]["message"] = f"Loading model: {model_name}..."

        model = get_whisper_model(model_name)

        jobs_store[job_id]["progress"] = 50
        jobs_store[job_id]["message"] = "Transcribing audio..."

        decode_options = {
            "task": task,
            "word_timestamps": word_timestamps,
            "temperature": temperature,
        }
        if language and language != "auto":
            decode_options["language"] = language

        start_time = time.time()
        result = model.transcribe(audio_path, **decode_options)
        elapsed = round(time.time() - start_time, 2)

        jobs_store[job_id]["progress"] = 90
        jobs_store[job_id]["message"] = "Formatting results..."

        segments = []
        for seg in result.get("segments", []):
            segment_data = {
                "id": seg.get("id", 0),
                "start": round(seg.get("start", 0), 3),
                "end": round(seg.get("end", 0), 3),
                "text": seg.get("text", "").strip(),
            }
            if word_timestamps and "words" in seg:
                segment_data["words"] = [
                    {
                        "word": w.get("word", ""),
                        "start": round(w.get("start", 0), 3),
                        "end": round(w.get("end", 0), 3),
                    }
                    for w in seg["words"]
                ]
            segments.append(segment_data)

        jobs_store[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "message": "Done!",
                "result": {
                    "text": result.get("text", "").strip(),
                    "language": result.get("language", "unknown"),
                    "segments": segments,
                    "duration": elapsed,
                    "model": model_name,
                    "task": task,
                },
            }
        )

    except Exception as e:
        jobs_store[job_id].update(
            {
                "status": "failed",
                "progress": 0,
                "message": str(e),
                "error": traceback.format_exc(),
            }
        )
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass


# ============ API Routes ============


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/models", methods=["GET"])
def get_models():
    return jsonify({"models": MODELS})


@app.route("/api/languages", methods=["GET"])
def get_languages():
    lang_list = [{"code": k, "name": v} for k, v in LANGUAGES.items()]
    return jsonify({"languages": lang_list})


@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = Path(audio_file.filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        return (
            jsonify(
                {
                    "error": f'Unsupported format. Supported: {", ".join(sorted(SUPPORTED_FORMATS))}'
                }
            ),
            400,
        )

    job_id = str(uuid.uuid4())
    safe_filename = f"{job_id}{ext}"
    audio_path = str(UPLOAD_DIR / safe_filename)
    audio_file.save(audio_path)

    options = {
        "model": request.form.get("model", "turbo"),
        "language": request.form.get("language", "auto"),
        "task": request.form.get("task", "transcribe"),
        "word_timestamps": request.form.get("word_timestamps", "false").lower()
        == "true",
        "temperature": float(request.form.get("temperature", "0.0")),
    }

    jobs_store[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Queued...",
        "filename": audio_file.filename,
        "options": options,
        "created_at": time.time(),
    }

    thread = threading.Thread(
        target=transcribe_audio, args=(job_id, audio_path, options), daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/job/<job_id>", methods=["GET"])
def get_job(job_id: str):
    if job_id not in jobs_store:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(jobs_store[job_id])


@app.route("/api/job/<job_id>/stream", methods=["GET"])
def stream_job(job_id: str):
    """Server-Sent Events for real-time job progress"""

    def generate():
        while True:
            if job_id not in jobs_store:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            job = jobs_store[job_id]
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    jobs = sorted(
        jobs_store.values(), key=lambda x: x.get("created_at", 0), reverse=True
    )
    return jsonify({"jobs": list(jobs)[:50]})


@app.route("/api/health", methods=["GET"])
def health():
    try:
        import torch

        import whisper

        return jsonify(
            {
                "status": "ok",
                "whisper_version": getattr(whisper, "__version__", "unknown"),
                "torch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "loaded_models": list(_model_cache.keys()),
            }
        )
    except ImportError as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/export/<fmt>", methods=["POST"])
def export_result(fmt: str):
    data = request.json
    if not data or "result" not in data:
        return jsonify({"error": "No result data"}), 400

    result = data["result"]
    text = result.get("text", "")
    segments = result.get("segments", [])

    if fmt == "txt":
        content = text
        mimetype = "text/plain"
        filename = "transcription.txt"
    elif fmt == "srt":
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(
                f"{i}\n{_srt_time(seg['start'])} --> {_srt_time(seg['end'])}\n{seg['text']}\n"
            )
        content = "\n".join(lines)
        mimetype = "text/plain"
        filename = "transcription.srt"
    elif fmt == "vtt":
        lines = ["WEBVTT\n"]
        for seg in segments:
            lines.append(
                f"{_vtt_time(seg['start'])} --> {_vtt_time(seg['end'])}\n{seg['text']}\n"
            )
        content = "\n".join(lines)
        mimetype = "text/vtt"
        filename = "transcription.vtt"
    elif fmt == "json":
        content = json.dumps(result, indent=2, ensure_ascii=False)
        mimetype = "application/json"
        filename = "transcription.json"
    elif fmt == "tsv":
        lines = ["start\tend\ttext"]
        for seg in segments:
            lines.append(f"{seg['start']:.3f}\t{seg['end']:.3f}\t{seg['text']}")
        content = "\n".join(lines)
        mimetype = "text/tab-separated-values"
        filename = "transcription.tsv"
    else:
        return jsonify({"error": f"Unknown format: {fmt}"}), 400

    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _srt_time(s: float) -> str:
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _vtt_time(s: float) -> str:
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


if __name__ == "__main__":
    print("=" * 60)
    print("  Whisper Web UI - Starting Server")
    print("  Open: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
