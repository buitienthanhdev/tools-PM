"""Nét Ảnh AI: Real-ESRGAN (ncnn-vulkan)."""

import threading
import traceback
import uuid
import warnings
from pathlib import Path

from flask import Blueprint, jsonify, request

from core import config as hubcfg
from core import gpu
from core.jobs import UPLOAD_DIR
from core.jobs import gpu_wait_msg as _gpu_wait_msg
from core.jobs import jobs, new_job

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
    files = list(UPLOAD_DIR.glob(f"image_{Path(str(upload_id)).name}.*"))
    if not files:
        return jsonify({"error": "Không tìm thấy ảnh đã upload"}), 404
    job_id = new_job("Đang xếp hàng...")
    threading.Thread(
        target=worker_image, args=(job_id, files[0], scale, model_key), daemon=True
    ).start()
    return jsonify({"job_id": job_id, "status": "queued"})
