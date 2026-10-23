"""
Kho file bất biến: bản gốc lưu theo SHA-256 trong thư mục riêng của từng tổ chức, đặt chỉ-đọc.
Không có hàm sửa/xoá bản gốc. Artifact (báo cáo) lưu riêng, mỗi phiên bản một file.
"""

import hashlib
import os
import stat
import tempfile
from pathlib import Path

from . import settings

CHUNK = 1024 * 1024


class StorageError(RuntimeError):
    pass


def _root(kind, org_id):
    if not org_id or "/" in org_id or "\\" in org_id or ".." in org_id:
        raise StorageError("org_id không hợp lệ")
    p = Path(settings.data_dir()) / kind / org_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def hash_stream(fp, limit_bytes=None):
    """Đọc stream vào file tạm, trả về (đường dẫn tạm, sha256, kích thước). Vượt giới hạn → lỗi."""
    h = hashlib.sha256()
    size = 0
    tmp_dir = Path(settings.data_dir()) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=tmp_dir, prefix="up_")
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = fp.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if limit_bytes is not None and size > limit_bytes:
                    raise StorageError(f"file vượt giới hạn {limit_bytes // (1024 * 1024)} MB")
                h.update(chunk)
                out.write(chunk)
    except Exception:
        _unlink(tmp)
        raise
    return tmp, h.hexdigest(), size


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def put_original(org_id, tmp_path, sha256):
    """Chuyển file tạm vào kho bất biến. Nếu đã có (cùng hash) thì giữ bản cũ, xoá file tạm."""
    dest = _root("objects", org_id) / sha256[:2] / sha256
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        _unlink(tmp_path)
    else:
        os.replace(tmp_path, dest)
        os.chmod(dest, stat.S_IREAD)
    return str(dest.relative_to(settings.data_dir()))


def put_bytes(org_id, data):
    sha = sha256_bytes(data)
    tmp_dir = Path(settings.data_dir()) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=tmp_dir, prefix="b_")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return put_original(org_id, tmp, sha), sha


def put_artifact(org_id, artifact_id, ext, data):
    dest = _root("artifacts", org_id) / f"{artifact_id}.{ext}"
    if dest.exists():
        raise StorageError("artifact đã tồn tại — phiên bản mới phải có id mới")
    tmp = dest.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)
    os.chmod(dest, stat.S_IREAD)
    return str(dest.relative_to(settings.data_dir())), sha256_bytes(data), len(data)


def abspath(rel):
    base = Path(settings.data_dir()).resolve()
    p = (base / rel).resolve()
    if base not in p.parents:
        raise StorageError("đường dẫn ngoài kho dữ liệu")
    return p


def read(rel):
    return abspath(rel).read_bytes()


def verify(rel, sha256):
    h = hashlib.sha256()
    with open(abspath(rel), "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest() == sha256


def _unlink(p):
    try:
        os.chmod(p, stat.S_IWRITE)
        os.unlink(p)
    except OSError:
        pass


def discard_tmp(p):
    _unlink(p)
