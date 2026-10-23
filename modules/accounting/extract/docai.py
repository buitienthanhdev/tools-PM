"""
Adapter gọi PaddleOCR / docling trong venv riêng qua tiến trình con (docai_worker.py).
Tách venv vì hai thư viện này hạ phiên bản numpy / huggingface-hub mà các công cụ khác của Hub đang dùng.
Mỗi lúc chỉ một tiến trình (CPU nặng); có timeout; lỗi → trả None để bộ đọc chính tiếp tục bình thường.
"""

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from core import config as hubcfg

from .. import settings, telemetry

WORKER = Path(__file__).resolve().parent / "docai_worker.py"
_lock = threading.Lock()


def python_path():
    p = settings.get().get("docai_python") or str(Path(hubcfg.BASE_DIR).parent / "venvs" / "docai" / "Scripts" / "python.exe")
    return p if os.path.isfile(p) else None


def available(kind):
    mode = settings.get().get("paddle_ocr" if kind == "ocr" else "docling", "auto")
    return mode != "off" and python_path() is not None


def _run(cmd, path, timeout):
    py = python_path()
    if not py:
        return None
    with _lock, telemetry.span("docai", cmd=cmd):
        try:
            r = subprocess.run([py, "-I", str(WORKER), cmd, str(path)], capture_output=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"[docai] {cmd} lỗi: {type(e).__name__}")
            return None
    out = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0 or "@@DOCAI@@" not in out:
        print(f"[docai] {cmd} thất bại (mã {r.returncode}): {r.stderr.decode('utf-8', 'replace')[-300:]}")
        return None
    return json.loads(out.rsplit("@@DOCAI@@", 1)[1])


def ocr_image(png_bytes, scale=1.0, timeout=240):
    """Ảnh PNG → các dòng [(text, conf, bbox theo toạ độ gốc/scale)] — cùng dạng với extract.ocr.read_image."""
    tmp_dir = Path(settings.data_dir()) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=tmp_dir, prefix="ocr_", suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(png_bytes)
        res = _run("ocr", path, timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not res:
        return None, None
    from .ocr import group_lines

    boxes = [((b[0] / scale, b[1] / scale, b[2] / scale, b[3] / scale), t, c) for t, c, b in res["lines"]]
    return group_lines(boxes), res["model"]


def pdf_tables(pdf_bytes, timeout=900):
    """PDF → [{page, grid}] bằng docling (bảng không kẻ ô, bố cục phức tạp)."""
    tmp_dir = Path(settings.data_dir()) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=tmp_dir, prefix="doc_", suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pdf_bytes)
        res = _run("tables", path, timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return (res["tables"], res["model"]) if res else (None, None)
