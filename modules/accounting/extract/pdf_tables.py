"""
Bảng trong PDF có lớp chữ (pdfplumber): dòng hàng hoá đơn và bảng sao kê/sổ, kèm toạ độ từng ô để
mở đúng vị trí trong chứng từ gốc. PDF scan (không có lớp chữ) không có bảng ở đây — xem OCR.
"""

import io

from .. import money, settings
from . import tables
from .base import EXTRACTED, Field, fold

LINE_ROLES = {
    "description": ("ten hang hoa dich vu", "ten hang hoa", "ten hang", "hang hoa dich vu", "dien giai", "noi dung", "description"),
    "unit": ("don vi tinh", "dvt", "don vi", "unit"),
    "quantity": ("so luong", "sl", "quantity", "qty"),
    "unit_price": ("don gia", "unit price", "price"),
    "amount": ("thanh tien", "thanh tien truoc thue", "amount"),
    "vat_rate": ("thue suat", "ts", "vat rate"),
}
TOTAL_ROW = ("cong tien hang", "tong cong", "cong", "tien thue", "tong tien", "thue suat")


def _role(cell):
    f = fold(cell)
    f2 = fold(str(cell or "").split("(")[0])
    for role, names in LINE_ROLES.items():
        if f in names or f2 in names or any(f.startswith(n + " ") for n in names if len(n) > 4):
            return role
    return None


def extract(data, file_name, max_pages=None):
    """Trả về list các bảng: {page, grid, cell_boxes(row→[bbox…]), bbox}."""
    import pdfplumber

    max_pages = max_pages or int(settings.get().get("max_pdf_table_pages", 50))
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pno, page in enumerate(pdf.pages[:max_pages], start=1):
            for t in page.find_tables():
                rows = t.rows
                grid = [[(c or "").strip() if isinstance(c, str) else c for c in r] for r in t.extract()]
                boxes = [[list(c) if c else None for c in r.cells] for r in rows]
                if len(grid) >= 2 and max(len(r) for r in grid) >= 2:
                    out.append({"page": pno, "grid": grid, "cell_boxes": boxes, "bbox": list(t.bbox)})
    return out


def invoice_lines(tabs, currency="VND"):
    """Tìm bảng dòng hàng (có cột số lượng + thành tiền). Trả về (lines, fields, chỉ số bảng) hoặc ([], [], None)."""
    for t in tabs:
        grid = t["grid"]
        for h in range(min(3, len(grid))):
            roles = {}
            for c, cell in enumerate(grid[h]):
                r = _role(cell)
                if r and r not in roles.values():
                    roles[c] = r
            if {"quantity", "amount"} <= set(roles.values()) and ({"description"} & set(roles.values())):
                return (*_lines(t, h, roles, currency), tabs.index(t))
    return [], [], None


def _lines(t, h, roles, currency):
    col = {r: c for c, r in roles.items()}
    lines, fields = [], []
    n = 0
    for ri in range(h + 1, len(t["grid"])):
        row = t["grid"][ri]
        cell = lambda r: row[col[r]] if r in col and col[r] < len(row) else None  # noqa: E731
        desc = cell("description")
        if not desc and cell("amount") in (None, ""):
            continue
        if fold(desc).startswith(TOTAL_ROW) and not cell("quantity"):
            continue
        n += 1
        amt = money.parse_amount(cell("amount"), currency)
        qty = money.parse_amount(cell("quantity"), "USD")
        price = money.parse_amount(cell("unit_price"), currency)
        rate, label = money.parse_rate(cell("vat_rate")) if cell("vat_rate") else (None, None)
        line = {"line_no": n, "description": desc, "unit": cell("unit"),
                "quantity": money.fmt(qty.value) if qty.status == "OK" else None,
                "unit_price": money.fmt(price.value) if price.status == "OK" else None,
                "amount": money.fmt(amt.value) if amt.status == "OK" else None,
                "vat_rate": money.fmt(rate) if rate is not None else None, "vat_label": label, "vat_amount": None, "discount": None}
        lines.append(line)
        for r in ("quantity", "unit_price", "amount"):
            if r in col and line[r] is not None:
                box = t["cell_boxes"][ri][col[r]] if ri < len(t["cell_boxes"]) and col[r] < len(t["cell_boxes"][ri]) else None
                fields.append(Field(name=f"line{n}.{r}", raw=cell(r), normalized=line[r], confidence=0.9, method="pdf_table",
                                    page=t["page"], location={"page": t["page"], "bbox": [round(x, 1) for x in box]} if box else
                                    {"page": t["page"]}, status=EXTRACTED))
    return lines, fields


def table_docs(tabs, file_name, skip_ids=()):
    """Bảng còn lại (sao kê/sổ/bảng dữ liệu) → Doc qua bộ nhận diện bảng chung, giữ toạ độ từng dòng."""
    docs = []
    for i, t in enumerate(tabs):
        if i in skip_ids:
            continue
        for d in tables.build_docs(t["grid"], f"Trang {t['page']}", file_name):
            d.data["page"] = t["page"]
            d.data["row_boxes"] = {}
            for rn in d.data.get("row_numbers") or []:
                cells = t["cell_boxes"][rn - 1] if rn - 1 < len(t["cell_boxes"]) else []
                bxs = [b for b in cells if b]
                if bxs:
                    d.data["row_boxes"][str(rn)] = [round(min(b[0] for b in bxs), 1), round(min(b[1] for b in bxs), 1),
                                                    round(max(b[2] for b in bxs), 1), round(max(b[3] for b in bxs), 1)]
            for rec in d.data.get("records") or []:
                rec["row_ref"] = f"Trang {t['page']} dòng {rec['row']}"
            for rec in d.bank_txns + d.entries:
                rec["row_ref"] = f"Trang {t['page']} dòng {rec['row']}"
            docs.append(d)
    return docs
