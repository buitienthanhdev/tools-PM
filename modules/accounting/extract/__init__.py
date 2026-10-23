"""
Chọn parser theo định dạng đã nhận diện, chạy, rồi ghi kết quả + provenance trong một giao dịch.
Kết quả được cache theo (file, parser, phiên bản parser): chạy lại task không trích xuất lại.
"""

from .. import audit, db, money, storage
from ..engine import validate
from . import office, pdf, xml_invoice
from .base import VERIFIED, ExtractError, Result

PARSERS = {
    "xml": ("xml_einvoice", xml_invoice.VERSION),
    "pdf": ("pdf", pdf.VERSION),
    "xlsx": ("excel_openpyxl", office.VERSION),
    "xlsm": ("excel_openpyxl", office.VERSION),
    "csv": ("delimited", office.VERSION),
    "tsv": ("delimited", office.VERSION),
    "docx": ("docx", office.VERSION),
    "json": ("json", office.VERSION),
    "txt": ("text", office.VERSION),
    "png": ("image_ocr", office.VERSION),
    "jpeg": ("image_ocr", office.VERSION),
    "tiff": ("image_ocr", office.VERSION),
}


def run(file_row):
    kind = file_row["kind"]
    path = storage.abspath(file_row["storage_path"])
    name = file_row["original_name"]
    if kind not in PARSERS:
        return Result("none", "0", status="UNSUPPORTED", error={"code": "unsupported", "message": f"Không trích xuất {kind}"})
    try:
        if kind in ("xlsx", "xlsm"):
            return office.excel(path, name)
        data = path.read_bytes()
        if kind == "xml":
            root = xml_invoice.parse_bytes(data)
            if xml_invoice.is_einvoice(root):
                return xml_invoice.extract(data, name)
            r = office.textfile(data, name)
            r.parser = "xml_text"
            return r
        if kind == "pdf":
            return pdf.extract(data, name)
        if kind in ("csv", "tsv"):
            return office.delimited(data, name, kind)
        if kind == "docx":
            return office.docx(data, name)
        if kind == "json":
            return office.jsonfile(data, name)
        if kind == "txt":
            return office.textfile(data, name)
        return office.image(data, name)
    except ExtractError as e:
        p, v = PARSERS[kind]
        return Result(p, v, status="FAILED", error={"code": e.code, "message": str(e)})


def cached(org_id, file_id):
    return db.one(
        "SELECT * FROM extractions WHERE org_id=? AND file_id=? AND status IN ('OK','PARTIAL') ORDER BY created_at DESC LIMIT 1",
        (org_id, file_id),
    )


def ensure(org_id, file_id, org_tax_id=None, actor="agent"):
    """Trích xuất (nếu chưa có) và trả về bản ghi extraction."""
    f = db.one("SELECT * FROM files WHERE id=? AND org_id=?", (file_id, org_id))
    if not f:
        raise ExtractError("not_found", "Không có file")
    existing = cached(org_id, file_id)
    parser = PARSERS.get(f["kind"])
    if existing and parser and (existing["parser"], existing["parser_version"]) in (parser, ("xml_text", parser[1])):
        return existing
    if not storage.verify(f["storage_path"], f["sha256"]):
        raise ExtractError("integrity", "Bản gốc không khớp SHA-256 — dừng xử lý file này")
    res = run(f)
    return persist(org_id, f, res, org_tax_id, actor)


def persist(org_id, f, res, org_tax_id=None, actor="agent"):
    ext_id = db.new_id()
    with db.tx() as c:
        dup = c.execute(
            "SELECT * FROM extractions WHERE file_id=? AND parser=? AND parser_version=?",
            (f["id"], res.parser, res.version),
        ).fetchone()
        if dup and dup["status"] in ("OK", "PARTIAL"):
            return dict(dup)
        if dup:  # lần trước lỗi → thay bằng lần chạy mới (không có dữ liệu con)
            c.execute("UPDATE extractions SET parser_version=parser_version||'-failed-'||? WHERE id=?",
                      (ext_id[:8], dup["id"]))
        row = {
            "id": ext_id, "org_id": org_id, "file_id": f["id"], "parser": res.parser, "parser_version": res.version,
            "status": res.status, "error_json": db.dumps(res.error) if res.error else None,
            "stats_json": db.dumps({**res.stats, "model_id": res.model_id}), "text_content": res.text[:1_000_000],
            "created_at": db.now(),
        }
        if res.status in ("OK", "PARTIAL"):
            old = [r[0] for r in c.execute(
                "SELECT id FROM extractions WHERE file_id=? AND status IN ('OK','PARTIAL')", (f["id"],))]
            if old:
                c.execute(f"UPDATE extractions SET status='SUPERSEDED' WHERE id IN ({','.join('?' for _ in old)})", old)
                audit.log(c, org_id, actor, "extract.supersede", "file", f["id"], superseded=old,
                          new_parser=f"{res.parser}@{res.version}")
        db.insert(c, "extractions", row)
        for doc in res.docs:
            _persist_doc(c, org_id, f, ext_id, res, doc, org_tax_id)
        audit.log(c, org_id, actor, "extract", "file", f["id"], parser=res.parser, version=res.version,
                  status=res.status, docs=len(res.docs), model_id=res.model_id, error=res.error)
    return row


