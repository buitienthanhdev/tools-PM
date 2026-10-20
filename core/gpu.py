"""
Điều phối GPU dùng chung (16 GB không đủ cho Whisper + VoxCPM + Ollama + Real-ESRGAN cùng lúc).

- Mỗi lúc chỉ một tác vụ nặng chạy, tác vụ khác xếp hàng.
- Khi đổi "họ" model (whisper / voxcpm / ollama / esrgan), giải phóng VRAM của các họ khác.
"""

import threading
import time
from contextlib import contextmanager

import requests

from . import config

_lock = threading.Lock()
_meta = threading.Lock()
_state = {"owner": None, "family": None, "since": None, "waiting": []}
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


@contextmanager
def task(name, family, on_wait=None):
    """with gpu.task("whisper:abc", "whisper"): ... — xếp hàng rồi chạy độc quyền."""
    with _meta:
        _state["waiting"].append(name)
        pos = len(_state["waiting"])
    if on_wait and (_lock.locked() or pos > 1):
        try:
            on_wait(pos - 1 + (1 if _lock.locked() else 0))
        except Exception:
            pass
    _lock.acquire()
    try:
        with _meta:
            if name in _state["waiting"]:
                _state["waiting"].remove(name)
            prev = _state["family"]
            _state.update(owner=name, family=family, since=time.time())
        if prev and prev != family:
            for fam, fn in list(_evictors.items()):
                if fam != family:
                    try:
                        fn()
                    except Exception as e:
                        print(f"[gpu] evict {fam} lỗi: {e}")
            _free_cuda()
        yield
    finally:
        with _meta:
            _state.update(owner=None, since=None)
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
        }
