"""
Ingestion + Document Intelligence trên golden dataset: nhận diện định dạng thật, file độc hại, ZIP,
XXE, trạng thái hoá đơn, provenance, Excel/CSV/UTF-16, workbook công thức.
pytest tests_hub/test_accounting_extract.py -q   (OCR: đặt AAAP_OCR_TEST=1)
"""

import io
import os

import pytest
from accounting_fixture import ORG_TAX, configure, ingest, new_ctx


@pytest.fixture()
def env(tmp_path):
    configure(tmp_path)
    return tmp_path


def _ingest_one(ctx, path):
    from modules.accounting.ingest import pipeline

    return pipeline.ingest_stream(ctx, io.BytesIO(path.read_bytes()), path.name)


def test_rejected_by_real_signature(env, golden, expected):
    ctx = new_ctx()
    for name, code in expected["rejected"].items():
        r = _ingest_one(ctx, golden / name)
        assert r["status"] == "rejected" and r["error"]["code"] == code, name


def test_extension_not_trusted(env, golden):
    from modules.accounting.ingest import pipeline

    ctx = new_ctx()
    data = (golden / "inv_purchase_101.xml").read_bytes()
    r = pipeline.ingest_stream(ctx, io.BytesIO(data), "hoa_don.pdf")  # đuôi sai
    assert r["status"] == "stored" and r["kind"] == "xml"


def test_size_limit(tmp_path, golden):
    configure(tmp_path, max_file_mb=1)
    from modules.accounting.ingest import pipeline

    ctx = new_ctx()
    r = pipeline.ingest_stream(ctx, io.BytesIO(b"a" * (2 * 1024 * 1024)), "big.txt")
    assert r["status"] == "rejected" and r["error"]["code"] == "too_large"


def test_duplicate_file_detected(env, golden):
    ctx = new_ctx()
    a = _ingest_one(ctx, golden / "inv_purchase_101.xml")
    b = _ingest_one(ctx, golden / "inv_purchase_101.xml")
    assert a["status"] == "stored" and b["status"] == "duplicate" and a["file_id"] == b["file_id"]


