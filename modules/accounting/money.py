"""
Tiền tệ bằng Decimal. Không bao giờ dùng float cho số tiền.

Đọc số từ chứng từ Việt Nam: "1.234.567", "1.234.567,50", "1,234,567.50", "(1.000)", "25.000.000 đ".
Chuỗi có thể hiểu hai cách (VD "1.234" với ngoại tệ) trả về AMBIGUOUS — không tự chọn.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

SCALES = {"VND": 0, "JPY": 0, "KRW": 0, "USD": 2, "EUR": 2, "GBP": 2, "CNY": 2, "SGD": 2}
DEFAULT_SCALE = 2
ZERO = Decimal("0")
_CURRENCY_TOKENS = re.compile(r"(vnđ|vnd|đồng|đ|₫|usd|us\$|\$|eur|€)", re.I)


def scale(currency):
    return SCALES.get((currency or "VND").upper(), DEFAULT_SCALE)


def q(value, currency="VND"):
    """Làm tròn theo số lẻ của đồng tiền (ROUND_HALF_UP)."""
    d = to_decimal(value)
    return d.quantize(Decimal(1).scaleb(-scale(currency)), rounding=ROUND_HALF_UP)


def to_decimal(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not money")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # float chỉ đến từ thư viện đọc file (Excel lưu số double); repr() là biểu diễn ngắn nhất
        return Decimal(repr(value))
    if isinstance(value, str):
        return Decimal(value.strip())
    raise TypeError(f"không chuyển được {type(value).__name__} thành Decimal")


def fmt(value):
    """Chuỗi thập phân chuẩn để lưu DB (không có số mũ)."""
    if value is None:
        return None
    d = to_decimal(value)
    with localcontext() as ctx:
        ctx.prec = 60
        s = format(d.normalize() if d != 0 else Decimal(0), "f")
    return s


def D(s):
    """Đọc lại giá trị từ DB."""
    return None if s is None or s == "" else Decimal(s)


def sum_(values):
    total = ZERO
    for v in values:
        if v is not None:
            total += to_decimal(v)
    return total


@dataclass
class Parsed:
    value: Decimal | None
    status: str  # OK | AMBIGUOUS | INVALID | EMPTY
    note: str = ""


def parse_amount(raw, currency="VND"):
    """Đọc số tiền từ ô Excel/chuỗi văn bản. Không đoán khi chuỗi có hai cách hiểu."""
    if raw is None:
        return Parsed(None, "EMPTY")
    if isinstance(raw, bool):
        return Parsed(None, "INVALID", "giá trị logic")
    if isinstance(raw, (int, Decimal)):
        return Parsed(to_decimal(raw), "OK")
    if isinstance(raw, float):
        d = to_decimal(raw)
        rounded = q(d, currency)
        if abs(d - rounded) > Decimal("0.000001"):
            return Parsed(d, "OK", f"số lẻ vượt độ chính xác của {currency}")
        return Parsed(rounded if scale(currency) == 0 else d, "OK")
    s = str(raw).strip()
    if not s:
        return Parsed(None, "EMPTY")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    s = _CURRENCY_TOKENS.sub("", s).strip().replace(" ", "").replace(" ", "")
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    if s.startswith("+"):
        s = s[1:]
    if not s or not re.fullmatch(r"[0-9.,]+", s):
        return Parsed(None, "INVALID", f"không phải số: {str(raw)[:40]}")
    dots, commas = s.count("."), s.count(",")
    sc = scale(currency)
    if dots and commas:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        if s.count(dec) > 1:
            return Parsed(None, "INVALID", "nhiều dấu thập phân")
        intpart, frac = s.split(dec)
        if not _valid_grouping(intpart, thou):
            return Parsed(None, "INVALID", "nhóm hàng nghìn sai")
        num = intpart.replace(thou, "") + "." + frac
    elif dots or commas:
        sep = "." if dots else ","
        parts = s.split(sep)
        if len(parts) > 2:
            if not _valid_grouping(s, sep):
                return Parsed(None, "INVALID", "nhóm hàng nghìn sai")
            num = s.replace(sep, "")
        else:
            intpart, frac = parts
            if len(frac) == 3 and intpart and intpart != "0":
                # "1.234" / "1,234": hàng nghìn hay thập phân? Chỉ chắc chắn khi đồng tiền không có số lẻ
                if sc == 0:
                    num = intpart + frac
                else:
                    return Parsed(None, "AMBIGUOUS", f"'{raw}' có thể là {intpart}{frac} hoặc {intpart}.{frac}")
            else:
                num = intpart + "." + frac
    else:
        num = s
    try:
        d = Decimal(num)
    except InvalidOperation:
        return Parsed(None, "INVALID", f"không phải số: {str(raw)[:40]}")
    if neg:
        d = -d
    if sc == 0 and d != d.to_integral_value():
        return Parsed(d, "OK", f"{currency} không có số lẻ nhưng chứng từ ghi {raw}")
    return Parsed(d, "OK")


def _valid_grouping(s, sep):
    groups = s.split(sep)
    return bool(groups[0]) and len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])


def parse_rate(raw):
    """Thuế suất GTGT: '10%', '10', 0.1, 'KCT', 'KKKNT'. Trả về (Decimal phần trăm | None, nhãn)."""
    if raw is None:
        return None, None
    s = str(raw).strip().upper().replace(" ", "")
    if s in ("KCT", "KHONGCHIUTHUE", "KHÔNGCHỊUTHUẾ"):
        return None, "KCT"
    if s in ("KKKNT", "KHAC"):
        return None, s
    s = s.rstrip("%")
    try:
        d = Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None, "INVALID"
    if isinstance(raw, float) and d < 1 and d > 0:
        d = d * 100
    return d.normalize(), f"{fmt(d)}%"
