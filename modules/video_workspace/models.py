"""
Model và năng lực máy chủ.
- ensure(): chỉ tải model có trong catalog.MODELS, từ nguồn chính thức, kiểm SHA-256, ghi nguyên tử (.part → đổi tên).
- capabilities(): chạy `rve-backend.py --list_backends` trong venv riêng → backend thật sự khả dụng (không đoán).
"""

import hashlib
import os
import re
import subprocess
import threading
import time

import requests

from . import catalog, settings

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_verified = {}  # đường dẫn → (size, mtime) đã kiểm SHA-256
_dl_lock = threading.Lock()
_caps = {"checked_at": 0, "result": None, "running": False}
_caps_lock = threading.Lock()


class ModelError(Exception):
    pass


def model_path(model_id):
    m = catalog.MODELS[model_id]
    return os.path.join(settings.get()["models_dir"], m["file"])


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_ready(model_id):
    p = model_path(model_id)
    if not os.path.isfile(p):
        return False
    st = os.stat(p)
    key = (st.st_size, st.st_mtime)
    if _verified.get(p) == key:
        return True
    if _sha256(p) != catalog.MODELS[model_id]["sha256"]:
        return False
    _verified[p] = key
    return True


def ensure(model_id, log=print):
    """Trả về đường dẫn model đã kiểm tra; tải nếu thiếu và được phép."""
    if model_id not in catalog.MODELS:
        raise ModelError(f"Model không có trong danh mục đã duyệt: {model_id}")
    m = catalog.MODELS[model_id]
    p = model_path(model_id)
    with _dl_lock:
        if is_ready(model_id):
            return p
        if os.path.isfile(p):
            raise ModelError(f"File model {m['file']} sai SHA-256 — đã chặn (cần quản trị viên xoá file và tải lại)")
        if not settings.get()["allow_model_download"]:
            raise ModelError(f"Model {m['label']} chưa được cài trên máy chủ")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        url = catalog.SOURCE + m["file"]
        log(f"Tải model {m['file']} từ {url}")
        part = p + ".part"
        h = hashlib.sha256()
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    h.update(chunk)
        if h.hexdigest() != m["sha256"]:
            os.remove(part)
            raise ModelError(f"Model tải về sai SHA-256 ({m['file']}) — đã huỷ")
        os.replace(part, p)
        _verified[p] = (os.stat(p).st_size, os.stat(p).st_mtime)
        return p


def env_problems():
    cfg = settings.get()
    probs = []
    if not os.path.isfile(cfg["python"]):
        probs.append(f"Thiếu môi trường Python xử lý video ({cfg['python']})")
    if not os.path.isfile(settings.ffmpeg()) or not os.path.isfile(settings.ffprobe()):
        probs.append(f"Thiếu ffmpeg/ffprobe ({cfg['ffmpeg_dir']})")
    if not os.path.isfile(os.path.join(cfg["rve_dir"], "rve-backend.py")):
        probs.append("Thiếu mã nguồn REAL-Video-Enhancer (chạy scripts/setup_video_workspace.py)")
    return probs


def _detect():
    cfg = settings.get()
    res = {"ok": False, "backends": [], "gpus": [], "torch": None, "half": None, "error": None}
    probs = env_problems()
    if probs:
        res["error"] = "; ".join(probs)
        return res
    try:
        r = subprocess.run([cfg["python"], "-E", "-s", "rve-backend.py", "--list_backends"], cwd=cfg["rve_dir"],
                           capture_output=True, timeout=180, creationflags=NO_WINDOW)
        out = r.stdout.decode("utf-8", "replace")
        m = re.search(r"Available Backends: \[(.*?)\]", out)
        res["backends"] = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()] if m else []
        res["gpus"] = [g.strip() for g in re.findall(r"PyTorch GPU \d+: ([^\r\n]+)", out)]
        t = re.search(r"PyTorch Version: (\S+)", out)
        res["torch"] = t.group(1) if t else None
        res["half"] = "Half precision support: True" in out
        res["ok"] = any(b.startswith(cfg["backend"]) and "cuda" in b for b in res["backends"]) if cfg["backend"] == "pytorch" \
            else cfg["backend"] in res["backends"]
        if not res["ok"]:
            res["error"] = f"Backend {cfg['backend']} (GPU) không khả dụng: {res['backends'] or out[-300:]}"
    except Exception as e:
        res["error"] = f"Không chạy được backend RVE: {type(e).__name__}: {e}"
    return res


def capabilities(refresh=False, wait=False):
    """Kết quả nhận diện (cache 1 giờ); chạy nền lần đầu để không chặn request."""
    with _caps_lock:
        fresh = _caps["result"] is not None and time.time() - _caps["checked_at"] < 3600
        if (fresh and not refresh) or _caps["running"]:
            if not wait or _caps["result"] is not None:
                return _caps["result"]
        _caps["running"] = True

    def work():
        try:
            r = _detect()
        finally:
            with _caps_lock:
                _caps["running"] = False
        with _caps_lock:
            _caps.update(result=r, checked_at=time.time())

    if wait:
        work()
    else:
        threading.Thread(target=work, daemon=True, name="video-caps").start()
    return _caps["result"]
