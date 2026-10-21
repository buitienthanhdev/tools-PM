"""Nét Ảnh AI: Real-ESRGAN (ncnn-vulkan)."""

import threading
import time
import traceback
import uuid
import warnings
from pathlib import Path

from flask import Blueprint, jsonify, request

from core import auth, gpu
from core import config as hubcfg
from core.jobs import UPLOAD_DIR, jobs, new_job
from core.jobs import gpu_wait_msg as _gpu_wait_msg
from modules.image_ai import model_store as ai_model_store

bp = Blueprint("image", __name__)

# ── API: Image Enhancer (Real-ESRGAN thật) ────────────────────
# khoá model người dùng chọn → (tên model ncnn, hệ số gốc của model, dùng -s 2/3/4 trực tiếp?)
ESRGAN_MODELS = {
    "photo": ("realesrgan-x4plus", 4, False),
    "anime": ("realesrgan-x4plus-anime", 4, False),
    "fast": ("realesr-animevideov3", None, True),
}
MAX_OUTPUT_MP = 100  # megapixel đầu ra tối đa
MAX_IMAGE_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_IMAGE_UPLOAD_PIXELS = 32_000_000
MAX_IMAGE_AI_ENHANCE_PIXELS = 8_000_000
IMAGE_UPLOADS = {}
IMAGE_UPLOADS_LOCK = threading.RLock()
IMAGE_AI_LOCK = threading.Lock()
IMAGE_AI_CAPACITY_LOCK = threading.Lock()
MAX_PENDING_IMAGE_AI_JOBS = 3
IMAGE_AI_TOOLS = {
    "enhance": ("enhance", "Real-ESRGAN same-size enhancement"),
    "background": ("bg", "BiRefNet background removal"),
    "denoise": ("denoise", "SCUNet photo denoise"),
    "deblur": ("deblur", "NAFNet photo deblur"),
    "colorize": ("colorize", "DDColor photo colorization"),
    "erase": ("erase", "LaMa object removal"),
    "face_restore": ("face", "GFPGAN face restoration"),
}


def _inspect_image(path):
    from PIL import Image

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format not in {"PNG", "JPEG", "WEBP", "BMP"}:
                    raise ValueError("Chỉ hỗ trợ ảnh PNG, JPEG, WebP hoặc BMP.")
                image_format = image.format
                width, height = image.size
                if width < 1 or height < 1 or width * height > MAX_IMAGE_UPLOAD_PIXELS:
                    raise ValueError("Ảnh vượt giới hạn 32 megapixel.")
                image.verify()
            with Image.open(path) as image:
                image.load()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
    ) as exc:
        raise ValueError(
            "Không đọc được ảnh (file hỏng hoặc vượt giới hạn bộ nhớ)."
        ) from exc
    return width, height, image_format


def _save_upload(stream, path):
    size = 0
    with path.open("wb") as destination:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_IMAGE_UPLOAD_BYTES:
                raise ValueError("Ảnh vượt quá giới hạn tải lên 50 MB")
            destination.write(chunk)
    return size


def _esrgan_exe():
    d = Path(hubcfg.get()["realesrgan_dir"])
    exe = d / "realesrgan-ncnn-vulkan.exe"
    return (exe, d / "models") if exe.exists() else (None, None)


