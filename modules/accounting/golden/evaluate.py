"""
Đo chỉ số chất lượng trên golden dataset (PHẦN XVII). Không dùng LLM (planner theo quy tắc) để kết quả lặp lại được.

    python -m modules.accounting.golden.evaluate [thư mục ra]

In JSON: tỉ lệ đọc file, độ đúng trạng thái/tổng tiền hoá đơn, precision/recall đối soát,
tỉ lệ dương tính giả khi phát hiện trùng, độ trễ P50/P95 của tác vụ end-to-end.
"""

import io
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Nhãn đúng cho đối soát sao kê ↔ sổ tiền gửi: tham chiếu sao kê → tập số chứng từ sổ
RECON_TRUTH = {
    "FT2609000009": {"FT2609000009"}, "FT2606600003": {"UNC001"}, "FT2607300004": {"UNC002"},
    "FT2607500001": {"BC001"}, "FT2608100002": {"BC002"}, "FT2607700010": {"PT002"},
    "FT2608800007": {"UNC005", "UNC006"},
}
# FT2608500005 (2 bút toán 5.000.000 không phân biệt được) và FT2608700006 (lệch tiền) không có cặp đúng duy nhất;
# FT2606700008 là khoản chi trùng, không có bút toán tương ứng.


def main(out_dir=None):
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    tmp = Path(out_dir or tempfile.mkdtemp(prefix="aaap_eval_"))
    os.environ["PM_ACCOUNTING_DIR"] = str(tmp / "data")
    from core import config as hubcfg

    hubcfg.get()["accounting"] = {"antivirus": "off", "ocr": "off", "llm_planner": False}
    from modules.accounting import db, extract, security
    from modules.accounting.engine import duplicates, reconcile
    from modules.accounting.golden.generate import EXPECTED, build
    from modules.accounting.ingest import pipeline

    golden = build(tmp / "golden")
    metrics = {}
    org = security.create_org("eval", "eval@x", tax_id=EXPECTED["org"]["tax_id"])
    ctx = security.context(org, "eval@x")
    db.bind(org)

    # 1. Đọc file
    supported = ok = rejected_ok = 0
    ids_by_name = {}
    for f in sorted(golden.iterdir()):
        if f.name == "EXPECTED.json" or f.suffix == ".png":
            continue
        r = pipeline.ingest_stream(ctx, io.BytesIO(f.read_bytes()), f.name)
        if f.name in EXPECTED["rejected"]:
            rejected_ok += r["status"] == "rejected" and r["error"]["code"] == EXPECTED["rejected"][f.name]
            continue
        for fid in pipeline.flatten([r]):
            row = db.one("SELECT original_name FROM files WHERE id=?", (fid,))
            ids_by_name.setdefault(row["original_name"], fid)
            supported += 1
            e = extract.ensure(org, fid, EXPECTED["org"]["tax_id"])
            ok += e["status"] in ("OK", "PARTIAL")
    metrics["document_parsing_success_rate"] = round(ok / supported, 4)
    metrics["malicious_or_unsupported_rejected"] = f"{rejected_ok}/{len(EXPECTED['rejected'])}"
    metrics["note_parsing"] = "PARTIAL tính là đọc được; encrypted.pdf là thất bại có chủ đích (không có mật khẩu)."

    # 2. Hoá đơn
    inv = {r["n"]: r for r in db.all_("SELECT i.*, f.original_name n FROM invoices i JOIN files f ON f.id=i.file_id WHERE i.org_id=?", (org,))}
    st = EXPECTED["invoice_status"]
    metrics["invoice_status_accuracy"] = round(sum(inv.get(n, {}).get("status") == s for n, s in st.items()) / len(st), 4)
    tt = EXPECTED["invoice_totals"]
    metrics["invoice_total_accuracy"] = round(sum(inv.get(n, {}).get("total") == v for n, v in tt.items()) / len(tt), 4)
    xml, pdf = inv["inv_sale_011.xml"], inv["inv_sale_011.pdf"]
    keys = ("form_no", "series", "number", "issue_date", "seller_tax_id", "buyer_tax_id", "subtotal", "vat_amount", "total")
    metrics["pdf_field_accuracy_vs_xml"] = round(sum(xml[k] == pdf[k] for k in keys) / len(keys), 4)

    # 3. Trùng lặp
    groups = duplicates.detect(org)
    num = {r["id"]: r["n"] for r in inv.values()}
    flagged = [g for g in groups if g["type"].startswith("INVOICE")]
    truth = [{"inv_sale_011.xml", "inv_sale_011_copy.xml", "inv_sale_011.pdf"}, {"inv_purchase_101.xml", "inv_purchase_105_suspect.xml"}]
    hits = [g for g in flagged if {num[i] for i in g["invoice_ids"]} in truth]
    metrics["duplicate_groups_flagged"] = len(flagged)
    metrics["duplicate_false_positive_rate"] = round((len(flagged) - len(hits)) / max(1, len(flagged)), 4)
    metrics["duplicate_recall"] = round(len(hits) / len(truth), 4)

    # 4. Đối soát
    bank = db.all_("SELECT id, txn_date date, amount, reference, description, counterparty FROM bank_transactions WHERE org_id=? AND file_id=?",
                   (org, ids_by_name["sao_ke_vcb_032026.xlsx"]))
    book = db.all_("SELECT id, entry_date date, amount, doc_no reference, description, counterparty FROM imported_entries WHERE org_id=? AND file_id=?",
                   (org, ids_by_name["so_tien_gui_032026.xlsx"]))
    matches, _ = reconcile.reconcile(bank, book, 3)
    proposed = [m for m in matches if m["status"] in ("MATCHED_EXACT", "MATCHED_VERIFIED", "POTENTIAL_MATCH")]
    correct = [m for m in proposed if len(m["bank_rows"]) == 1
               and RECON_TRUTH.get(m["bank_rows"][0]["reference"]) == {k["reference"] for k in m["book_rows"]}]
    metrics["reconciliation_precision"] = round(len(correct) / max(1, len(proposed)), 4)
    metrics["reconciliation_recall"] = round(len(correct) / len(RECON_TRUTH), 4)
    metrics["reconciliation_auto_confirmed"] = sum(m["status"] in ("MATCHED_EXACT", "MATCHED_VERIFIED") for m in matches)
    metrics["human_review_rate_reconciliation"] = round(sum(m["status"] in ("POTENTIAL_MATCH", "AMBIGUOUS", "CONFLICTED") for m in matches) / len(matches), 4)

    # 5. Tác vụ end-to-end (planner quy tắc, worker đồng bộ) — độ trễ
    from flask import Flask

    from core import auth
    from modules.accounting import api, jobs

    auth.USERS_PATH, auth.SECRET_PATH, auth.SETUP_CODE_PATH = (str(tmp / x) for x in ("u.json", "s.key", "c.txt"))
    app = Flask("eval")
    app.config.update(TESTING=True, FEATURES={"accounting": True})
    auth.init_app(app)
    app.register_blueprint(api.bp)
    c = app.test_client()
    c.post("/api/auth/register", json={"email": "u@x.com", "password": "matkhau123"})
    users = auth._read()
    users["users"]["u@x.com"]["modules"].append("accounting")
    auth._write(users)
    org2 = c.get("/api/accounting/status").json["orgs"][0]["id"]
    c.post(f"/api/accounting/o/{org2}/settings", json={"tax_id": EXPECTED["org"]["tax_id"]})
    scen = {
        "A_invoices": (["hoa_don_thang3.zip", "inv_sale_011.pdf", "inv_purchase_103_vat_wrong.xml", "inv_injection_205.xml"],
                       "Kiểm tra tất cả hoá đơn, phát hiện trùng lặp, tổng hợp theo nhà cung cấp và xuất Excel"),
        "B_reconciliation": (["sao_ke_vcb_032026.xlsx", "so_tien_gui_032026.xlsx"], "Đối soát sao kê với sổ tiền gửi và tạo báo cáo sai lệch"),
        "C_monthly": ([f"so_quy_T{m}_2026.xlsx" for m in (1, 2, 3)] + ["doanh_thu_q1_2026.csv"], "So sánh thu chi theo tháng, tạo dashboard Excel"),
    }
    lat, done, valid = [], 0, 0
    per = {}
    for name, (files, cmd) in scen.items():
        per[name] = []
        for _ in range(5):
            conv = c.post(f"/api/accounting/o/{org2}/conversations", json={}).json["conversation"]["id"]
            c.post(f"/api/accounting/o/{org2}/files", data={"conversation_id": conv, "files": [(io.BytesIO((golden / f).read_bytes()), f) for f in files]},
                   content_type="multipart/form-data")
            tid = c.post(f"/api/accounting/o/{org2}/conversations/{conv}/messages", json={"content": cmd}).json["task_id"]
            t0 = time.perf_counter()
            while jobs.run_once("eval"):
                pass
            dt = time.perf_counter() - t0
            v = c.get(f"/api/accounting/o/{org2}/tasks/{tid}").json
            lat.append(dt)
            per[name].append(round(dt, 3))
            done += v["task"]["status"] in ("COMPLETED", "PARTIALLY_COMPLETED")
            valid += any(s["tool"] == "generate_excel" and s["data"].get("verified") for s in v["steps"])
    lat.sort()
    metrics["task_completion_rate"] = round(done / len(lat), 4)
    metrics["artifact_validity_rate"] = round(valid / len(lat), 4)
    metrics["latency_p50_s"] = round(statistics.median(lat), 3)
    metrics["latency_p95_s"] = round(lat[int(0.95 * (len(lat) - 1))], 3)
    metrics["latency_by_scenario_s"] = per
    metrics["latency_note"] = "Planner theo quy tắc, không gồm thời gian upload và thời gian LLM lập kế hoạch (đo riêng trên staging)."
    metrics["cost_per_task"] = "0 chi phí API: AI chạy local (Ollama); chi phí là thời gian GPU/CPU của máy chủ"
    ok_chain = __import__("modules.accounting.audit", fromlist=["verify"]).verify()
    metrics["audit_chain_ok"] = ok_chain[0]
    (tmp / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    return metrics


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1] if len(sys.argv) > 1 else None)
