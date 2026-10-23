"""
Trích xuất hoá đơn từ văn bản (PDF có lớp chữ, DOCX, kết quả OCR) theo nhãn tiếng Việt/Anh.
Chỉ lấy giá trị đứng sau nhãn nhận diện được; thiếu nhãn → trường UNKNOWN, không suy đoán.
"""

import re

from .. import money
from .base import EXTRACTED, NEEDS_REVIEW, UNKNOWN, Doc, Field, fold, norm_tax_id, parse_date

NUM = r"[-(]?\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,4})?\)?|[-(]?\d+(?:[.,]\d{1,4})?\)?"

INVOICE_MARKERS = ("hoa don gia tri gia tang", "hoa don ban hang", "vat invoice", "hoa don dien tu", "invoice")
SELLER_LABELS = ("don vi ban hang", "nguoi ban", "ten nguoi ban", "seller", "don vi ban")
BUYER_PERSON_LABELS = ("ho ten nguoi mua", "nguoi mua hang", "ten nguoi mua", "buyer")
BUYER_LABELS = ("don vi mua hang", "ten don vi mua", "nguoi mua", "ten don vi", "company name")
TOTAL_LABELS = [
    ("total", ("tong tien thanh toan", "tong cong tien thanh toan", "total payment", "tong thanh toan",
               "tong cong thanh toan")),
    ("vat_amount", ("tien thue gtgt", "tien thue", "vat amount", "thue gtgt")),
    ("subtotal", ("cong tien hang", "tong tien hang", "total amount excl", "tien hang chua thue", "cong tien hang hoa")),
]


def looks_like_invoice(text):
    f = fold(text[:5000])
    return any(m in f for m in INVOICE_MARKERS) and ("ma so thue" in f or "tax code" in f)


def _value_after_colon(raw):
    if ":" in raw:
        return raw.split(":", 1)[1].strip()
    return None


def _last_number(raw):
    found = re.findall(NUM, raw)
    return found[-1].strip() if found else None


