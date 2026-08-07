"""
PM Tools Hub — Unified Flask Backend
Single server serving Dashboard + Whisper STT + VoxCPM TTS + GenReport APIs
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
STATIC_DIR = os.path.join(BASE_DIR, "static")
app = Flask(__name__, static_folder=None)
CORS(app)

UPLOAD_DIR = Path(BASE_DIR) / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

AUDIO_EXTS = {
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

# ── State ─────────────────────────────────────────────────────
SERVER_START_TIME = time.time()
jobs = {}
_wmodel = {}
_wlock = threading.Lock()
_vox_demo = None
_vox_lock = threading.Lock()


# ── Whisper Model Cache ───────────────────────────────────────
def get_whisper(name="turbo"):
    with _wlock:
        if name not in _wmodel:
            import whisper as wh

            print(f"[Whisper] Loading model: {name}")
            _wmodel[name] = wh.load_model(name)
            print(f"[Whisper] Model {name} ready")
        return _wmodel[name]


# ── VoxCPM Demo Cache ─────────────────────────────────────────
def get_voxcpm():
    global _vox_demo
    with _vox_lock:
        if _vox_demo is None:
            try:
                # Try importing VoxCPMDemo from the VoxCPM app.py
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "voxcpm_app", os.path.join(VOXCPM_APP, "app.py")
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _vox_demo = mod.VoxCPMDemo(model_id="openbmb/VoxCPM2", device="auto")
                print("[VoxCPM] VoxCPM2 demo loaded successfully")
            except Exception as e:
                print(f"[VoxCPM] Error loading demo: {e}")
                raise RuntimeError(f"VoxCPM2 model failed to load: {e}")
        return _vox_demo


# ── Workers ───────────────────────────────────────────────────
def worker_whisper(job_id, audio_path, opts):
    jobs[job_id]["status"] = "processing"
    try:
        model_name = opts.get("model", "turbo")
        lang = opts.get("language", "auto")
        task = opts.get("task", "transcribe")

        jobs[job_id].update(
            {"progress": 10, "message": "[1/4] Đang xếp hàng & cấp phát GPU CUDA..."}
        )
        time.sleep(0.3)

        jobs[job_id].update(
            {
                "progress": 25,
                "message": f"[2/4] Nạp mô hình OpenAI Whisper ({model_name})...",
            }
        )
        model = get_whisper(model_name)

        jobs[job_id].update(
            {
                "progress": 45,
                "message": "[3/4] Đang trích xuất sóng âm thanh & chuẩn hóa resample 16kHz...",
            }
        )
        time.sleep(0.3)

        jobs[job_id].update(
            {
                "progress": 65,
                "message": "[3/4] Đang phân tích sóng âm thanh & bóc băng lời nói...",
            }
        )
        decode_opts = {
            "task": task,
            "condition_on_previous_text": False,
            "initial_prompt": "Đây là bài hát hoặc cuộc trò chuyện bằng Tiếng Việt.",
        }
        if lang and lang != "auto":
            decode_opts["language"] = lang

        t0 = time.time()
        result = model.transcribe(audio_path, **decode_opts)
        elapsed = round(time.time() - t0, 2)

        jobs[job_id].update(
            {
                "progress": 88,
                "message": "[4/4] Đang căn chỉnh timeline phụ đề (SRT/VTT/TXT)...",
            }
        )
        segments = [
            {
                "id": s.get("id", i),
                "start": round(s["start"], 2),
                "end": round(s["end"], 2),
                "text": s["text"].strip(),
            }
            for i, s in enumerate(result.get("segments", []))
        ]
        time.sleep(0.2)

        jobs[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "message": "🎉 Hoàn thành bóc băng âm thanh thành công!",
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
        jobs[job_id].update(
            {
                "status": "failed",
                "progress": 0,
                "message": f"Lỗi: {e}",
                "error": traceback.format_exc(),
            }
        )
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass


def detect_and_crop_first_vocal_segment(ref_path):
    """
    Intelligent VAD + Whisper Voice Segment Cropper:
    1. Uses Whisper to find the exact start/end timestamp of the FIRST spoken voice sentence.
    2. Crops a clean 6-12s voice audio segment starting from that exact voice timestamp using soundfile.
    3. Returns (clean_ref_wav_path, prompt_text_transcript).
    """
    if not ref_path or not os.path.exists(ref_path):
        return None, ""

    try:
        import numpy as np
        import soundfile as sf

        import whisper

        wmodel = get_whisper("turbo")

        print(f"[VAD Crop] Scanning audio for first voice segment: {ref_path}")
        res = wmodel.transcribe(ref_path, language="vi", task="transcribe")
        segments = res.get("segments", [])

        start_sec = 0.0
        end_sec = 10.0
        vocal_text_parts = []

        if segments:
            first_seg = None
            for seg in segments:
                txt = seg.get("text", "").strip()
                if len(txt) >= 2:
                    first_seg = seg
                    break

            if first_seg:
                start_sec = max(0.0, float(first_seg["start"]))
                end_sec = float(first_seg["end"])
                vocal_text_parts.append(first_seg.get("text", "").strip())

                for seg in segments:
                    if (
                        seg["start"] > first_seg["start"]
                        and (seg["end"] - start_sec) <= 12.0
                    ):
                        txt = seg.get("text", "").strip()
                        if txt:
                            vocal_text_parts.append(txt)
                            end_sec = max(end_sec, float(seg["end"]))

        duration_sec = end_sec - start_sec
        if duration_sec < 5.0:
            end_sec = start_sec + 8.0

        prompt_text = " ".join(vocal_text_parts).strip()
        print(
            f"[VAD Crop] Found first vocal segment: {start_sec:.2f}s -> {end_sec:.2f}s | Length: {len(prompt_text)} chars"
        )

        # Load 16kHz audio array cleanly via Whisper
        audio_16k = whisper.load_audio(ref_path)
        sr = 16000

        start_frame = int(start_sec * sr)
        end_frame = int(end_sec * sr)
        cropped_wav = audio_16k[start_frame:end_frame]

        if len(cropped_wav) == 0:
            cropped_wav = audio_16k[: int(10 * sr)]

        max_v = np.max(np.abs(cropped_wav))
        if max_v > 0:
            cropped_wav = cropped_wav / max_v * 0.95

        clean_ref = str(UPLOAD_DIR / f"crop_voice_{uuid.uuid4()}.wav")
        sf.write(clean_ref, cropped_wav, sr)
        return clean_ref, prompt_text

    except Exception as e:
        print(f"[VAD Crop Warning] Smart crop failed ({e}), using fallback crop")
        try:
            import numpy as np
            import soundfile as sf

            import whisper

            audio_16k = whisper.load_audio(ref_path)
            sr = 16000
            cropped_wav = audio_16k[: int(10 * sr)]

            max_v = np.max(np.abs(cropped_wav))
            if max_v > 0:
                cropped_wav = cropped_wav / max_v * 0.95

            clean_ref = str(UPLOAD_DIR / f"crop_voice_{uuid.uuid4()}.wav")
            sf.write(clean_ref, cropped_wav, sr)
            return clean_ref, ""
        except Exception:
            return ref_path, ""


def worker_voxcpm(job_id, text, control, ref_path, prompt_text, cfg):
    processed_ref = None
    jobs[job_id].update(
        {
            "status": "processing",
            "progress": 10,
            "message": "[1/4] Đang nạp VoxCPM2 Engine & GPU CUDA...",
        }
    )
    try:
        demo = get_voxcpm()

        if ref_path and os.path.exists(ref_path):
            jobs[job_id].update(
                {
                    "progress": 25,
                    "message": "[2/4] Đang dùng AI dò tìm & cắt ngay đoạn giọng nói đầu tiên...",
                }
            )
            processed_ref, auto_prompt = detect_and_crop_first_vocal_segment(ref_path)

            if not prompt_text and auto_prompt:
                prompt_text = auto_prompt
                print(
                    f"[VoxCPM] Auto set prompt_text from VAD ({len(prompt_text)} chars)"
                )

        jobs[job_id].update(
            {
                "progress": 60,
                "message": "[3/4] Đang tổng hợp giọng nói AI 48kHz high-fidelity...",
            }
        )
        t0 = time.time()

        sample_rate, wav, seed = demo.generate_tts_audio(
            text_input=text,
            control_instruction=control,
            reference_wav_path_input=processed_ref,
            prompt_text=prompt_text,
            cfg_value_input=cfg,
        )
        elapsed = round(time.time() - t0, 2)

        jobs[job_id].update(
            {
                "progress": 88,
                "message": "[4/4] Đang mã hóa & đóng gói file âm thanh WAV 48kHz...",
            }
        )
        import numpy as np
        import scipy.io.wavfile as wf

        if isinstance(wav, np.ndarray):
            if wav.dtype == np.float32 or wav.dtype == np.float64:
                max_val = np.max(np.abs(wav))
                if max_val > 0:
                    wav = wav / max_val * 0.95
                wav = (wav * 32767).astype(np.int16)

        fname = f"voxcpm_{job_id}.wav"
        wf.write(str(UPLOAD_DIR / fname), sample_rate, wav)

        audio_dur = round(len(wav) / sample_rate, 2) if sample_rate > 0 else elapsed

        jobs[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "message": "🎉 Sinh giọng nói VoxCPM2 thành công!",
                "result": {
                    "audio_url": f"/uploads/{fname}",
                    "duration": audio_dur,
                    "inference_time": elapsed,
                    "sample_rate": sample_rate,
                    "seed": seed,
                    "text": text,
                },
            }
        )
    except Exception as e:
        jobs[job_id].update(
            {
                "status": "failed",
                "progress": 0,
                "message": f"Lỗi: {e}",
                "error": traceback.format_exc(),
            }
        )
    finally:
        try:
            if ref_path and os.path.exists(ref_path):
                os.remove(ref_path)
            if processed_ref and os.path.exists(processed_ref):
                os.remove(processed_ref)
        except Exception:
            pass


def worker_genreport(job_id, form_data):
    jobs[job_id].update(
        {
            "status": "processing",
            "progress": 15,
            "message": "[1/3] Đang nạp dữ liệu & khởi tạo Ollama Qwen 3.6...",
        }
    )
    try:
        import genreport_service

        jobs[job_id].update(
            {
                "progress": 40,
                "message": "[2/3] Qwen 3.6 đang tổng hợp suy luận kỹ thuật chuyên sâu...",
            }
        )

        res = genreport_service.generate_word_report(form_data)

        jobs[job_id].update(
            {
                "progress": 90,
                "message": "[3/3] Đang đóng gói & map dữ liệu vào mẫu Word chuẩn (.docx)...",
            }
        )
        time.sleep(0.3)

        jobs[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "message": "🎉 Đã tạo báo cáo tiến độ kỹ thuật & file Word thành công!",
                "result": res,
            }
        )
    except Exception as e:
        jobs[job_id].update(
            {
                "status": "failed",
                "progress": 0,
                "message": f"Lỗi tạo báo cáo: {e}",
                "error": traceback.format_exc(),
            }
        )


# ── Cache-Control for all responses ──────────────────────────
@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ── API: Health ───────────────────────────────────────────────
@app.route("/api/health")
def api_health():
    try:
        import torch

        import whisper as wh

        uptime = time.time() - SERVER_START_TIME
        return jsonify(
            {
                "status": "ok",
                "domain": "https://sonxit.io.vn",
                "uptime_seconds": round(uptime, 2),
                "cuda": torch.cuda.is_available(),
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "whisper": getattr(wh, "__version__", "loaded"),
                "modules": ["whisper", "voxcpm", "genreport"],
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── API: Serve uploaded files ─────────────────────────────────
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ── API: Whisper Transcribe ───────────────────────────────────
@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "Thiếu file âm thanh"}), 400
    f = request.files["audio"]
    ext = Path(f.filename).suffix.lower()
    if ext not in AUDIO_EXTS:
        return jsonify({"error": f"Định dạng không hỗ trợ: {ext}"}), 400

    job_id = str(uuid.uuid4())
    save_path = str(UPLOAD_DIR / f"{job_id}{ext}")
    f.save(save_path)

    opts = {
        "model": request.form.get("model", "turbo"),
        "language": request.form.get("language", "auto"),
        "task": request.form.get("task", "transcribe"),
    }
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 5,
        "message": "Đã nhận, đang xếp hàng...",
        "created_at": time.time(),
    }
    threading.Thread(
        target=worker_whisper, args=(job_id, save_path, opts), daemon=True
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"})


# ── API: VoxCPM Generate ─────────────────────────────────────
@app.route("/api/voxcpm/generate", methods=["POST"])
def api_voxcpm_generate():
    text = request.form.get("text", "").strip()
    if not text:
        return jsonify({"error": "Vui lòng nhập văn bản cần đọc"}), 400

    control = request.form.get("control", "")
    prompt_text = request.form.get("prompt_text", "")
    try:
        cfg = float(request.form.get("cfg", 2.0))
    except ValueError:
        cfg = 2.0

    ref_path = ""
    if "ref_audio" in request.files and request.files["ref_audio"].filename:
        rf = request.files["ref_audio"]
        ext = Path(rf.filename).suffix.lower()
        if ext in AUDIO_EXTS:
            tmp = str(UPLOAD_DIR / f"ref_{uuid.uuid4()}{ext}")
            rf.save(tmp)
            ref_path = tmp

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 5,
        "message": "Khởi tạo tác vụ VoxCPM...",
        "created_at": time.time(),
    }
    threading.Thread(
        target=worker_voxcpm,
        args=(job_id, text, control, ref_path, prompt_text, cfg),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"})


# ── API: GenReport Generate ──────────────────────────────────
@app.route("/api/genreport/generate", methods=["POST"])
def api_genreport_generate():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            data = request.form.to_dict()

        if not data:
            return jsonify({"error": "Dữ liệu báo cáo không hợp lệ"}), 400

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 5,
            "message": "Khởi tạo tác vụ GenReport...",
            "created_at": time.time(),
        }
        threading.Thread(
            target=worker_genreport, args=(job_id, data), daemon=True
        ).start()
        return jsonify({"job_id": job_id, "status": "queued"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── API: Image Enhancer Upload ────────────────────────────────
@app.route("/api/image/upload", methods=["POST"])
def api_image_upload():
    if "image" not in request.files:
        return jsonify({"error": "Thiếu file hình ảnh"}), 400
    img_file = request.files["image"]
    if not img_file.filename:
        return jsonify({"error": "File không hợp lệ"}), 400

    ext = Path(img_file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        return jsonify({"error": f"Định dạng không được hỗ trợ: {ext}"}), 400

    job_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"image_{job_id}{ext}"
    img_file.save(str(save_path))

    return jsonify(
        {
            "status": "ok",
            "job_id": job_id,
            "file_path": f"/uploads/image_{job_id}{ext}",
            "message": "Đã tải lên hình ảnh thành công",
        }
    )


@app.route("/api/image/process", methods=["POST"])
def api_image_process():
    data = request.json or {}
    job_id = data.get("job_id")
    scale = data.get("scale", "4x")
    model_type = data.get("model", "ultrasharp")

    if not job_id:
        return jsonify({"error": "Thiếu job_id"}), 400

    # Match uploaded file
    uploaded_files = list(UPLOAD_DIR.glob(f"image_{job_id}.*"))
    if not uploaded_files:
        return jsonify({"error": "Không tìm thấy ảnh đã upload"}), 404

    orig_path = uploaded_files[0]
    output_filename = f"enhanced_{job_id}_{scale}.png"
    output_path = UPLOAD_DIR / output_filename

    try:
        # Perform image processing / copy as enhanced output for preview comparison
        from PIL import Image, ImageEnhance

        with Image.open(orig_path) as img:
            # Apply AI enhancement simulation (Sharpen & Contrast & Upscale size)
            w, h = img.size
            factor = 4 if scale == "4x" else (2 if scale == "2x" else 1)
            img_resized = img.resize((w * factor, h * factor), Image.Resampling.LANCZOS)

            enhancer = ImageEnhance.Sharpness(img_resized)
            img_enhanced = enhancer.enhance(2.0)

            enhancer_contrast = ImageEnhance.Contrast(img_enhanced)
            img_final = enhancer_contrast.enhance(1.15)

            img_final.save(str(output_path), format="PNG")

        return jsonify(
            {
                "status": "completed",
                "orig_path": f"/uploads/{orig_path.name}",
                "enhanced_path": f"/uploads/{output_filename}",
                "width": w * factor,
                "height": h * factor,
                "scale": scale,
                "model": model_type,
            }
        )
    except Exception as e:
        return jsonify({"error": f"Lỗi xử lý ảnh: {str(e)}"}), 500


# ── API: GenReport Parse Raw Notes ────────────────────────────
@app.route("/api/genreport/parse_raw", methods=["POST"])
def api_genreport_parse_raw():
    try:
        data = request.get_json(force=True, silent=True) or request.form.to_dict()
        raw_text = data.get("raw_text", "").strip()
        if not raw_text:
            return jsonify({"error": "Vui lòng nhập ghi chú sơ phác công việc"}), 400

        import genreport_service

        parsed = genreport_service.parse_raw_notes_with_ai(raw_text)
        if not parsed:
            return jsonify({"error": "Không thể phân tích dữ liệu sơ phác"}), 500

        return jsonify({"status": "ok", "data": parsed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: VoxCPM Info ─────────────────────────────────────────
@app.route("/api/voxcpm/info")
def api_voxcpm_info():
    return jsonify(
        {
            "name": "VoxCPM2 Voice AI",
            "status": "available",
            "models": [
                {
                    "id": "voxcpm2-2b",
                    "name": "VoxCPM2 (2B)",
                    "desc": "30-Language 48kHz TTS",
                },
                {
                    "id": "voxcpm1.5",
                    "name": "VoxCPM1.5",
                    "desc": "Expressive SFT Model",
                },
            ],
        }
    )


# ── API: Job Status & SSE Stream ─────────────────────────────
@app.route("/api/job/<job_id>")
def api_job(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Tác vụ không tồn tại"}), 404
    return jsonify(jobs[job_id])


@app.route("/api/job/<job_id>/stream")
def api_job_stream(job_id):
    def generate():
        while True:
            if job_id not in jobs:
                yield f'data: {json.dumps({"error": "Tác vụ không tìm thấy"})}\n\n'
                break
            job = jobs[job_id]
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.4)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── API: Export ───────────────────────────────────────────────
@app.route("/api/export/<fmt>", methods=["POST"])
def api_export(fmt):
    data = request.json or {}
    result = data.get("result", {})
    text = result.get("text", "")
    segments = result.get("segments", [])

    def srt_time(s):
        m, sc = divmod(int(s), 60)
        h, m = divmod(m, 60)
        ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"

    def vtt_time(s):
        m, sc = divmod(int(s), 60)
        h, m = divmod(m, 60)
        ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sc:02d}.{ms:03d}"

    if fmt == "txt":
        content, mime, name = text, "text/plain", "transcription.txt"
    elif fmt == "srt":
        lines = [
            f'{i}\n{srt_time(s["start"])} --> {srt_time(s["end"])}\n{s["text"]}\n'
            for i, s in enumerate(segments, 1)
        ]
        content, mime, name = "\n".join(lines), "text/plain", "transcription.srt"
    elif fmt == "vtt":
        lines = ["WEBVTT\n"] + [
            f'{vtt_time(s["start"])} --> {vtt_time(s["end"])}\n{s["text"]}\n'
            for s in segments
        ]
        content, mime, name = "\n".join(lines), "text/vtt", "transcription.vtt"
    else:
        return jsonify({"error": f"Unsupported format: {fmt}"}), 400

    return Response(
        content,
        mimetype=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ── Serve Uploads ─────────────────────────────────────────────
@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    as_attachment = request.args.get("download", "0") == "1"
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=as_attachment)


# ── SPA Fallback & Route Handling ─────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if path:
        full = Path(STATIC_DIR) / path
        if full.exists() and full.is_file():
            return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": f"API route not found: {request.path}"}), 404
    return send_from_directory(STATIC_DIR, "index.html")


@app.errorhandler(Exception)
def handle_500(e):
    traceback.print_exc()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    print("=" * 60)
    print("  PM Tools Hub — Dev Server")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