@bp.route("/api/image/upload", methods=["POST"])
def api_image_upload():
    if request.content_length and request.content_length > MAX_IMAGE_UPLOAD_BYTES + 1024 * 1024:
        return jsonify({"error": "Ảnh vượt quá giới hạn tải lên 50 MB"}), 413
    if "image" not in request.files:
        return jsonify({"error": "Thiếu file hình ảnh"}), 400
    img_file = request.files["image"]
    if not img_file.filename:
        return jsonify({"error": "File không hợp lệ"}), 400

    ext = Path(img_file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        return jsonify({"error": "Chỉ hỗ trợ ảnh PNG, JPEG, WebP hoặc BMP."}), 400

    upload_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"image_{upload_id}{ext}"
    try:
        _save_upload(img_file.stream, save_path)
    except ValueError as exc:
        save_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 413
    except OSError:
        save_path.unlink(missing_ok=True)
        raise
    try:
        w, h, image_format = _inspect_image(save_path)
    except ValueError as exc:
        save_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400
    expected_format = {
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".webp": "WEBP",
        ".bmp": "BMP",
    }[ext]
    if image_format != expected_format:
        save_path.unlink(missing_ok=True)
        return jsonify({"error": "Phần mở rộng không khớp với định dạng ảnh thực tế."}), 400

    current_user = auth.current_user()
    now = time.time()
    with IMAGE_UPLOADS_LOCK:
        ttl_seconds = float(hubcfg.get()["upload_ttl_hours"]) * 3600
        for previous_id, record in tuple(IMAGE_UPLOADS.items()):
            if now - record["created_at"] > ttl_seconds:
                IMAGE_UPLOADS.pop(previous_id, None)
        IMAGE_UPLOADS[upload_id] = {
            "path": save_path,
            "width": w,
            "height": h,
            "owner": current_user["email"] if current_user else None,
            "created_at": now,
        }

    return jsonify(
        {
            "status": "ok",
            "job_id": upload_id,
            "width": w,
            "height": h,
            "file_path": f"/uploads/image_{upload_id}{ext}",
            "message": "Đã tải lên hình ảnh thành công",
        }
    )


def _uploaded_image(upload_id):
    if not isinstance(upload_id, str) or len(upload_id) != 36:
        return None
    with IMAGE_UPLOADS_LOCK:
        record = IMAGE_UPLOADS.get(upload_id)
    if not record:
        return None
    if not record["path"].is_file():
        with IMAGE_UPLOADS_LOCK:
            IMAGE_UPLOADS.pop(upload_id, None)
        return None
    denied = auth.check_job_owner(record)
    return denied or record


def authorize_image_upload(filename):
    if not filename.startswith(("image_", "enhanced_")):
        return None

    stem = Path(filename).stem
    if stem.startswith("image_ai_"):
        job_id = stem.removeprefix("image_ai_")
        expected_path = f"/uploads/{filename}"
        job = jobs.get(job_id)
        if not job or (job.get("result") or {}).get("enhanced_path") != expected_path:
            return jsonify({"error": "Ảnh không tồn tại."}), 404
        return auth.check_job_owner(job)

    if stem.startswith("enhanced_"):
        job_id = stem.removeprefix("enhanced_")
        expected_path = f"/uploads/{filename}"
        job = jobs.get(job_id)
        if not job or (job.get("result") or {}).get("enhanced_path") != expected_path:
            return jsonify({"error": "Ảnh không tồn tại."}), 404
        return auth.check_job_owner(job)

    if stem.startswith("image_"):
        upload_id = stem.removeprefix("image_")
        with IMAGE_UPLOADS_LOCK:
            record = IMAGE_UPLOADS.get(upload_id)
        if not record or record["path"].name != filename or not record["path"].is_file():
            return jsonify({"error": "Ảnh không tồn tại hoặc đã hết hạn."}), 404
        return auth.check_job_owner(record)

    return jsonify({"error": "Ảnh không tồn tại."}), 404


def _onnx_runtime_available():
    try:
        import onnxruntime

        return True, onnxruntime.__version__
    except ImportError:
        return False, None


@bp.route("/api/image/ai/models", methods=["GET"])
def api_image_ai_models():
    runtime_available, runtime_version = _onnx_runtime_available()
    return jsonify(
        {
            "runtime_available": runtime_available,
            "runtime_version": runtime_version,
            "provider": "CPUExecutionProvider",
            "models": {
                key: ai_model_store.status(key)
                for key in sorted({model for model, _ in IMAGE_AI_TOOLS.values()})
            },
        }
    )


@bp.route("/api/image/ai/models/<model_key>", methods=["POST"])
def api_image_ai_model_download(model_key):
    if not ai_model_store.valid(model_key):
        return jsonify({"error": "Mô hình ảnh không hợp lệ."}), 404
    runtime_available, _ = _onnx_runtime_available()
    if not runtime_available:
        return jsonify({"error": "Máy chủ chưa cài onnxruntime."}), 503
    ai_model_store.start_download(model_key)
    return jsonify(ai_model_store.status(model_key)), 202


def _image_ai_progress(job_id, done, total, message):
    percent = 10 + int(max(0, min(1, done / max(total, 1))) * 85)
    jobs[job_id].update(progress=percent, message=message)


def _run_image_ai(job_id, tool, image_path, mask_path=None, background="transparent"):
    output_path = UPLOAD_DIR / f"image_ai_{job_id}.png"
    try:
        job = jobs[job_id]
        job.update(status="processing", progress=5, message="Đang chờ tác vụ AI khác...")
        with IMAGE_AI_LOCK:
            if job.get("status") == "cancelled":
                return

            def progress(done, total=None, message=None):
                if isinstance(total, str):
                    message = total
                    total = 100
                elif total is None:
                    total = 100
                    done = int(done)
                _image_ai_progress(
                    job_id,
                    done,
                    total,
                    message or f"{IMAGE_AI_TOOLS[tool][1]}: {done}/{total}",
                )

            if tool == "background":
                from modules.image_ai import bg_remove

                width, height = bg_remove.remove_background(
                    image_path,
                    output_path,
                    background=background,
                    progress_cb=progress,
                )
            elif tool in ("denoise", "deblur"):
                from modules.image_ai import restore_engine

                width, height = restore_engine.clean_image(
                    tool,
                    image_path,
                    output_path,
                    progress_cb=progress,
                )
            elif tool == "colorize":
                from modules.image_ai import restore_engine

                width, height = restore_engine.colorize_image(
                    image_path, output_path, progress_cb=progress
                )
            elif tool == "erase":
                from modules.image_ai import restore_engine

                width, height = restore_engine.inpaint_image(
                    image_path, mask_path, output_path, progress_cb=progress
                )
            elif tool == "face_restore":
                import cv2
                import numpy as np
                from PIL import Image

                from modules.image_ai import face_restore

                with Image.open(image_path) as source:
                    rgb = np.asarray(source.convert("RGB"))
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                restored = face_restore.restore_faces(bgr, progress_cb=progress)
                if not cv2.imwrite(str(output_path), restored):
                    raise RuntimeError("Không ghi được ảnh phục hồi khuôn mặt.")
                height, width = restored.shape[:2]
            elif tool == "enhance":
                from modules.image_ai import ai_engine

                width, height = ai_engine.enhance_image(
                    image_path, output_path, progress_cb=progress
                )
            else:
                raise ValueError("Công cụ ảnh không được hỗ trợ.")

        job.update(
            status="completed",
            progress=100,
            message="Hoàn tất xử lý ảnh.",
            result={
                "tool": tool,
                "engine": IMAGE_AI_TOOLS[tool][1],
                "enhanced_path": f"/uploads/{output_path.name}",
                "width": width,
                "height": height,
                "format": "PNG",
            },
        )
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        print(f"[image-ai] {tool} failed for task {job_id}: {exc}", flush=True)
        jobs[job_id].update(
            status="failed",
            progress=0,
            message=f"{IMAGE_AI_TOOLS[tool][1]} lỗi: {str(exc)[:200]}",
        )
    finally:
        if mask_path:
            mask_path.unlink(missing_ok=True)


@bp.route("/api/image/ai/<tool>", methods=["POST"])
def api_image_ai_start(tool):
    if tool not in IMAGE_AI_TOOLS:
        return jsonify({"error": "Công cụ AI ảnh không hợp lệ."}), 404
    runtime_available, _ = _onnx_runtime_available()
    if not runtime_available:
        return jsonify({"error": "Máy chủ chưa cài onnxruntime."}), 503

    upload_id = request.form.get("job_id")
    record = _uploaded_image(upload_id)
    if record is None:
        return jsonify({"error": "Không tìm thấy ảnh đã tải lên."}), 404
    if not isinstance(record, dict):
        return record

    model_key = IMAGE_AI_TOOLS[tool][0]
    if not ai_model_store.available(model_key):
        model_status = ai_model_store.status(model_key)
        return jsonify(
            {
                "error": "Cần tải model trước khi chạy công cụ này.",
                "model": model_key,
                "model_size": model_status["size"],
            }
        ), 409
    if tool == "enhance":
        width = record.get("width")
        height = record.get("height")
        if width is None or height is None:
            width, height, _ = _inspect_image(record["path"])
        if width * height > MAX_IMAGE_AI_ENHANCE_PIXELS:
            return jsonify(
                {
                    "error": "Tăng chi tiết AI hiện giới hạn ảnh đầu vào 8 megapixel để kiểm soát bộ nhớ.",
                    "max_pixels": MAX_IMAGE_AI_ENHANCE_PIXELS,
                }
            ), 413

    background = request.form.get("background", "transparent")
    if tool == "background" and background != "transparent":
        import re

        if not re.fullmatch(r"#[0-9a-fA-F]{6}", background):
            return jsonify({"error": "Màu nền phải có dạng #RRGGBB."}), 400

    mask_path = None
    if tool == "erase":
        mask = request.files.get("mask")
        if mask is None or not mask.filename:
            return jsonify({"error": "Tải lên vùng mask trắng/đen để xóa vật thể."}), 400
        if Path(mask.filename).suffix.lower() != ".png":
            return jsonify({"error": "Mask phải là ảnh PNG."}), 400
        mask_path = UPLOAD_DIR / f"image_mask_{uuid.uuid4()}.png"
        try:
            _save_upload(mask.stream, mask_path)
            mask_width, mask_height, mask_format = _inspect_image(mask_path)
            if mask_format != "PNG":
                raise ValueError("Mask phải là ảnh PNG.")
            from PIL import Image

            with Image.open(mask_path) as mask_image:
                mask_image.load()
                if mask_image.mode not in {"1", "L", "LA", "RGBA", "RGB"}:
                    raise ValueError("Mask PNG không có kênh màu được hỗ trợ.")
            with Image.open(record["path"]) as image:
                if abs(
                    image.width / image.height - mask_width / mask_height
                ) > 0.01:
                    raise ValueError("Tỷ lệ khung hình mask phải khớp với ảnh gốc.")
        except (OSError, ValueError) as exc:
            mask_path.unlink(missing_ok=True)
            return jsonify({"error": str(exc)}), 400

    with IMAGE_AI_CAPACITY_LOCK:
        pending = sum(
            1
            for job in jobs.values()
            if job.get("tool") in IMAGE_AI_TOOLS
            and job.get("status") in {"queued", "processing"}
        )
        if pending >= MAX_PENDING_IMAGE_AI_JOBS:
            if mask_path:
                mask_path.unlink(missing_ok=True)
            return jsonify(
                {"error": "Hàng đợi AI đang đầy. Hãy chờ một tác vụ hoàn tất rồi thử lại."}
            ), 429

        job_id = new_job(
            f"Đang chờ {IMAGE_AI_TOOLS[tool][1]}...",
            tool=tool,
            result=None,
        )
        worker = threading.Thread(
            target=_run_image_ai,
            args=(job_id, tool, record["path"], mask_path, background),
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError:
            jobs.pop(job_id, None)
            if mask_path:
                mask_path.unlink(missing_ok=True)
            raise
    return jsonify({"job_id": job_id, "status": "queued", "tool": tool}), 202


def worker_image(job_id, orig_path, scale, model_key):
    import re as _re
    import subprocess

    from PIL import Image

    out_path = UPLOAD_DIR / f"enhanced_{job_id}.png"
    tmp_out = UPLOAD_DIR / f"enhanced_{job_id}_raw.png"
    try:
        exe, models_dir = _esrgan_exe()
        if not exe:
            raise RuntimeError(
                "Chưa cài Real-ESRGAN (thiếu realesrgan-ncnn-vulkan.exe)"
            )
        name, native, is_native = ESRGAN_MODELS[model_key]
        factor = 4 if scale == "4x" else 2
        if is_native:
            model, run_scale = f"{name}-x{factor}", factor
        else:
            model, run_scale = name, native
        with Image.open(orig_path) as im:
            w, h = im.size
        if w * h * run_scale * run_scale > MAX_OUTPUT_MP * 1_000_000:
            raise RuntimeError(
                f"Ảnh {w}x{h} quá lớn để phóng {scale} (tối đa {MAX_OUTPUT_MP} megapixel đầu ra)"
            )
        cmd = [
            str(exe),
            "-i",
            str(orig_path),
            "-o",
            str(tmp_out),
            "-n",
            model,
            "-s",
            str(run_scale),
            "-f",
            "png",
            "-m",
            str(models_dir),
        ]
        jobs[job_id].update(status="processing", progress=8, message="Đang chờ GPU...")
        with gpu.task(f"image:{job_id}", "esrgan", on_wait=_gpu_wait_msg(job_id)):
            jobs[job_id].update(
                progress=12, message=f"Real-ESRGAN đang phóng {scale} ({model})..."
            )
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(exe.parent),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            tail = []
            for line in proc.stdout:
                tail = (tail + [line.strip()])[-6:]
                m = _re.match(r"\s*([\d.]+)%", line)
                if m:
                    jobs[job_id].update(progress=12 + int(float(m.group(1)) * 0.75))
            proc.wait(timeout=1800)
        if proc.returncode != 0 or not tmp_out.exists():
            raise RuntimeError(
                "Real-ESRGAN lỗi: " + " | ".join(t for t in tail if t)[-300:]
            )

        jobs[job_id].update(progress=92, message="Đang hoàn thiện ảnh...")
        with Image.open(tmp_out) as big:
            target = (w * factor, h * factor)
            if big.size != target:  # model x4 nhưng người dùng chọn 2X
                big = big.resize(target, Image.Resampling.LANCZOS)
            big.save(str(out_path), format="PNG")
        jobs[job_id].update(
            status="completed",
            progress=100,
            message="Hoàn tất",
            result={
                "orig_path": f"/uploads/{Path(orig_path).name}",
                "enhanced_path": f"/uploads/{out_path.name}",
                "width": w * factor,
                "height": h * factor,
                "scale": scale,
                "model": model_key,
                "engine": "Real-ESRGAN",
            },
        )
    except Exception as e:
        jobs[job_id].update(
            status="failed",
            progress=0,
            message=f"Lỗi: {e}",
            error=traceback.format_exc(),
        )
    finally:
        tmp_out.unlink(missing_ok=True)


@bp.route("/api/image/process", methods=["POST"])
def api_image_process():
    data = request.json or {}
    upload_id = data.get("job_id")
    scale = data.get("scale", "4x")
    model_key = data.get("model", "photo")
    if not upload_id:
        return jsonify({"error": "Thiếu job_id"}), 400
    if scale not in ("2x", "4x"):
        return jsonify({"error": "Tỉ lệ chỉ hỗ trợ 2x hoặc 4x"}), 400
    if model_key not in ESRGAN_MODELS:
        return jsonify({"error": "Mô hình không hợp lệ"}), 400
    exe, _ = _esrgan_exe()
    if not exe:
        return jsonify({"error": "Máy chủ chưa cài Real-ESRGAN"}), 503
    record = _uploaded_image(str(upload_id))
    if record is None:
        return jsonify({"error": "Không tìm thấy ảnh đã upload"}), 404
    if not isinstance(record, dict):
        return record
    job_id = new_job("Đang xếp hàng...")
    threading.Thread(
        target=worker_image,
        args=(job_id, record["path"], scale, model_key),
        daemon=True,
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"})
