"""
Nhận diện bảng từ lưới ô (Excel/CSV): tìm dòng tiêu đề, ánh xạ cột theo từ đồng nghĩa,
phân loại bảng (sao kê ngân hàng / sổ kế toán / danh sách hoá đơn / bảng dữ liệu) và chuẩn hoá dòng.

Quy tắc chiều tiền (không đoán):
- Sao kê ngân hàng: "ghi có / credit / nộp vào" = tiền vào; "ghi nợ / debit / rút ra" = tiền ra.
- Sổ quỹ / sổ tiền gửi: "thu" = vào, "chi" = ra; sổ TK 111/112 cột "Nợ" = vào, "Có" = ra.
- Bảng chỉ có cột "Nợ/Có" mà không rõ là sao kê hay sổ → không xác định chiều, đưa vào kiểm duyệt.
"""

from .. import money
from .base import (
    CONFLICTED,
    EXTRACTED,
    NEEDS_REVIEW,
    Doc,
    col_letter,
    date_order,
    fold,
    norm_tax_id,
    parse_date,
)

SYN = {
    "date": ["ngay", "ngay giao dich", "ngay gd", "ngay hach toan", "ngay chung tu", "ngay ct", "ngay lap",
             "date", "transaction date", "posting date", "txn date", "ngay hoa don", "value date", "ngay hieu luc"],
    "description": ["dien giai", "noi dung", "mo ta", "chi tiet", "description", "details", "narrative",
                    "noi dung giao dich", "noi dung thanh toan", "ten hang hoa", "ten hang hoa dich vu", "memo"],
    "reference": ["so tham chieu", "ma giao dich", "so gd", "reference", "ref", "ma gd", "transaction id",
                  "so but toan", "so giao dich", "ref no", "trace"],
    "doc_no": ["so chung tu", "so ct", "chung tu", "so phieu", "doc no", "voucher", "voucher no"],
    "invoice_no": ["so hoa don", "so hd", "invoice no", "invoice number", "so hddt"],
    "invoice_series": ["ky hieu", "ky hieu hoa don", "serial", "ky hieu hd"],
    "tax_id": ["mst", "ma so thue", "tax code", "tax id", "ma so thue nguoi ban", "mst nguoi ban"],
    "bank_debit": ["ghi no", "so tien ghi no", "rut ra", "debit", "withdrawal", "withdrawals", "debit amount",
                   "so tien rut", "tien ra"],
    "bank_credit": ["ghi co", "so tien ghi co", "nop vao", "credit", "deposit", "deposits", "credit amount",
                    "so tien nop", "tien vao"],
    "led_debit": ["no", "phat sinh no", "ps no", "so tien no"],
    "led_credit": ["co", "phat sinh co", "ps co", "so tien co"],
    "inflow": ["thu", "tien thu", "so tien thu", "thu vao"],
    "outflow": ["chi", "tien chi", "so tien chi", "chi ra"],
    "amount": ["so tien", "amount", "gia tri", "thanh tien", "tong tien", "tong cong", "tien",
               "tong tien thanh toan", "doanh thu", "chi phi", "value"],
    "vat": ["tien thue", "thue gtgt", "vat", "tien thue gtgt", "vat amount"],
    "subtotal": ["tien hang", "tien truoc thue", "cong tien hang", "gia tri truoc thue", "amount before vat"],
    "balance": ["so du", "balance", "so du cuoi", "running balance", "ton quy"],
    "counterparty": ["doi tuong", "khach hang", "nha cung cap", "ben nhan", "nguoi nhan", "ten don vi",
                     "counterparty", "partner", "doi tac", "ten khach hang", "ten ncc", "nguoi ban", "nguoi mua",
                     "ten nguoi ban", "ten nguoi mua", "ben chuyen", "beneficiary", "payee", "ten doi ung",
                     "doi ung", "ten tai khoan doi ung", "ten nguoi huong", "nguoi huong", "ten nguoi chuyen"],
    "account": ["tai khoan", "tk", "so tk", "account", "tk doi ung", "tai khoan doi ung"],
    "category": ["loai", "phan loai", "khoan muc", "category", "hang muc", "phong ban", "bo phan", "department",
                 "nhom", "loai chi phi", "loai doanh thu"],
    "currency": ["loai tien", "tien te", "currency", "ccy", "dvt tien"],
    "month": ["thang", "ky", "month", "period"],
    "quantity": ["so luong", "sl", "qty", "quantity"],
    "unit_price": ["don gia", "unit price", "price"],
}
_LOOKUP = {}
for _k, _vs in SYN.items():
    for _v in _vs:
        _LOOKUP.setdefault(_v, _k)

BANK_HINTS = ("sao ke", "statement", "ngan hang", "bank", "so phu", "account statement", "vietcombank",
              "techcombank", "bidv", "vietinbank", "agribank", "mb bank", "acb", "tpbank", "vpbank", "sacombank")
