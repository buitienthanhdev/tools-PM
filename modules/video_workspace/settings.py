"""Cấu hình Video Workspace: mặc định → khoá "video" trong data/config.json → biến môi trường."""

import os

from core import config as hubcfg

_ROOT = os.path.dirname(hubcfg.BASE_DIR)  # thư mục chứa Hub (D:\tools PM)
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "enabled": False,  # tắt mặc định — bật sau khi cài venv/ffmpeg/model và kiểm thử
    "data_dir": "",  # trống = <PM_DATA_DIR>/video
    # Môi trường xử lý (ngoài git): venv riêng có PyTorch CUDA, ffmpeg/ffprobe cố định phiên bản, thư mục model
    "python": os.path.join(_ROOT, "venvs", "video", "Scripts", "python.exe"),
    "ffmpeg_dir": os.path.join(_ROOT, "venvs", "video-bin", "ffmpeg-7.1.1-essentials_build", "bin"),
    "models_dir": os.path.join(_ROOT, "venvs", "video-models"),
    "rve_dir": os.path.join(MODULE_DIR, "vendor", "real-video-enhancer", "backend"),
    "backend": "pytorch",  # backend RVE đã kiểm thử trên máy này (CUDA)
    "gpu_id": 0,
    "gpu_concurrency": 1,  # số job chạy đồng thời trên một GPU
    "allow_model_download": True,  # chỉ tải từ danh mục đã duyệt (catalog.py), kiểm tra SHA-256
    "allow_noncommercial_models": True,  # model giấy phép CC BY-NC*: tắt nếu dùng thương mại
    # Giới hạn
    "max_upload_mb": 4096,
    "chunk_mb": 32,  # mỗi phần tải lên ≤ giới hạn 100 MB/request của Cloudflare
    "max_duration_s": 1800,
    "max_input_pixels": 3840 * 2160,
    "max_output_pixels": 3840 * 2160,
    "max_output_fps": 240,
    "max_queued_per_user": 3,
    "max_queued_total": 30,
    "max_runtime_s": 4 * 3600,
    "stall_timeout_s": 300,  # không có khung hình mới trong N giây → coi là treo
    "max_attempts": 2,  # job bị gián đoạn (máy chủ khởi động lại) được chạy lại tối đa N lần tổng cộng
    "quota_per_user_gb": 30,
    "retention_hours": 72,
    "preview_seconds": 10,
    "crf": 18,
    "min_free_disk_gb": 10,
}


def get():
    cfg = dict(DEFAULTS)
    cfg.update(hubcfg.get().get("video") or {})
    if os.environ.get("PM_VIDEO"):
        cfg["enabled"] = os.environ["PM_VIDEO"] == "1"
    if os.environ.get("PM_VIDEO_DIR"):
        cfg["data_dir"] = os.environ["PM_VIDEO_DIR"]
    if not cfg["data_dir"]:
        cfg["data_dir"] = os.path.join(hubcfg.DATA_DIR, "video")
    return cfg


def data_dir(*parts):
    d = os.path.join(get()["data_dir"], *parts)
    os.makedirs(d, exist_ok=True)
    return d


def ffmpeg():
    return os.path.join(get()["ffmpeg_dir"], "ffmpeg.exe" if os.name == "nt" else "ffmpeg")


def ffprobe():
    return os.path.join(get()["ffmpeg_dir"], "ffprobe.exe" if os.name == "nt" else "ffprobe")
