"""Kiểu dữ liệu chung của bộ trích xuất: mỗi giá trị đi kèm provenance tới vị trí trong file gốc."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# Trạng thái kiểm chứng của một giá trị
VERIFIED = "VERIFIED"  # nguồn có cấu trúc + qua kiểm tra chéo xác định
EXTRACTED = "EXTRACTED"  # có provenance, chưa kiểm tra chéo
NEEDS_REVIEW = "NEEDS_REVIEW"
NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
CONFLICTED = "CONFLICTED"
UNKNOWN = "UNKNOWN"


@dataclass
class Field:
    name: str
    raw: object
    normalized: object
    confidence: float
    method: str
    page: int | None = None
    sheet: str | None = None
    cell: str | None = None
    location: dict | None = None
    status: str = EXTRACTED


@dataclass
class Doc:
    doc_type: str  # invoice | bank_statement | ledger | table | text
    title: str
    data: dict = field(default_factory=dict)
    fields: list = field(default_factory=list)
    invoice: dict | None = None
    lines: list = field(default_factory=list)
    bank_txns: list = field(default_factory=list)
    entries: list = field(default_factory=list)
    status: str = EXTRACTED
    warnings: list = field(default_factory=list)


@dataclass
class Result:
    parser: str
    version: str
    status: str = "OK"  # OK | PARTIAL | FAILED | UNSUPPORTED
    error: dict | None = None
    docs: list = field(default_factory=list)
    text: str = ""
    stats: dict = field(default_factory=dict)
    model_id: str | None = None


class ExtractError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def fold(s):
    """Chuỗi so khớp: bỏ dấu tiếng Việt, chữ thường, gọn khoảng trắng."""
    s = str(s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^0-9a-zA-Z%]+", " ", s).strip().lower()
    return s


def norm_tax_id(s):
    if s is None:
        return None
    t = re.sub(r"[^0-9-]", "", str(s))
    return t or None


EXCEL_EPOCH = datetime(1899, 12, 30)


def parse_date(raw, day_first=True):
    """Trả về (ISO yyyy-mm-dd | None, ghi chú). Mặc định ngày trước tháng (dd/mm/yyyy) như chứng từ VN."""
    if raw is None or raw == "":
        return None, "empty"
    if isinstance(raw, datetime):
        return raw.date().isoformat(), "native"
    if isinstance(raw, date):
        return raw.isoformat(), "native"
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if 20000 < raw < 80000:
            return (EXCEL_EPOCH + timedelta(days=int(raw))).date().isoformat(), "excel_serial"
        return None, "invalid"
    s = str(raw).strip()
    m = re.search(r"ng[aà]y\D{0,12}(\d{1,2})\D{1,20}th[aá]ng\D{0,12}(\d{1,2})\D{1,20}n[aă]m\D{0,12}(\d{4})", s, re.I)
    if m:
        d, mo, y = map(int, m.groups())
        return _mk(y, mo, d)
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _mk(y, mo, d)
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})(?:\s.*)?", s)
    if m:
        a, b, y = map(int, m.groups())
        if y < 100:
            y += 2000
        d, mo = (a, b) if day_first else (b, a)
        return _mk(y, mo, d)
    return None, "invalid"


def _mk(y, mo, d):
    try:
        return date(y, mo, d).isoformat(), "parsed"
    except ValueError:
        return None, "invalid"


def date_order(values):
    """Xác định cột ngày dd/mm hay mm/dd từ dữ liệu: 'day_first' | 'month_first' | 'conflicted'."""
    day_first_evidence = month_first_evidence = 0
    for v in values:
        if not isinstance(v, str):
            continue
        m = re.fullmatch(r"\s*(\d{1,2})[-/.](\d{1,2})[-/.]\d{2,4}.*", v)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 >= b:
            day_first_evidence += 1
        elif b > 12 >= a:
            month_first_evidence += 1
    if day_first_evidence and month_first_evidence:
        return "conflicted"
    return "month_first" if month_first_evidence else "day_first"


def col_letter(idx0):
    s, n = "", idx0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s
