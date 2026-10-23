"""
Hoá đơn điện tử XML (cấu trúc HDon/DLHDon theo NĐ 123/2020 và quy định định dạng dữ liệu của TCT).
Đọc an toàn: không resolve entity, không truy cập mạng, giới hạn kích thước (chống XXE / billion laughs).
Mỗi giá trị ghi XPath trong file gốc.
"""

from lxml import etree

from .. import money
from .base import EXTRACTED, Doc, ExtractError, Field, Result, norm_tax_id, parse_date

PARSER = "xml_einvoice"
VERSION = "1.1.0"  # 1.1.0: tổng tiền bằng chữ

_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False,
    huge_tree=False, remove_comments=True, remove_pis=True,
)


def _ln(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _child(el, *names):
    """Phần tử con theo localname (bỏ qua namespace), đi theo đường dẫn names."""
    cur = el
    for n in names:
        if cur is None:
            return None
        cur = next((c for c in cur if _ln(c) == n), None)
    return cur


def _children(el, name):
    return [] if el is None else [c for c in el if _ln(c) == name]


def _find(root, name):
    for el in root.iter():
        if _ln(el) == name:
            return el
    return None


def _xml_decimal(text):
    """Số trong XML theo kiểu xs:decimal: '25000000', '1.5', '-200'. Không chấp nhận dấu phân tách nghìn."""
    import re
    from decimal import Decimal

    if not text or not re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", text):
        return None
    return money.fmt(Decimal(text))


def parse_bytes(data):
    try:
        return etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError as e:
        raise ExtractError("bad_xml", f"XML lỗi cú pháp: {e}") from e


def is_einvoice(root):
    return _find(root, "DLHDon") is not None


def extract(data, file_name=""):
    root = parse_bytes(data)
    res = Result(PARSER, VERSION)
    hdons = [el for el in root.iter() if _ln(el) == "HDon" and _child(el, "DLHDon") is not None]
    if not hdons:
        if is_einvoice(root):
            hdons = [_find(root, "DLHDon").getparent()]
        else:
            raise ExtractError("not_einvoice", "XML không phải hoá đơn điện tử (không có DLHDon)")
    tree = root.getroottree()
    for h in hdons:
        res.docs.append(_one(h, tree, file_name))
    res.stats = {"invoices": len(res.docs)}
    return res


def _one(hdon, tree, file_name):
    dl = _child(hdon, "DLHDon")
    tt = _child(dl, "TTChung")
    nd = _child(dl, "NDHDon")
    nban, nmua = _child(nd, "NBan"), _child(nd, "NMua")
    ttoan = _child(nd, "TToan")
    fields = []

    def take(el, name, path_desc, kind="text", currency="VND"):
        if el is None:
            return None
        text = (el.text or "").strip()
        if kind == "money":
            norm = _xml_decimal(text)
        elif kind == "date":
            norm, _ = parse_date(text)
        elif kind == "tax":
            norm = norm_tax_id(text)
        else:
            norm = text or None
        fields.append(Field(
            name=name, raw=text, normalized=norm, confidence=1.0 if norm is not None else 0.0,
            method="xml_xpath", location={"xpath": tree.getpath(el), "desc": path_desc},
            status=EXTRACTED if norm is not None else "UNKNOWN",
        ))
        return norm

    currency = take(_child(tt, "DVTTe"), "currency", "TTChung/DVTTe") or "VND"
    inv = {
        "source_format": "xml",
        "invoice_name": take(_child(tt, "THDon"), "invoice_name", "TTChung/THDon"),
        "form_no": take(_child(tt, "KHMSHDon"), "form_no", "TTChung/KHMSHDon"),
        "series": take(_child(tt, "KHHDon"), "series", "TTChung/KHHDon"),
        "number": take(_child(tt, "SHDon"), "number", "TTChung/SHDon"),
        "issue_date": take(_child(tt, "NLap"), "issue_date", "TTChung/NLap", "date"),
        "currency": currency.upper(),
        "fx_rate": take(_child(tt, "TGia"), "fx_rate", "TTChung/TGia", "money", "USD"),
        "seller_name": take(_child(nban, "Ten"), "seller_name", "NBan/Ten"),
        "seller_tax_id": take(_child(nban, "MST"), "seller_tax_id", "NBan/MST", "tax"),
        "seller_address": take(_child(nban, "DChi"), "seller_address", "NBan/DChi"),
        "buyer_name": take(_child(nmua, "Ten"), "buyer_name", "NMua/Ten")
        or take(_child(nmua, "HVTNMHang"), "buyer_name", "NMua/HVTNMHang"),
        "buyer_tax_id": take(_child(nmua, "MST"), "buyer_tax_id", "NMua/MST", "tax"),
        "subtotal": take(_child(ttoan, "TgTCThue"), "subtotal", "TToan/TgTCThue", "money", currency),
        "vat_amount": take(_child(ttoan, "TgTThue"), "vat_amount", "TToan/TgTThue", "money", currency),
        "total": take(_child(ttoan, "TgTTTBSo"), "total", "TToan/TgTTTBSo", "money", currency),
        "total_in_words": take(_child(ttoan, "TgTTTBChu"), "total_in_words", "TToan/TgTTTBChu"),
        "authority_code": take(_child(hdon, "MCCQT"), "authority_code", "MCCQT"),
        "invoice_kind": "original",
        "related_invoice": None,
    }
    rel = _child(tt, "TTHDLQuan")
    if rel is not None:
        kind_code = take(_child(rel, "TCHDon"), "related_kind", "TTHDLQuan/TCHDon")
        inv["invoice_kind"] = {"1": "replacement", "2": "adjustment"}.get(kind_code or "", "related")
        parts = [take(_child(rel, n), f"related_{n}", f"TTHDLQuan/{n}") for n in ("KHMSHDCLQuan", "KHHDCLQuan", "SHDCLQuan")]
        inv["related_invoice"] = "|".join(p or "" for p in parts) if any(parts) else None
        take(_child(rel, "NLHDCLQuan"), "related_date", "TTHDLQuan/NLHDCLQuan", "date")

    lines = []
    for i, it in enumerate(_children(_child(nd, "DSHHDVu"), "HHDVu"), start=1):
        rate_el = _child(it, "TSuat")
        rate_raw = (rate_el.text or "").strip() if rate_el is not None else None
        rate, rate_label = money.parse_rate(rate_raw) if rate_raw else (None, None)
        line = {
            "line_no": int((_child(it, "STT").text or i)) if _child(it, "STT") is not None and (_child(it, "STT").text or "").strip().isdigit() else i,
            "nature": (_child(it, "TChat").text or "").strip() if _child(it, "TChat") is not None else None,
            "description": take(_child(it, "THHDVu"), f"line{i}.description", f"HHDVu[{i}]/THHDVu"),
            "unit": take(_child(it, "DVTinh"), f"line{i}.unit", f"HHDVu[{i}]/DVTinh"),
            "quantity": take(_child(it, "SLuong"), f"line{i}.quantity", f"HHDVu[{i}]/SLuong", "money", "USD"),
            "unit_price": take(_child(it, "DGia"), f"line{i}.unit_price", f"HHDVu[{i}]/DGia", "money", "USD"),
            "discount": take(_child(it, "STCKhau"), f"line{i}.discount", f"HHDVu[{i}]/STCKhau", "money", currency),
            "amount": take(_child(it, "ThTien"), f"line{i}.amount", f"HHDVu[{i}]/ThTien", "money", currency),
            "vat_rate": money.fmt(rate) if rate is not None else None,
            "vat_label": rate_label,
            "vat_amount": None,
        }
        if rate_el is not None:
            fields.append(Field(name=f"line{i}.vat_rate", raw=rate_raw, normalized=line["vat_label"],
                                confidence=1.0, method="xml_xpath",
                                location={"xpath": tree.getpath(rate_el)}))
        lines.append(line)

    groups = []
    for g in _children(_child(ttoan, "THTTLTSuat"), "LTSuat"):
        rate, label = money.parse_rate((_child(g, "TSuat").text or "").strip() if _child(g, "TSuat") is not None else None)
        groups.append({
            "rate": money.fmt(rate) if rate is not None else None, "label": label,
            "taxable": take(_child(g, "ThTien"), f"vat_group.{label}.taxable", "LTSuat/ThTien", "money", currency),
            "vat": take(_child(g, "TThue"), f"vat_group.{label}.vat", "LTSuat/TThue", "money", currency),
        })
    inv["vat_groups"] = groups
    inv["has_signature"] = _find(hdon, "DSCKS") is not None

    title = f"Hoá đơn {inv.get('series') or ''} số {inv.get('number') or '?'} — {inv.get('seller_name') or 'không rõ người bán'}"
    doc = Doc(doc_type="invoice", title=title.strip(), invoice=inv, lines=lines, fields=fields)
    doc.data = {"file_name": file_name, "format": "xml"}
    return doc
