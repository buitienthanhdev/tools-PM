r"""Bảo trì định kỳ: xoay vòng log lớn và sao lưu dữ liệu quan trọng.

Chạy:  .venv\Scripts\python.exe scripts\maintenance.py
Nên đặt vào Windows Task Scheduler (hàng ngày).
"""

import os
import shutil
import time
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(BASE, "logs")
DATA = os.path.join(BASE, "data")
BACKUPS = os.path.join(BASE, "backups")
LOG_MAX = 5 * 1024 * 1024
KEEP_BACKUPS = 14
CRITICAL = ("users.json", "secret.key", "config.json", "admin_setup_code.txt")


def rotate_logs():
    for name in os.listdir(LOGS) if os.path.isdir(LOGS) else []:
        p = os.path.join(LOGS, name)
        if name.endswith(".log") and os.path.getsize(p) > LOG_MAX:
            dst = f"{p}.{time.strftime('%Y%m%d')}.old"
            try:
                shutil.copyfile(p, dst)
                open(p, "w").close()  # cắt bớt tại chỗ, tiến trình đang ghi vẫn dùng được
                print(f"rotated {name}")
            except OSError as e:
                print(f"skip {name}: {e}")
    cutoff = time.time() - 14 * 86400
    for name in os.listdir(LOGS) if os.path.isdir(LOGS) else []:
        p = os.path.join(LOGS, name)
        if name.endswith(".old") and os.path.getmtime(p) < cutoff:
            os.remove(p)


def backup():
    os.makedirs(BACKUPS, exist_ok=True)
    out = os.path.join(BACKUPS, f"data_{time.strftime('%Y%m%d_%H%M%S')}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in CRITICAL:
            p = os.path.join(DATA, f)
            if os.path.exists(p):
                z.write(p, f)
        kb = os.path.join(DATA, "legal", "kb.json")
        if os.path.exists(kb):
            z.write(kb, "legal/kb.json")
    print(f"backup -> {out}")
    old = sorted(f for f in os.listdir(BACKUPS) if f.startswith("data_"))
    for f in old[:-KEEP_BACKUPS]:
        os.remove(os.path.join(BACKUPS, f))


if __name__ == "__main__":
    rotate_logs()
    backup()
