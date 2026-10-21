"""Whisper (bóc băng) + VoxCPM (giọng nói AI)."""

import os
import threading
import time
import traceback
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request

from core import gpu
from core.jobs import UPLOAD_DIR, jobs, new_job
from core.jobs import gpu_wait_msg as _gpu_wait_msg

bp = Blueprint("speech", __name__)

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
                from core.voxengine import VoxEngine

                _vox_demo = VoxEngine(model_id="openbmb/VoxCPM2", device="auto")
                _vox_demo.load()
                print("[VoxCPM] VoxCPM2 loaded successfully")
            except Exception as e:
                print(f"[VoxCPM] Error loading model: {e}")
                raise RuntimeError(f"VoxCPM2 model failed to load: {e}") from e
        return _vox_demo


def _evict_whisper():
    with _wlock:
        _wmodel.clear()


def _evict_vox():
    global _vox_demo
    with _vox_lock:
        _vox_demo = None


gpu.register("whisper", _evict_whisper)
gpu.register("voxcpm", _evict_vox)


# ── Workers ───────────────────────────────────────────────────
def _worker_whisper_inner(job_id, audio_path, opts):
    jobs[job_id]["status"] = "processing"
    try:
        model_name = opts.get("model", "turbo")
        lang = opts.get("language", "auto")
        task = opts.get("task", "transcribe")

        jobs[job_id].update(
            {"progress": 10, "message": "[1/4] Đang xếp hàng & cấp phát GPU CUDA..."}
        )

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


def worker_whisper(job_id, audio_path, opts):
    with gpu.task(f"whisper:{job_id}", "whisper", on_wait=_gpu_wait_msg(job_id)):
        _worker_whisper_inner(job_id, audio_path, opts)


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
        res = wmodel.transcribe(ref_path, task="transcribe")
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


def split_text_chunks(text, limit=240):
    """Cắt văn bản dài thành các cụm ≤ limit ký tự, ưu tiên ngắt ở cuối câu."""
    import re as _re

    text = _re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return [text]
    sentences = _re.split(r"(?<=[.!?…;:])\s+", text)
    chunks, cur = [], ""
    for sent in sentences:
        if len(sent) > limit and cur:  # giữ đúng thứ tự: đẩy cụm đang dở ra trước
            chunks.append(cur)
            cur = ""
        while len(sent) > limit:  # câu quá dài: ngắt ở dấu phẩy/khoảng trắng gần nhất
            cut = max(sent.rfind(",", 0, limit), sent.rfind(" ", 0, limit))
            cut = cut if cut > limit // 3 else limit
            chunks.append(sent[: cut + 1].strip())
            sent = sent[cut + 1 :].strip()
        if cur and len(cur) + 1 + len(sent) > limit:
            chunks.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c]


def _worker_voxcpm_inner(job_id, text, control, ref_path, prompt_text, cfg):
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

        # Văn bản dài: đọc từng cụm câu rồi ghép lại (giọng giữ nguyên nhờ cùng mô tả/audio tham chiếu)
        chunks = split_text_chunks(text)
        parts, sample_rate, seed = [], None, None
        for ci, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                jobs[job_id].update(
                    progress=60 + int(25 * (ci - 1) / len(chunks)),
                    message=f"[3/4] Đang đọc đoạn {ci}/{len(chunks)}...",
                )
            sample_rate, part, seed = demo.generate_tts_audio(
                text_input=chunk,
                control_instruction=control,
                reference_wav_path_input=processed_ref,
                prompt_text=prompt_text,
                cfg_value_input=cfg,
            )
            parts.append(part)
        if len(parts) == 1:
            wav = parts[0]
        else:
            import numpy as np

            gap = np.zeros(int(sample_rate * 0.25), dtype=np.asarray(parts[0]).dtype)
            wav = np.concatenate(
                [x for p_ in parts for x in (np.asarray(p_), gap)][:-1]
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


def worker_voxcpm(job_id, text, control, ref_path, prompt_text, cfg):
    with gpu.task(f"voxcpm:{job_id}", "voxcpm", on_wait=_gpu_wait_msg(job_id)):
        _worker_voxcpm_inner(job_id, text, control, ref_path, prompt_text, cfg)


# ── API: Whisper Transcribe ───────────────────────────────────
@bp.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "Thiếu file âm thanh"}), 400
    f = request.files["audio"]
    ext = Path(f.filename).suffix.lower()
    if ext not in AUDIO_EXTS:
        return jsonify({"error": f"Định dạng không hỗ trợ: {ext}"}), 400

    job_id = new_job("Đã nhận, đang xếp hàng...")
    save_path = str(UPLOAD_DIR / f"{job_id}{ext}")
    f.save(save_path)

    opts = {
        "model": request.form.get("model", "turbo"),
        "language": request.form.get("language", "auto"),
        "task": request.form.get("task", "transcribe"),
    }
    threading.Thread(
        target=worker_whisper, args=(job_id, save_path, opts), daemon=True
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"})


# ── API: VoxCPM Generate ─────────────────────────────────────
@bp.route("/api/voxcpm/generate", methods=["POST"])
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

    job_id = new_job("Khởi tạo tác vụ VoxCPM...")
    threading.Thread(
        target=worker_voxcpm,
        args=(job_id, text, control, ref_path, prompt_text, cfg),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"})


# ── API: VoxCPM Info ─────────────────────────────────────────
@bp.route("/api/voxcpm/info")
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