def extract(pages, file_name, method, locate=None, currency="VND", base_conf=0.9):
    """
    pages: [(số trang, [(dòng văn bản, độ tin cậy dòng, bbox|None)])]
    locate(page, text) → bbox: tìm vị trí giá trị trên trang (PDF có lớp chữ).
    """
    fields = []
    inv = {
        "source_format": method, "form_no": None, "series": None, "number": None, "issue_date": None,
        "currency": currency, "fx_rate": None, "seller_name": None, "seller_tax_id": None, "buyer_name": None,
        "buyer_tax_id": None, "buyer_person": None, "subtotal": None, "vat_amount": None, "total": None, "authority_code": None,
        "invoice_kind": "original", "related_invoice": None, "vat_groups": [], "vat_rate_text": None,
    }
    section = None
    ocr = method.startswith("ocr")

    def put(key, raw, norm, page, line_conf, bbox):
        if norm is None or inv.get(key) not in (None, "", []):
            return
        inv[key] = norm
        loc = {"page": page}
        box = bbox or (locate(page, str(raw)) if locate and raw else None)
        if box:
            loc["bbox"] = [round(float(x), 1) for x in box]
        conf = round(base_conf * (line_conf if line_conf is not None else 1.0), 3)
        fields.append(Field(name=key, raw=raw, normalized=norm, confidence=conf, method=method, page=page,
                            location=loc, status=NEEDS_REVIEW if ocr else EXTRACTED))

    for page, lines in pages:
        for raw, conf, bbox in lines:
            f = fold(raw)
            if not f:
                continue
            if any(f.startswith(lbl) for lbl in SELLER_LABELS):
                section = "seller"
                v = _value_after_colon(raw)
                if v:
                    put("seller_name", v, v, page, conf, bbox)
                continue
            if any(f.startswith(lbl) for lbl in BUYER_PERSON_LABELS):
                section = "buyer"
                v = _value_after_colon(raw)
                if v:
                    put("buyer_person", v, v, page, conf, bbox)
                continue
            if any(f.startswith(lbl) for lbl in BUYER_LABELS) and (section == "buyer" or not f.startswith(("ten don vi", "company"))):
                section = "buyer"
                v = _value_after_colon(raw)
                if v and not re.fullmatch(r"[\d\s.-]+", v):
                    put("buyer_name", v, v, page, conf, bbox)
                continue
            if f.startswith(("ma so thue", "mst", "tax code")):
                v = _value_after_colon(raw) or raw
                tid = norm_tax_id(re.sub(r"\(.*?\)", "", v))
                if tid and len(tid.replace("-", "")) in (10, 13):
                    put("seller_tax_id" if section != "buyer" else "buyer_tax_id", v, tid, page, conf, bbox)
                continue
            if f.startswith(("ky hieu", "serial")) and "mau so" not in f:
                v = _value_after_colon(raw)
                if v:
                    v = v.split()[0].strip()
                    put("series", v, v.upper(), page, conf, bbox)
                continue
            if f.startswith(("mau so", "ky hieu mau so", "form")):
                v = _value_after_colon(raw)
                if v:
                    put("form_no", v, v.split()[0], page, conf, bbox)
                continue
            if re.match(r"^(so|no)( hoa don| no)?\b", f) and not f.startswith(("so tai khoan", "so tien", "so luong")):
                v = _value_after_colon(raw)
                m = re.search(r"\d{1,8}", v or "")
                if m:
                    put("number", m.group(0), m.group(0), page, conf, bbox)
                continue
            if f.startswith(("ngay", "date")) and inv["issue_date"] is None:
                iso, note = parse_date(raw)
                if iso:
                    put("issue_date", raw.strip(), iso, page, conf, bbox)
                continue
            if f.startswith(("thue suat", "vat rate")):
                m = re.search(r"(\d{1,2})\s*%", raw)
                if m:
                    put("vat_rate_text", m.group(0), m.group(1), page, conf, bbox)
                continue
            if f.startswith(("ma cua co quan thue", "ma cqt")):
                v = _value_after_colon(raw)
                if v:
                    put("authority_code", v, v, page, conf, bbox)
                continue
            for key, labels in TOTAL_LABELS:
                if any(f.startswith(lbl) for lbl in labels):
                    num = _last_number(raw.split(":", 1)[-1])
                    if num:
                        p = money.parse_amount(num, currency)
                        if p.status == "OK":
                            put(key, num, money.fmt(p.value), page, conf, bbox)
                        else:
                            fields.append(Field(name=key, raw=num, normalized=None, confidence=0.0, method=method,
                                                page=page, location={"page": page, "note": p.note}, status=UNKNOWN))
                    break

    # Ký hiệu hiển thị dạng "1C26TAA" = ký hiệu mẫu số (1 chữ số) + ký hiệu hoá đơn (6 ký tự)
    s = inv["series"]
    if s and not inv["form_no"] and re.fullmatch(r"[1-6][CK]\d{2}[A-Z]{3}", s):
        inv["form_no"], inv["series"] = s[0], s[1:]
        fields.append(Field(name="form_no", raw=s, normalized=s[0], confidence=0.9, method=f"{method}+split_symbol",
                            location={"note": "tách từ ký hiệu hiển thị"}, status=EXTRACTED))
    if inv["vat_rate_text"] and inv["subtotal"]:
        inv["vat_groups"] = [{"rate": inv["vat_rate_text"], "label": f"{inv['vat_rate_text']}%",
                              "taxable": inv["subtotal"], "vat": inv["vat_amount"]}]
    found = sum(1 for k in ("series", "number", "issue_date", "seller_tax_id", "total") if inv[k])
    if found < 2:
        return None
    title = f"Hoá đơn {inv.get('series') or ''} số {inv.get('number') or '?'} — {inv.get('seller_name') or 'không rõ người bán'}"
    doc = Doc(doc_type="invoice", title=title, invoice=inv, fields=fields)
    doc.data = {"file_name": file_name, "format": method, "lines_extracted": False}
    doc.warnings.append("Hoá đơn đọc từ văn bản: không trích xuất từng dòng hàng hoá")
    if ocr:
        doc.status = NEEDS_REVIEW
        doc.warnings.append("Dữ liệu từ OCR — cần kiểm duyệt trước khi sử dụng")
    return doc
