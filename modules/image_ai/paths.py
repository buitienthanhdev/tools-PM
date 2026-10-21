"""Resolve writable AI model storage inside PM Tools' configured data dir."""

from pathlib import Path

from core import config


def data(*parts):
    return Path(config.DATA_DIR, *parts)


_providers = None


def ort_providers():
    """CUDA first (preloading its DLLs once), CPU as fallback."""
    global _providers
    if _providers is None:
        import onnxruntime as ort

        try:
            ort.preload_dlls()
        except Exception:
            pass
        available = ort.get_available_providers()
        _providers = [
            p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available
        ] or ["CPUExecutionProvider"]
    return _providers


def find_model(name):
    path = data("models", name)
    return path if path.is_file() else None
