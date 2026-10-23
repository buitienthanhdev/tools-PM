"""
Kiểm tra hoá đơn bằng phép tính xác định (Decimal). Mỗi vấn đề gắn mã quy tắc trong engine/rules.py.

Trạng thái:
- VERIFIED: nguồn có cấu trúc (XML), đủ trường bắt buộc, mọi phép cộng/thuế khớp.
- VALID_EXTRACTED: nguồn văn bản (PDF/DOCX), các phép tính kiểm được đều khớp — vẫn chưa phải VERIFIED.
- NEEDS_REVIEW / NEEDS_EVIDENCE / CONFLICTED: có vấn đề, phải có người xem.
"""

from decimal import Decimal

from .. import money
from ..extract.base import fold, norm_tax_id

REQUIRED = ("form_no", "series", "number", "issue_date", "seller_name", "seller_tax_id", "total")
STANDARD_RATES = {Decimal("0"), Decimal("5"), Decimal("10")}
REDUCED_RATES = {Decimal("8")}


def _d(v):
    return money.D(v) if isinstance(v, str) else (money.to_decimal(v) if v is not None else None)


def _issue(rule, severity, field, message, expected=None, actual=None):
    return {"rule_id": rule, "severity": severity, "field": field, "message": message,
            "expected": money.fmt(expected) if isinstance(expected, Decimal) else expected,
            "actual": money.fmt(actual) if isinstance(actual, Decimal) else actual}


def business_key(inv):
    parts = [norm_tax_id(inv.get("seller_tax_id")), (inv.get("form_no") or "").strip(),
             (inv.get("series") or "").strip().upper(), (inv.get("number") or "").strip().lstrip("0")]
    return "|".join(parts) if all(parts) else None


def direction(inv, org_tax_id):
    t = norm_tax_id(org_tax_id)
    if not t:
        return "unknown"
    if norm_tax_id(inv.get("seller_tax_id")) == t:
        return "sale"
    if norm_tax_id(inv.get("buyer_tax_id")) == t:
        return "purchase"
    return "unrelated"


def invoice(inv, lines, structured):
    cur = (inv.get("currency") or "VND").upper()
    unit = Decimal(1).scaleb(-money.scale(cur))
    issues = []
    for f in REQUIRED:
        if not inv.get(f):
            issues.append(_issue("R-INV-REQUIRED", "evidence", f, f"Thiếu trường bắt buộc: {f}"))

    sub, vat, total = _d(inv.get("subtotal")), _d(inv.get("vat_amount")), _d(inv.get("total"))

    if lines:
        line_sum = money.ZERO
        for ln in lines:
            q, p, a = _d(ln.get("quantity")), _d(ln.get("unit_price")), _d(ln.get("amount"))
            nature = str(ln.get("nature") or "1")
            sign = -1 if nature == "3" else 1  # TChat=3: chiết khấu thương mại → trừ
            if a is not None and nature != "4":  # TChat=4: dòng ghi chú/diễn giải
                line_sum += sign * a
            if q is not None and p is not None and a is not None and not ln.get("discount"):
                if abs(q * p - a) > unit:
                    issues.append(_issue("R-VAT-ARITH", "review", f"line{ln['line_no']}.amount",
                                         f"Dòng {ln['line_no']}: số lượng × đơn giá ≠ thành tiền", q * p, a))
        if sub is not None and abs(line_sum - sub) > unit:
            issues.append(_issue("R-VAT-ARITH", "conflict", "subtotal",
                                 "Tổng thành tiền các dòng ≠ cộng tiền hàng", line_sum, sub))

    groups = inv.get("vat_groups") or []
    vat_from_groups = money.ZERO
    for g in groups:
        rate, taxable, gvat = _d(g.get("rate")), _d(g.get("taxable")), _d(g.get("vat"))
        if gvat is not None:
            vat_from_groups += gvat
        if rate is None:
            continue
        if rate in REDUCED_RATES:
            issues.append(_issue("R-VAT-RATES", "review", "vat_rate",
                                 f"Thuế suất {money.fmt(rate)}% là mức giảm có thời hạn — cần xác nhận kỳ áp dụng"))
        elif rate not in STANDARD_RATES:
            issues.append(_issue("R-VAT-RATES", "conflict", "vat_rate", f"Thuế suất {money.fmt(rate)}% không hợp lệ"))
        if taxable is not None and gvat is not None:
            expected = money.q(taxable * rate / 100, cur)
            n_lines = max(1, sum(1 for ln in lines if ln.get("vat_rate") == g.get("rate")))
            if abs(expected - gvat) > unit * n_lines:
                issues.append(_issue("R-VAT-ARITH", "conflict", "vat_amount",
                                     f"Tiền thuế nhóm {g.get('label')} không khớp giá tính thuế × thuế suất",
                                     expected, gvat))
    if groups and vat is not None and any(g.get("vat") for g in groups) and abs(vat_from_groups - vat) > unit:
        issues.append(_issue("R-VAT-ARITH", "conflict", "vat_amount", "Tổng thuế các nhóm ≠ tổng tiền thuế",
                             vat_from_groups, vat))
    if sub is not None and vat is not None and total is not None:
        if abs(sub + vat - total) > unit:
            issues.append(_issue("R-VAT-ARITH", "conflict", "total", "Cộng tiền hàng + tiền thuế ≠ tổng thanh toán",
                                 sub + vat, total))
    elif total is not None and (sub is None or vat is None):
        issues.append(_issue("R-VAT-ARITH", "evidence", "vat_amount", "Không đủ dữ liệu để kiểm tra tiền thuế"))

    if cur != "VND" and not inv.get("fx_rate"):
        issues.append(_issue("R-INV-REQUIRED", "evidence", "fx_rate",
                             f"Hoá đơn {cur} không có tỷ giá — không quy đổi sang VND"))
    if inv.get("invoice_kind") in ("adjustment", "replacement") and not inv.get("related_invoice"):
        issues.append(_issue("R-INV-CORRECTION", "evidence", "related_invoice",
                             "Hoá đơn điều chỉnh/thay thế không ghi hoá đơn gốc"))
    if total is not None and total < 0 and inv.get("invoice_kind") == "original":
        issues.append(_issue("R-VAT-ARITH", "review", "total", "Tổng tiền âm trên hoá đơn gốc"))
    if fold(inv.get("seller_name")) and fold(inv.get("seller_name")) == fold(inv.get("buyer_name")):
        issues.append(_issue("R-INV-REQUIRED", "review", "buyer_name", "Người bán trùng người mua"))

    sev = {i["severity"] for i in issues}
    if "conflict" in sev:
        status = "CONFLICTED"
    elif "evidence" in sev:
        status = "NEEDS_EVIDENCE"
    elif "review" in sev:
        status = "NEEDS_REVIEW"
    else:
        status = "VERIFIED" if structured else "VALID_EXTRACTED"
    return status, issues