def test_zip_bomb_and_traversal(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    bomb = _ingest_one(ctx, golden / "zip_bomb.zip")
    assert bomb["children"] == [] and any("zip bomb" in w for w in bomb["warnings"])
    assert db.one("SELECT status FROM files WHERE id=?", (bomb["file_id"],))["status"] == "rejected_archive"
    trav = _ingest_one(ctx, golden / "traversal.zip")
    assert [c["name"] for c in trav["children"]] == ["inv_purchase_101.xml"]
    reasons = " ".join(trav["warnings"])
    assert "../../evil.txt" in reasons and "C:/Windows/evil2.txt" in reasons
    assert db.one("SELECT archive_path FROM files WHERE id=?", (trav["children"][0]["file_id"],))["archive_path"] == "chung_tu/inv_purchase_101.xml"


def test_nested_zip_depth_limited(env, golden):
    ctx = new_ctx()
    r = _ingest_one(ctx, golden / "nested.zip")
    level1 = next(c for c in r["children"] if c["name"] == "level1.zip")
    level2 = level1["children"][0]
    assert level2["kind"] == "zip" and level2["children"] == []
    assert any("lồng quá sâu" in w for w in level2["warnings"])


def test_xxe_not_resolved(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / "xxe_attack.xml"])
    blob = " ".join(str(v) for r in db.all_("SELECT * FROM fields WHERE org_id=?", (ctx.org_id,)) for v in r.values())
    blob += " ".join(str(v) for r in db.all_("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,)) for v in r.values())
    assert "[fonts]" not in blob.lower() and "for 16-bit app support" not in blob.lower()
    inv = db.one("SELECT status, number FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv["number"] is None and inv["status"] == "NEEDS_EVIDENCE"


def test_invoice_statuses_and_totals(env, golden, expected):
    from modules.accounting import db

    ctx = new_ctx()
    names = list(expected["invoice_status"])
    ingest(ctx, [golden / n for n in names])
    rows = db.all_("SELECT i.status, i.total, f.original_name n FROM invoices i JOIN files f ON f.id=i.file_id WHERE i.org_id=?", (ctx.org_id,))
    got = {r["n"]: r["status"] for r in rows}
    assert got == expected["invoice_status"]
    totals = {r["n"]: r["total"] for r in rows}
    for n, t in expected["invoice_totals"].items():
        assert totals[n] == t, n


def test_invoice_missing_fields_flagged(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_104_no_mst.xml"])
    inv = db.one("SELECT status, issues_json, business_key FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv["status"] == "NEEDS_EVIDENCE" and inv["business_key"] is None
    assert "R-INV-REQUIRED" in inv["issues_json"] and "seller_tax_id" in inv["issues_json"]


def test_vat_inconsistency_flagged(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_103_vat_wrong.xml"])
    inv = db.one("SELECT status, issues_json FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv["status"] == "CONFLICTED" and "R-VAT-ARITH" in inv["issues_json"]
    f = db.one("SELECT validation_status FROM fields WHERE org_id=? AND field_name='vat_amount'", (ctx.org_id,))
    assert f["validation_status"] == "CONFLICTED"


def test_reduced_vat_rate_needs_review(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_202_vat8.xml"])
    inv = db.one("SELECT status, issues_json FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv["status"] == "NEEDS_REVIEW" and "R-VAT-RATES" in inv["issues_json"]


def test_adjustment_invoice_links_original(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_adjust_101.xml", golden / "inv_adjust_noref.xml"])
    rows = {r["number"]: r for r in db.all_("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,))}
    assert rows["0000110"]["invoice_kind"] == "adjustment" and rows["0000110"]["related_invoice"] == "1|C26TAA|0000101"
    assert rows["0000111"]["status"] == "NEEDS_EVIDENCE" and "R-INV-CORRECTION" in rows["0000111"]["issues_json"]


def test_foreign_currency_needs_rate(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_usd_norate.xml", golden / "inv_usd_rate.xml"])
    rows = {r["number"]: r for r in db.all_("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,))}
    assert rows["0000301"]["status"] == "NEEDS_EVIDENCE" and rows["0000301"]["currency"] == "USD"
    assert rows["0000302"]["fx_rate"] == "25350" and rows["0000302"]["total"] == "330"


def test_provenance_xml_and_pdf(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_sale_011.xml", golden / "inv_sale_011.pdf"])
    rows = db.all_("""SELECT fl.*, f.original_name n, f.sha256 fsha FROM fields fl JOIN files f ON f.id=fl.file_id
                      WHERE fl.org_id=? AND fl.field_name='total'""", (ctx.org_id,))
    by = {r["n"]: r for r in rows}
    x, p = by["inv_sale_011.xml"], by["inv_sale_011.pdf"]
    assert x["normalized_value"] == p["normalized_value"] == "27500000"
    assert x["validation_status"] == "VERIFIED" and "TgTTTBSo" in x["source_location_json"]
    assert x["source_file_hash"] == x["fsha"] and x["parser_version"].startswith("xml_einvoice@")
    assert p["validation_status"] == "EXTRACTED" and p["source_page"] == 1 and '"bbox"' in p["source_location_json"]
    # Mọi trường đều có đủ thông tin provenance tối thiểu
    for r in db.all_("SELECT * FROM fields WHERE org_id=?", (ctx.org_id,)):
        assert r["file_id"] and r["source_file_hash"] and r["extraction_method"] and r["parser_version"] and r["extracted_at"]


def test_pdf_evidence_render(env, golden):
    import json as _json

    from modules.accounting import db, storage
    from modules.accounting.extract import pdf

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_sale_011.pdf"])
    fl = db.one("SELECT * FROM fields WHERE org_id=? AND field_name='total'", (ctx.org_id,))
    f = db.one("SELECT * FROM files WHERE id=?", (fl["file_id"],))
    png = pdf.render_page(storage.read(f["storage_path"]), 1, _json.loads(fl["source_location_json"])["bbox"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5000
    assert storage.verify(f["storage_path"], f["sha256"])  # tô vùng bằng chứng không sửa bản gốc


def test_bank_statement_and_cashbook_semantics(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "sao_ke_vcb_032026.xlsx", golden / "so_tien_gui_032026.xlsx", golden / "sao_ke_export_utf16.txt"])
    b = {r["reference"]: r for r in db.all_("SELECT * FROM bank_transactions WHERE org_id=?", (ctx.org_id,))}
    assert b["FT2606600003"]["amount"] == "-4675000"  # ghi nợ sao kê = tiền ra
    assert b["FT2607500001"]["amount"] == "27500000"
    assert b["FT2607500001"]["counterparty"] == "CTY TNHH TM BINH MINH"
    assert b["FT26092X"]["amount"] == "120000"  # TSV UTF-16
    assert "Sao ke!A" in b["FT2606600003"]["row_ref"]
    e = {r["doc_no"]: r for r in db.all_("SELECT * FROM imported_entries WHERE org_id=?", (ctx.org_id,))}
    assert e["UNC001"]["amount"] == "-4675000" and e["BC001"]["amount"] == "27500000"  # Thu/Chi
    assert db.one("SELECT count(*) n FROM bank_transactions WHERE org_id=? AND description LIKE '%Số dư%'", (ctx.org_id,))["n"] == 0


def test_ambiguous_decimal_not_guessed(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "usd_payments_ambiguous.csv"])
    d = db.one("SELECT data_json FROM documents WHERE org_id=?", (ctx.org_id,))
    assert "1.234" in d["data_json"]  # giữ nguyên giá trị gốc
    from modules.accounting.engine import analysis

    ms = analysis.monthly_summary(ctx.org_id)
    assert not ms["months"]  # không có dòng nào bị đoán thành số


def test_macro_workbook_not_executed(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    r, _ = ingest(ctx, [golden / "bang_tinh_macro.xlsm"])
    assert r[0]["kind"] == "xlsm" and any("macro" in w for w in r[0]["warnings"])
    ex = db.one("SELECT status FROM extractions WHERE org_id=?", (ctx.org_id,))
    assert ex["status"] == "OK"


def test_workbook_formula_findings(env, golden, expected):
    from modules.accounting import db, storage
    from modules.accounting.engine import workbook

    ctx = new_ctx()
    ingest(ctx, [golden / "bao_cao_chi_phi_q1.xlsx"])
    f = db.one("SELECT * FROM files WHERE org_id=?", (ctx.org_id,))
    a = workbook.analyze(storage.abspath(f["storage_path"]), f["original_name"])
    types = {x["type"] for x in a["findings"]}
    assert set(expected["workbook_findings"]) <= types
    stale = next(x for x in a["findings"] if x["type"] == "stale_or_wrong_value")
    assert stale["cell"] == "D8"  # SUM(D3:D7) = 41.150.000 nhưng file lưu 40.000.000
    gap = [x for x in a["findings"] if x["type"] == "sum_range_gap"]
    assert any(x["cell"] == "C8" for x in gap)  # SUM(C3:C6) bỏ sót C7
    assert a["summary"]["recalculated"] >= 3


def test_monthly_summary_golden(env, golden, expected):
    from modules.accounting import money
    from modules.accounting.engine import analysis

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / f"so_quy_T{m}_2026.xlsx" for m in (1, 2, 3)] + [golden / "doanh_thu_q1_2026.csv"])
    ms = analysis.monthly_summary(ctx.org_id, ids)
    got = {r["month"]: r for r in ms["months"]}
    for m, v in expected["monthly_cash"].items():
        assert got[m]["cash_in"] == money.D(v["in"]) and got[m]["cash_out"] == money.D(v["out"])
    for m, v in expected["monthly_revenue_csv"].items():
        assert got[m]["revenue"] == money.D(v)
    assert not ms["skipped"]


@pytest.mark.skipif(os.environ.get("AAAP_OCR_TEST") != "1", reason="OCR thật trên GPU: đặt AAAP_OCR_TEST=1")
def test_ocr_scanned_invoice(tmp_path, golden):
    configure(tmp_path, ocr="easyocr")
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "scan_invoice_106.pdf"])
    inv = db.one("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv is not None and inv["source_format"] == "ocr_pdf"
    assert inv["status"] not in ("VERIFIED", "VALID_EXTRACTED")  # OCR không bao giờ tự được tin
    fl = db.all_("SELECT validation_status, model_id FROM fields WHERE org_id=?", (ctx.org_id,))
    assert fl and all(f["validation_status"] in ("NEEDS_REVIEW", "UNKNOWN") for f in fl if f["validation_status"] != "EXTRACTED")
    assert all(f["model_id"] for f in fl)


def test_generic_list_detected_and_profiled(env, golden, expected):
    """Hồi quy từ production: danh sách sinh viên (không có tiêu đề kế toán) trước đây bị bỏ qua hoàn toàn."""
    from modules.accounting import db
    from modules.accounting.engine import analysis

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / expected["roster"]["file"]])
    d = db.one("SELECT data_json FROM cur_documents WHERE org_id=? AND doc_type='table'", (ctx.org_id,))
    assert d is not None
    t = analysis.profile(ctx.org_id, ids)[0]
    assert t["header_row"] == 9 and t["rows"] == expected["roster"]["rows"]
    assert len(t["skipped_rows"]) == expected["roster"]["skipped_footer_rows"]  # dòng ngày tháng, chức danh, chữ ký
    cols = {c["column"]: c for c in t["columns"]}
    assert cols["Mã SV"]["id_like"] and cols["Mã SV"]["distinct"] == 120
    assert dict(cols["Phái"]["distribution"]) == {"Nam": expected["roster"]["male"], "Nữ": expected["roster"]["female"]}
    for sensitive in ("Họ đệm", "Tên", "Ngày sinh", "Số CCCD"):
        assert cols[sensitive]["sensitive"] and "distribution" not in cols[sensitive]
    girls = analysis.profile(ctx.org_id, ids, filter_column="Phái", filter_value="Nữ")[0]
    assert girls["rows"] == 40


def test_reextraction_supersedes_without_double_counting(env, golden, monkeypatch):
    from modules.accounting import db, extract
    from modules.accounting.extract import office

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / "sao_ke_vcb_032026.xlsx"])
    n = lambda: db.one("SELECT count(*) n FROM cur_bank_transactions WHERE org_id=?", (ctx.org_id,))["n"]  # noqa: E731
    assert n() == 10
    monkeypatch.setattr(office, "VERSION", "9.9.9")
    monkeypatch.setitem(extract.PARSERS, "xlsx", ("excel_openpyxl", "9.9.9"))
    e = extract.ensure(ctx.org_id, ids[0], ORG_TAX)
    assert e["parser_version"] == "9.9.9" and n() == 10  # không nhân đôi
    sts = sorted(r["status"] for r in db.all_("SELECT status FROM extractions WHERE file_id=?", (ids[0],)))
    assert sts == ["OK", "SUPERSEDED"]
    assert db.one("SELECT count(*) n FROM bank_transactions WHERE org_id=?", (ctx.org_id,))["n"] == 20  # lịch sử giữ nguyên


def test_amount_in_words_mismatch_flagged(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_109_words_wrong.xml", golden / "inv_sale_011.xml", golden / "inv_sale_011.pdf"])
    rows = {r["number"] + r["source_format"]: r for r in db.all_("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,))}
    bad = rows["0000109xml"]
    assert bad["status"] == "CONFLICTED" and "R-INV-WORDS" in bad["issues_json"] and "năm trăm hai mươi tám nghìn" in bad["issues_json"]
    assert "R-INV-WORDS" not in rows["0000011xml"]["issues_json"] and rows["0000011xml"]["status"] == "VERIFIED"
    assert "R-INV-WORDS" not in rows["0000011pdf_text"]["issues_json"]  # chữ đọc từ PDF khớp
    f = db.one("SELECT normalized_value FROM fields WHERE org_id=? AND field_name='total_in_words' AND extraction_method='pdf_text'", (ctx.org_id,))
    assert f and f["normalized_value"].startswith("Hai mươi bảy triệu năm trăm nghìn")


def test_invalid_tax_id_flagged(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_108_bad_mst.xml"])
    inv = db.one("SELECT status, issues_json FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv["status"] == "NEEDS_REVIEW" and "R-INV-TAXID" in inv["issues_json"] and "0011111111" in inv["issues_json"]


def test_vietnamese_words_parser_property():
    import random

    from modules.accounting.engine.vnwords import int_to_words, words_to_int

    rng = random.Random(123)
    for _ in range(3000):
        n = rng.randint(0, 10**12)
        assert words_to_int(int_to_words(n)) == n
    for text, n in [("Hai tỷ không trăm linh hai triệu không trăm linh hai nghìn không trăm linh hai đồng", 2002002002),
                    ("Bốn mươi tư ngàn đồng chẵn", 44000), ("Bẩy mươi lăm nghìn", 75000), ("Một trăm lẻ năm", 105)]:
        assert words_to_int(text) == n
    assert words_to_int("hai ba triệu") is None and words_to_int("không rõ") is None


def test_legacy_xls_read(env, golden):
    from modules.accounting import db
    from modules.accounting.engine import analysis

    ctx = new_ctx()
    r, ids = ingest(ctx, [golden / "so_quy_T4_2026.xls", golden / "corrupt_excel.xls"])
    assert [x["kind"] for x in r] == ["xls", "xls"]
    ex = {f["original_name"]: e for f, e in ((db.one("SELECT * FROM files WHERE id=?", (i,)), db.one(
        "SELECT * FROM extractions WHERE file_id=? ORDER BY created_at DESC LIMIT 1", (i,))) for i in ids)}
    assert ex["so_quy_T4_2026.xls"]["status"] == "OK" and ex["so_quy_T4_2026.xls"]["parser"] == "excel_xlrd"
    assert ex["corrupt_excel.xls"]["status"] == "FAILED" and "bad_xls" in ex["corrupt_excel.xls"]["error_json"]
    e = {x["doc_no"]: x for x in db.all_("SELECT * FROM imported_entries WHERE org_id=?", (ctx.org_id,))}
    assert e["PT401"]["amount"] == "35000000" and e["PC402"]["amount"] == "-19000000" and e["PT401"]["entry_date"] == "2026-04-02"
    april = next(m for m in analysis.monthly_summary(ctx.org_id, ids)["months"] if m["month"] == "2026-04")
    assert april["cash_in"] == 35000000 and april["cash_out"] == 25000000


def test_pdf_invoice_line_items(env, golden):
    import json as _json

    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_210.pdf", golden / "inv_purchase_211_line_wrong.pdf"])
    inv = {r["number"]: r for r in db.all_("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,))}
    ok = inv["0000210"]
    lines = db.all_("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY line_no", (ok["id"],))
    assert [(x["description"], x["quantity"], x["unit_price"], x["amount"]) for x in lines] == [
        ("Cước vận chuyển nội thành", "4", "500000", "2000000"), ("Bốc xếp hàng hoá", "10", "100000", "1000000")]
    assert ok["status"] == "VALID_EXTRACTED"
    f = db.one("SELECT * FROM fields WHERE document_id=? AND field_name='line1.amount'", (ok["document_id"],))
    loc = _json.loads(f["source_location_json"])
    assert f["extraction_method"] == "pdf_table" and loc["page"] == 1 and len(loc["bbox"]) == 4
    d = db.one("SELECT data_json FROM documents WHERE id=?", (ok["document_id"],))
    assert '"lines_extracted": true' in d["data_json"]
    bad = inv["0000211"]
    assert bad["status"] == "NEEDS_REVIEW" and "line1.amount" in bad["issues_json"]  # 3 × 100.000 ≠ 330.000


def test_pdf_bank_statement(env, golden):
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "sao_ke_pdf_042026.pdf"])
    b = {r["reference"]: r for r in db.all_("SELECT * FROM bank_transactions WHERE org_id=?", (ctx.org_id,))}
    assert b["FT2609200001"]["amount"] == "35000000" and b["FT2610500002"]["amount"] == "-19000000"
    assert b["FT2609200001"]["txn_date"] == "2026-04-02" and b["FT2609200001"]["row_ref"].startswith("Trang 1 dòng")
    d = db.one("SELECT data_json FROM documents WHERE org_id=? AND doc_type='bank_statement'", (ctx.org_id,))
    assert '"row_boxes"' in d["data_json"]


DOCAI = os.environ.get("AAAP_DOCAI_TEST") == "1"


@pytest.mark.skipif(not DOCAI, reason="PaddleOCR/docling thật (venv riêng, chậm): đặt AAAP_DOCAI_TEST=1")
def test_paddleocr_fallback_on_blurred_scan(tmp_path, golden):
    configure(tmp_path, ocr="easyocr", paddle_ocr="auto")
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "scan_invoice_107_blur.pdf"])
    inv = db.one("SELECT * FROM invoices WHERE org_id=?", (ctx.org_id,))
    assert inv is not None, "EasyOCR không đọc được ảnh mờ; PaddleOCR phải nhận ra hoá đơn"
    assert inv["number"] == "0000107" and inv["total"] == "990000" and inv["seller_tax_id"] == "0011111110"
    assert inv["status"] not in ("VERIFIED", "VALID_EXTRACTED")  # OCR không bao giờ tự được tin
    ex = db.one("SELECT stats_json FROM extractions WHERE org_id=?", (ctx.org_id,))
    assert '"ocr_engine": "paddleocr"' in ex["stats_json"]


@pytest.mark.skipif(not DOCAI, reason="PaddleOCR/docling thật (venv riêng, chậm): đặt AAAP_DOCAI_TEST=1")
def test_docling_reads_unruled_table(tmp_path, golden):
    configure(tmp_path, docling="auto")
    from modules.accounting import db

    ctx = new_ctx()
    ingest(ctx, [golden / "sao_ke_khong_ke_o.pdf"])
    b = {r["reference"]: r["amount"] for r in db.all_("SELECT * FROM bank_transactions WHERE org_id=?", (ctx.org_id,))}
    assert b == {"FT2612500001": "12000000", "FT2613200002": "-3300000", "FT2614800003": "95000"}