LEDGER_HINTS = ("so quy", "so tien gui", "so cai", "nhat ky", "so ke toan", "ledger", "cash book", "so chi tiet")


def match_header(cell):
    f = fold(cell)
    if not f:
        return None
    if f in _LOOKUP:
        return _LOOKUP[f]
    # "Số tiền ghi nợ (VND)" → bỏ phần trong ngoặc / đơn vị
    f2 = fold(str(cell).split("(")[0])
    if f2 in _LOOKUP:
        return _LOOKUP[f2]
    return None


def find_header(grid, scan_rows=30):
    """Trả về (chỉ số dòng tiêu đề, {cột: vai trò}) hoặc (None, {})."""
    best = (None, {}, 0)
    for r, row in enumerate(grid[:scan_rows]):
        roles = {}
        for c, v in enumerate(row):
            role = match_header(v)
            if role and role not in roles.values():
                roles[c] = role
        score = len(roles)
        if score >= 2 and score > best[2]:
            best = (r, roles, score)
    return best[0], best[1]


def _context_text(grid, header_row, sheet_name, file_name):
    rows = grid[:header_row] if header_row else []
    words = " ".join(str(v) for row in rows for v in row if v not in (None, ""))
    return fold(f"{file_name} {sheet_name} {words}")


def classify(roles, context):
    vals = set(roles.values())
    bankish = any(h in context for h in BANK_HINTS)
    ledgerish = any(h in context for h in LEDGER_HINTS)
    has_date = "date" in vals
    if {"invoice_no"} <= vals and ({"amount", "subtotal", "tax_id", "vat"} & vals):
        return "invoice_list", None
    if has_date and ({"bank_debit", "bank_credit"} & vals):
        return "bank_statement", "bank"
    if has_date and ({"inflow", "outflow"} & vals):
        return "ledger", "cashbook"
    if has_date and ({"led_debit", "led_credit"} & vals):
        if bankish and not ledgerish:
            return "bank_statement", "bank_plain"  # "Nợ/Có" trong sao kê = góc nhìn ngân hàng
        if ledgerish:
            return "ledger", "ledger_dc"
        return "table", "ambiguous_dc"
    if has_date and "amount" in vals and ("balance" in vals or bankish) and not ledgerish:
        return "bank_statement", "signed"
    if has_date and "amount" in vals and ledgerish:
        return "ledger", "signed"
    return "table", None


