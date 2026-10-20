"""Tác vụ nền dùng chung: danh sách job, chủ sở hữu, dọn file tạm."""

import threading
import time
import uuid
from pathlib import Path

from . import auth, config

UPLOAD_DIR = Path(config.UPLOAD_DIR)
jobs = {}


def new_job(message, **extra):
    """Tạo tác vụ gắn với người dùng đang đăng nhập (người khác không xem được)."""
    job_id = str(uuid.uuid4())
    user = auth.current_user()
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress": 5,
        "message": message,
        "created_at": time.time(),
        "owner": user["email"] if user else None,
        **extra,
    }
    return job_id


def gpu_wait_msg(job_id):
    return lambda n: jobs[job_id].update(
        message=f"Đang chờ đến lượt dùng GPU ({n} tác vụ phía trước)..."
    )


def _cleanup_loop():
    while True:
        try:
            ttl = float(config.get()["upload_ttl_hours"]) * 3600
            now = time.time()
            for f in UPLOAD_DIR.iterdir():
                if f.is_file() and now - f.stat().st_mtime > ttl:
                    f.unlink(missing_ok=True)
            for jid in [
                k for k, j in jobs.items() if now - j.get("created_at", now) > ttl
            ]:
                jobs.pop(jid, None)
        except Exception as e:
            print(f"[cleanup] {e}")
        time.sleep(3600)


def start_cleanup():
    threading.Thread(target=_cleanup_loop, daemon=True).start()
