"""Mã băm mã nguồn giao diện (static/**/*.js|css, trừ static/dist).

Dùng chung cho server (đường dẫn /v/<mã>/…) và scripts/build_frontend.py (dấu của bản gộp).
Băm theo NỘI DUNG, chuẩn hoá CRLF → LF, để git checkout trên máy khác (autocrlf, mtime mới)
vẫn ra cùng một mã với lúc build.
"""

import hashlib
import os

CODE_EXT = (".js", ".css")
DIST = "dist"


def _code_files(static_dir):
    for root, dirs, files in os.walk(static_dir):
        if os.path.samefile(root, static_dir) and DIST in dirs:
            dirs.remove(DIST)
        for name in files:
            if name.endswith(CODE_EXT):
                full = os.path.join(root, name)
                yield os.path.relpath(full, static_dir).replace(os.sep, "/"), full


def signature(static_dir):
    """Rẻ: chỉ stat — dùng để biết có cần băm lại không."""
    return tuple(sorted((rel, os.stat(full).st_mtime_ns, os.stat(full).st_size) for rel, full in _code_files(static_dir)))


def source_hash(static_dir):
    h = hashlib.sha1()
    for rel, full in sorted(_code_files(static_dir)):
        with open(full, "rb") as f:
            h.update(rel.encode() + b"\0" + f.read().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()[:10]
