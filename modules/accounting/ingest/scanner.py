"""
Quét virus qua Microsoft Defender (MpCmdRun) có sẵn trên Windows Server.
Kết quả: CLEAN | INFECTED | NOT_SCANNED (không có trình quét / tắt) | ERROR.
File INFECTED bị từ chối; NOT_SCANNED vẫn nhận nhưng được ghi rõ trong provenance.
"""

import os
import subprocess
from pathlib import Path

from .. import settings

_CANDIDATES = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe",
]


def _defender():
    for p in _CANDIDATES:
        if p.is_file():
            return str(p)
    platform = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows Defender" / "Platform"
    if platform.is_dir():
        for d in sorted(platform.iterdir(), reverse=True):
            exe = d / "MpCmdRun.exe"
            if exe.is_file():
                return str(exe)
    return None


def available():
    mode = settings.get()["antivirus"]
    return mode != "off" and _defender() is not None


def scan(path):
    """Quét một file. Không tự xoá/cách ly (-DisableRemediation) để giữ bằng chứng."""
    mode = settings.get()["antivirus"]
    if mode == "off":
        return "NOT_SCANNED", "antivirus=off"
    exe = _defender()
    if not exe:
        return ("ERROR", "không tìm thấy Defender") if mode == "defender" else ("NOT_SCANNED", "không có trình quét")
    try:
        r = subprocess.run(
            [exe, "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"],
            capture_output=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return "ERROR", "quét quá thời gian"
    except OSError as e:
        return "ERROR", f"không chạy được trình quét: {e}"
    if r.returncode == 0:
        return "CLEAN", "Microsoft Defender"
    if r.returncode == 2:
        return "INFECTED", "Microsoft Defender phát hiện mã độc"
    out = (r.stdout or b"").decode("utf-8", "replace")[-300:]
    return "ERROR", f"Defender mã {r.returncode}: {out.strip()}"
