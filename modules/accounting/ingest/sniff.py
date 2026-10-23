"""
Nhận diện định dạng thực tế từ nội dung (magic bytes, cấu trúc OOXML), không tin phần mở rộng.
Kết quả: (kind, mime, chi tiết). kind ∈ SUPPORTED, hoặc lỗi có cấu trúc qua REJECTED.
"""

import csv
import io
import json
import zipfile

SUPPORTED = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "xls": "application/vnd.ms-excel",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "xml": "application/xml",
    "json": "application/json",
    "txt": "text/plain",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "zip": "application/zip",
}
# Nhận diện được nhưng không xử lý (trả lỗi có cấu trúc)
REJECTED = {
    "executable": "File thực thi (chương trình) không được phép tải lên",
    "encrypted_office": "File Office được mã hoá bằng mật khẩu — hãy gỡ mật khẩu rồi tải lại",
    "doc": "Định dạng Word 97-2003 (.doc) chưa được hỗ trợ — hãy lưu lại thành .docx",
    "unknown": "Không nhận diện được định dạng file",
    "empty": "File rỗng",
}

TEXT_ENCODINGS = ("utf-8-sig", "utf-16", "cp1258", "cp1252")


def decode_text(data):
    """Giải mã văn bản; trả về (text, encoding) hoặc (None, None) nếu là nhị phân."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            return None, None
    if b"\x00" in data[:4096]:
        return None, None
    for enc in ("utf-8-sig", "cp1258"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None, None


def _ooxml(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            ct = ""
            if "[Content_Types].xml" in names:
                ct = z.read("[Content_Types].xml")[:200000].decode("utf-8", "replace")
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return "unknown", {"error": "ZIP hỏng"}
    if "xl/workbook.xml" in names:
        macro = "xl/vbaProject.bin" in names or "macroEnabled" in ct
        return ("xlsm" if macro else "xlsx"), {"has_macros": macro}
    if "word/document.xml" in names:
        return "docx", {"has_macros": "word/vbaProject.bin" in names}
    return "zip", {"members": len(names)}


def sniff(path, original_name=""):
    with open(path, "rb") as f:
        head = f.read(65536)
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    info = {"declared_ext": ext}
    if not head:
        return "empty", "", info
    if head.startswith(b"%PDF-") or (b"%PDF-" in head[:1024]):
        return "pdf", SUPPORTED["pdf"], info
    if head.startswith((b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe")):
        return "executable", "", info
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        kind, extra = _ooxml(path)
        info.update(extra)
        return kind, SUPPORTED.get(kind, ""), info
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):  # OLE compound file
        if "EncryptionInfo".encode("utf-16-le") in head or b"EncryptedPackage" in head:
            return "encrypted_office", "", info
        if "Workbook".encode("utf-16-le") in head or "Book".encode("utf-16-le") in head:
            return "xls", SUPPORTED["xls"], info
        if "WordDocument".encode("utf-16-le") in head:
            return "doc", "", info
        return "unknown", "", info
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", SUPPORTED["png"], info
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg", SUPPORTED["jpeg"], info
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff", SUPPORTED["tiff"], info
    if head.startswith(b"#!"):
        return "executable", "", info

    with open(path, "rb") as f:
        data = f.read()
    text, enc = decode_text(data)
    if text is None:
        return "unknown", "", info
    info["encoding"] = enc
    s = text.lstrip()
    if s.startswith("<"):
        return "xml", SUPPORTED["xml"], info
    if s[:1] in "{[":
        try:
            json.loads(s)
            return "json", SUPPORTED["json"], info
        except ValueError:
            pass
    kind = _delimited(text, ext)
    return kind, SUPPORTED[kind], info


def _delimited(text, ext):
    sample = "\n".join(text.splitlines()[:50])
    if not sample.strip():
        return "txt"
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return "txt"
    rows = list(csv.reader(io.StringIO(sample), dialect))
    widths = [len(r) for r in rows if r]
    if len(widths) < 2 or max(widths) < 2:
        return "txt"
    consistent = sum(1 for w in widths if w == widths[0]) / len(widths)
    if consistent < 0.8:
        return "txt"
    return "tsv" if dialect.delimiter == "\t" else "csv"
