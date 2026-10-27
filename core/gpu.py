"""
Điều phối GPU dùng chung (16 GB không đủ cho Whisper + VoxCPM + Ollama + Real-ESRGAN cùng lúc).

- Mỗi lúc chỉ một tác vụ nặng chạy, tác vụ khác xếp hàng.
- Khi đổi "họ" model (whisper / voxcpm / ollama / esrgan / imageai / easyocr / video),
  giải phóng VRAM của các họ khác → công cụ đang chạy dùng trọn GPU.
- GPU rảnh quá `gpu_idle_release_seconds` (mặc định 5 phút) → nhả mọi model, VRAM về gần 0.
  Lần dùng sau nạp lại model (chậm hơn vài giây ở lượt đầu).
"""

import threading
import time
from contextlib import contextmanager

import requests

from . import config

_lock = threading.Lock()
_meta = threading.Lock()
_state = {"owner": None, "family": None, "since": None, "waiting": [], "idle_since": None, "released_at": None}
_evictors = {}  # family -> callable


def register(family, evict_fn):
    _evictors[family] = evict_fn


def _free_cuda():
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def evict_ollama():
    """Bảo Ollama nhả model đang nằm trong VRAM (keep_alive = 0)."""
    base = config.get()["ollama_url"]
    try:
        r = requests.get(f"{base}/api/ps", timeout=3)
        for m in r.json().get("models", []):
            requests.post(
                f"{base}/api/generate",
                json={"model": m["name"], "keep_alive": 0},
                timeout=10,
            )
    except Exception:
        pass


register("ollama", evict_ollama)


class Aborted(Exception):
    """Tác vụ bị huỷ khi còn đang xếp hàng chờ GPU."""


def _evict_all(keep=None):
    for fam, fn in list(_evictors.items()):
        if fam != keep:
            try:
                fn()
            except Exception as e:
                print(f"[gpu] evict {fam} lỗi: {e}")
    _free_cuda()


def release(reason="manual"):
    """Nhả mọi model khỏi VRAM ngay nếu GPU đang rảnh. Trả False nếu đang có tác vụ chạy."""
    if not _lock.acquire(blocking=False):
        return False
    try:
        with _meta:
            fam = _state["family"]
        _evict_all()
        with _meta:
            _state.update(family=None, idle_since=None, released_at=time.time())
        print(f"[gpu] đã nhả VRAM ({reason}; họ trước: {fam or 'không'})")
        return True
    finally:
        _lock.release()


def _idle_seconds():
    try:
        return int(config.get().get("gpu_idle_release_seconds", 300))
    except Exception:
        return 300


def _reaper():
    while True:
        time.sleep(15)
        limit = _idle_seconds()
        with _meta:
            idle_since, fam = _state["idle_since"], _state["family"]
        if limit > 0 and fam and idle_since and time.time() - idle_since >= limit:
            release(f"rảnh {limit}s")


_reaper_started = threading.Event()


def _ensure_reaper():
    if not _reaper_started.is_set():
        with _meta:
            if _reaper_started.is_set():
                return
            _reaper_started.set()
        threading.Thread(target=_reaper, name="gpu-idle-reaper", daemon=True).start()


@contextmanager
def task(name, family, on_wait=None, should_abort=None):
    """with gpu.task("whisper:abc", "whisper"): ... — xếp hàng rồi chạy độc quyền.
    should_abort(): trả True để rời hàng đợi (raise Aborted) — kiểm tra mỗi giây trong lúc chờ."""
    _ensure_reaper()
    with _meta:
        _state["waiting"].append(name)
        pos = len(_state["waiting"])
    if on_wait and (_lock.locked() or pos > 1):
        try:
            on_wait(pos - 1 + (1 if _lock.locked() else 0))
        except Exception:
            pass
    while not _lock.acquire(timeout=1):
        if should_abort and should_abort():
            with _meta:
                if name in _state["waiting"]:
                    _state["waiting"].remove(name)
            raise Aborted(name)
    try:
        with _meta:
            if name in _state["waiting"]:
                _state["waiting"].remove(name)
            prev = _state["family"]
            _state.update(owner=name, family=family, since=time.time(), idle_since=None)
        if prev and prev != family:
            _evict_all(keep=family)
        yield
    finally:
        with _meta:
            _state.update(owner=None, since=None, idle_since=time.time())
        _free_cuda()
        _lock.release()


def status():
    with _meta:
        busy = _state["owner"] is not None
        return {
            "busy": busy,
            "owner": _state["owner"],
            "family": _state["family"],
            "running_seconds": round(time.time() - _state["since"], 1) if busy else 0,
            "waiting": len(_state["waiting"]),
            "idle_release_seconds": _idle_seconds(),
            "release_in": (max(0, round(_idle_seconds() - (time.time() - _state["idle_since"])))
                           if not busy and _state["family"] and _state["idle_since"] and _idle_seconds() > 0 else None),
        }
