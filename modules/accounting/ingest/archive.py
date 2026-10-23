"""
Giải nén ZIP an toàn trong bộ nhớ: chặn path traversal, symlink, file mã hoá, zip bomb
(tỉ lệ nén, tổng dung lượng, số thành viên) và lồng quá sâu. Không ghi ra đĩa ngoài kho.
"""

import posixpath
import stat
import zipfile

from .. import settings


class ArchiveError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def _safe_name(name):
    n = name.replace("\\", "/")
    if n.startswith("/") or (len(n) > 1 and n[1] == ":"):
        return None
    norm = posixpath.normpath(n)
    if norm.startswith("../") or norm == ".." or "/../" in f"/{norm}/":
        return None
    return norm


def members(path):
    """Trả về danh sách (tên trong archive, bytes) và danh sách cảnh báo (bỏ qua thành viên)."""
    cfg = settings.get()
    max_members = int(cfg["max_zip_members"])
    max_total = int(cfg["max_zip_total_mb"]) * 1024 * 1024
    max_file = int(cfg["max_file_mb"]) * 1024 * 1024
    max_ratio = float(cfg["max_zip_ratio"])
    out, skipped = [], []
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise ArchiveError("bad_zip", "File ZIP hỏng") from e
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > max_members:
            raise ArchiveError("zip_too_many", f"ZIP có {len(infos)} file, vượt giới hạn {max_members}")
        declared = sum(i.file_size for i in infos)
        if declared > max_total:
            raise ArchiveError("zip_too_large", "Tổng dung lượng giải nén vượt giới hạn")
        total = 0
        for i in infos:
            name = _safe_name(i.filename)
            if name is None:
                skipped.append({"name": i.filename, "reason": "path_traversal"})
                continue
            mode = (i.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                skipped.append({"name": name, "reason": "symlink"})
                continue
            if i.flag_bits & 0x1:
                skipped.append({"name": name, "reason": "encrypted"})
                continue
            if i.file_size > max_file:
                skipped.append({"name": name, "reason": "too_large"})
                continue
            if i.compress_size and i.file_size / max(i.compress_size, 1) > max_ratio:
                raise ArchiveError("zip_bomb", f"Tỉ lệ nén bất thường ở '{name}' (nghi zip bomb)")
            # Đọc có giới hạn: không tin file_size khai báo
            with z.open(i) as fh:
                data = fh.read(max_file + 1)
            if len(data) > max_file:
                skipped.append({"name": name, "reason": "too_large"})
                continue
            total += len(data)
            if total > max_total:
                raise ArchiveError("zip_too_large", "Tổng dung lượng giải nén vượt giới hạn")
            out.append((name, data))
    return out, skipped