def _persist_doc(c, org_id, f, ext_id, res, doc, org_tax_id):
    doc_id = db.new_id()
    status = doc.status
    inv_status, issues = None, []
    if doc.doc_type == "invoice":
        structured = doc.invoice.get("source_format") == "xml"
        inv_status, issues = validate.invoice(doc.invoice, doc.lines, structured)
        if doc.status == "NEEDS_REVIEW" and inv_status in ("VERIFIED", "VALID_EXTRACTED"):
            inv_status = "NEEDS_REVIEW"  # OCR: số học khớp vẫn chưa đủ để tin
        status = inv_status
    data = dict(doc.data)
    data["warnings"] = doc.warnings
    if doc.invoice:
        data["invoice"] = doc.invoice
    db.insert(c, "documents", {
        "id": doc_id, "org_id": org_id, "file_id": f["id"], "extraction_id": ext_id, "doc_type": doc.doc_type,
        "title": doc.title[:300], "data_json": db.dumps(data), "status": status, "created_at": db.now(),
    })
    issue_fields = {i["field"] for i in issues if i["severity"] in ("conflict",)}
    for fld in doc.fields:
        vstatus = fld.status
        if inv_status == "VERIFIED" and fld.status == "EXTRACTED":
            vstatus = VERIFIED
        if fld.name in issue_fields:
            vstatus = "CONFLICTED"
        db.insert(c, "fields", {
            "id": db.new_id(), "org_id": org_id, "document_id": doc_id, "file_id": f["id"],
            "source_file_hash": f["sha256"], "field_name": fld.name[:120],
            "extracted_value": None if fld.raw is None else str(fld.raw)[:2000],
            "normalized_value": None if fld.normalized is None else str(fld.normalized)[:2000],
            "confidence": float(fld.confidence), "extraction_method": fld.method,
            "parser_version": f"{res.parser}@{res.version}", "model_id": res.model_id,
            "source_page": fld.page, "sheet_name": fld.sheet, "cell_reference": fld.cell,
            "source_location_json": db.dumps(fld.location) if fld.location else None,
            "validation_status": vstatus, "extracted_at": db.now(),
        })
    if doc.doc_type == "invoice":
        inv = doc.invoice
        inv_id = db.new_id()
        db.insert(c, "invoices", {
            "id": inv_id, "org_id": org_id, "document_id": doc_id, "file_id": f["id"],
            "source_format": inv.get("source_format"), "form_no": inv.get("form_no"), "series": inv.get("series"),
            "number": inv.get("number"), "issue_date": inv.get("issue_date"),
            "seller_tax_id": inv.get("seller_tax_id"), "seller_name": inv.get("seller_name"),
            "buyer_tax_id": inv.get("buyer_tax_id"), "buyer_name": inv.get("buyer_name"),
            "currency": inv.get("currency"), "fx_rate": inv.get("fx_rate"),
            "subtotal": inv.get("subtotal"), "vat_amount": inv.get("vat_amount"), "total": inv.get("total"),
            "invoice_kind": inv.get("invoice_kind") or "original", "related_invoice": inv.get("related_invoice"),
            "authority_code": inv.get("authority_code"), "business_key": validate.business_key(inv),
            "direction": validate.direction(inv, org_tax_id), "status": inv_status,
            "issues_json": db.dumps(issues), "created_at": db.now(),
        })
        for ln in doc.lines:
            db.insert(c, "invoice_lines", {
                "id": db.new_id(), "org_id": org_id, "invoice_id": inv_id, "line_no": ln["line_no"],
                "description": ln.get("description"), "unit": ln.get("unit"), "quantity": ln.get("quantity"),
                "unit_price": ln.get("unit_price"), "amount": ln.get("amount"), "vat_rate": ln.get("vat_rate"),
                "vat_amount": ln.get("vat_amount"),
            })
    for t in doc.bank_txns:
        db.insert(c, "bank_transactions", {
            "id": db.new_id(), "org_id": org_id, "document_id": doc_id, "file_id": f["id"],
            "account_no": None, "txn_date": t["date"], "description": t["description"], "reference": t["reference"],
            "debit": money.fmt(-money.D(t["amount"])) if money.D(t["amount"]) < 0 else "0",
            "credit": t["amount"] if money.D(t["amount"]) > 0 else "0",
            "amount": t["amount"], "currency": t["currency"], "balance": t["balance"],
            "counterparty": t["counterparty"], "row_ref": t["row_ref"],
        })
    for e in doc.entries:
        db.insert(c, "imported_entries", {
            "id": db.new_id(), "org_id": org_id, "document_id": doc_id, "file_id": f["id"],
            "entry_date": e["date"], "doc_no": e["reference"], "description": e["description"],
            "account": e["account"], "amount": e["amount"], "counterparty": e["counterparty"], "row_ref": e["row_ref"],
        })