def find_generic_header(grid, scan_rows=30):
    """Bảng không có tiêu đề kế toán (danh sách, bảng kê): dòng đầu tiên có ≥3 ô, phần lớn là chữ,
    và các dòng ngay sau có độ rộng tương đương."""
    for r, row in enumerate(grid[:scan_rows]):
        cells = [v for v in row if v not in (None, "")]
        if len(cells) < 3 or sum(isinstance(v, str) for v in cells) / len(cells) < 0.7:
            continue
        nxt = [sum(1 for v in x if v not in (None, "")) for x in grid[r + 1:r + 6]]
        if nxt and max(nxt) >= max(2, len(cells) // 2):
            return r
    return None


def _cell_ref(sheet, r0, c0):
    return f"{col_letter(c0)}{r0 + 1}"


def build_docs(grid, sheet_name, file_name, currency="VND"):
    """grid: danh sách dòng (list giá trị). Trả về list Doc (thường 1) cho bảng phát hiện được."""
    header_row, roles = find_header(grid)
    generic = header_row is None
    if generic:
        header_row = find_generic_header(grid)
        if header_row is None:
            return []
    context = _context_text(grid, header_row, sheet_name, file_name)
    kind, semantics = classify(roles, context)
    header = [str(v).strip() if v is not None else "" for v in grid[header_row]]
    width = sum(1 for h in header if h)
    min_cells = max(2, (width + 1) // 2)
    body, skipped = [], []
    for r in range(header_row + 1, len(grid)):
        row = grid[r]
        filled = sum(1 for v in row if v not in (None, ""))
        if not filled:
            continue
        first = fold(row[0]) if row else ""
        if first.startswith(("tong cong", "cong phat sinh", "total", "so du dau", "so du cuoi", "cong")):
            skipped.append(r + 1)
            continue  # dòng tổng/số dư của báo cáo nguồn, không phải giao dịch
        if generic and filled < min_cells:
            skipped.append(r + 1)  # chữ ký, ngày tháng, ghi chú cuối trang — không phải dòng dữ liệu
            continue
        body.append((r, row))
    colmap = {role: c for c, role in roles.items()}
    title = f"{file_name} — {sheet_name}" if sheet_name else file_name
    doc = Doc(doc_type=kind if kind != "invoice_list" else "table", title=title)
    doc.data = {
        "sheet": sheet_name, "header_row": header_row + 1, "header": header,
        "roles": {header[c] if c < len(header) else str(c): role for c, role in roles.items()},
        "columns": {role: col_letter(c) for c, role in roles.items()},
        "col_index": {role: c for c, role in roles.items()},
        "context": context[:300],
        "semantics": semantics, "table_kind": "generic" if generic else kind,
        "skipped_rows": skipped[:200],
    }
    date_vals = [row[colmap["date"]] for _, row in body if "date" in colmap and colmap["date"] < len(row)]
    order = date_order(date_vals)
    if order == "conflicted":
        doc.warnings.append("Cột ngày có cả dạng dd/mm và mm/dd — ngày được đánh dấu CONFLICTED")
    day_first = order != "month_first"
    if semantics == "ambiguous_dc":
        doc.status = NEEDS_REVIEW
        doc.warnings.append("Bảng có cột Nợ/Có nhưng không xác định được là sao kê ngân hàng hay sổ kế toán — chưa xác định chiều tiền")

    def get(row, role):
        c = colmap.get(role)
        return row[c] if c is not None and c < len(row) else None

    issues = 0
    rows_out = []
    for r, row in body:
        ref = f"{sheet_name}!A{r + 1}:{col_letter(max(len(row) - 1, 0))}{r + 1}" if sheet_name else f"row {r + 1}"
        d_iso, d_note = parse_date(get(row, "date"), day_first=day_first) if "date" in colmap else (None, "none")
        if order == "conflicted":
            d_iso, d_note = None, "conflicted"
        rec = {
            "row": r + 1, "row_ref": ref, "date": d_iso, "date_note": d_note,
            "description": _s(get(row, "description")), "reference": _s(get(row, "reference")) or _s(get(row, "doc_no")),
            "counterparty": _s(get(row, "counterparty")), "account": _s(get(row, "account")),
            "category": _s(get(row, "category")), "currency": _s(get(row, "currency")) or currency,
        }
        amount, problems = _signed_amount(row, colmap, semantics, rec["currency"])
        rec["amount"] = money.fmt(amount) if amount is not None else None
        rec["problems"] = problems
        if problems or (("date" in colmap) and d_iso is None):
            issues += 1
        bal = money.parse_amount(get(row, "balance"), rec["currency"]) if "balance" in colmap else None
        rec["balance"] = money.fmt(bal.value) if bal and bal.status == "OK" else None
        rec["tax_id"] = norm_tax_id(get(row, "tax_id"))
        rec["cells"] = {role: _cell_ref(sheet_name, r, c) for role, c in colmap.items()}
        rows_out.append(rec)
        if kind == "bank_statement" and amount is not None:
            doc.bank_txns.append(rec)
        elif kind == "ledger" and amount is not None:
            doc.entries.append(rec)
    doc.data["row_count"] = len(rows_out)
    doc.data["rows_with_issues"] = issues
    # Bảng dữ liệu chung: giữ toàn bộ giá trị để tổng hợp/hợp nhất
    doc.data["rows"] = [[_jsonable(v) for v in row] for _, row in body]
    doc.data["row_numbers"] = [r + 1 for r, _ in body]
    doc.data["records"] = rows_out if kind in ("bank_statement", "ledger") else []
    if issues and doc.status == EXTRACTED:
        doc.warnings.append(f"{issues} dòng thiếu ngày/số tiền hoặc số tiền không đọc được")
    if order == "conflicted":
        doc.status = CONFLICTED
    return [doc]


def _signed_amount(row, colmap, semantics, currency):
    problems = []

    def amt(role):
        c = colmap.get(role)
        if c is None or c >= len(row):
            return None
        p = money.parse_amount(row[c], currency)
        if p.status in ("AMBIGUOUS", "INVALID"):
            problems.append(f"{role}: {p.note}")
            return None
        return p.value

    if semantics == "bank" or semantics == "bank_plain":
        dr = amt("bank_debit") if "bank_debit" in colmap else amt("led_debit")
        cr = amt("bank_credit") if "bank_credit" in colmap else amt("led_credit")
    elif semantics == "cashbook":
        cr, dr = amt("inflow"), amt("outflow")
    elif semantics == "ledger_dc":
        cr, dr = amt("led_debit"), amt("led_credit")  # sổ TK tiền: Nợ = tăng (vào), Có = giảm (ra)
    elif semantics == "signed":
        v = amt("amount")
        return v, problems
    else:
        return None, problems
    if dr is None and cr is None:
        return None, problems
    if dr and cr:
        problems.append("dòng có cả hai chiều tiền")
    return (cr or money.ZERO) - (dr or money.ZERO), problems


def _s(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _jsonable(v):
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10] if isinstance(v, date) and not isinstance(v, datetime) else v.isoformat()
    if isinstance(v, Decimal):
        return money.fmt(v)
    # float giữ nguyên: đó chính là giá trị double Excel lưu; nơi tính tiền đổi qua money.parse_amount
    return v
