"""Cấu hình trung tâm của Hub: mặc định → data/config.json → biến môi trường."""

import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("PM_DATA_DIR") or os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULTS = {
    "admin_email": "tienthanh18082003@gmail.com",
    "auto_approve": True,  # True: đăng ký xong dùng ngay mọi công cụ; False: chờ admin duyệt + cấp quyền
    "ollama_url": "http://127.0.0.1:11434",
    "models": {
        "genreport": "qwen3.8:27b",
        "legal": "gemma4:31b",
        "cv": "gemma4:31b",
        "embed": "qwen3-embedding:0.6b",
    },
    "genreport_template": "",  # đường dẫn .docx tuỳ chọn; trống = dùng templates/report_template.docx
    "legal_min_similarity": 0.35,  # dưới ngưỡng này (cosine) coi như chưa có căn cứ
    "upload_ttl_hours": 24,
    "realesrgan_dir": os.path.join(BASE_DIR, "modules", "image_enhancer", "bin"),
    "gpu_idle_release_seconds": 300,  # GPU rảnh quá lâu → nhả mọi model khỏi VRAM; 0 = không tự nhả
}

_lock = threading.Lock()
_cache = None


def _load():
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except FileNotFoundError:
        pass
    except Exception as e:  # file hỏng: dùng mặc định, không làm sập server
        print(f"[config] Bỏ qua data/config.json lỗi: {e}")
    env = os.environ
    cfg["ollama_url"] = env.get(
        "PM_OLLAMA_URL", env.get("OLLAMA_HOST_URL", cfg["ollama_url"])
    )
    if env.get("PM_GPU_IDLE_SECONDS"):
        cfg["gpu_idle_release_seconds"] = int(env["PM_GPU_IDLE_SECONDS"])
    cfg["admin_email"] = env.get("PM_ADMIN_EMAIL", cfg["admin_email"]).strip().lower()
    for key, var in (
        ("genreport", "PM_MODEL_GENREPORT"),
        ("legal", "LEGAL_LLM_MODEL"),
        ("cv", "CV_OLLAMA_MODEL"), ("embed", "PM_MODEL_EMBED"),
    ):
        if env.get(var):
            cfg["models"][key] = env[var]
    return cfg


def get():
    global _cache
    with _lock:
        if _cache is None:
            _cache = _load()
        return _cache


def model(tool):
    return get()["models"][tool]


def reload():
    global _cache
    with _lock:
        _cache = None
    return get()
