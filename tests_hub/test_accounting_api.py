"""
End-to-end qua HTTP (Flask test client): phân quyền Hub, tổ chức, upload, giao việc bằng tiếng Việt,
worker, báo cáo đã xác minh, cô lập tenant, prompt injection, phê duyệt, sửa báo cáo, thiếu dữ liệu,
khôi phục khi worker chết, thử lại lỗi tạm thời.   pytest tests_hub/test_accounting_api.py -q
"""

import io

import openpyxl
import pytest
from accounting_fixture import configure, grant, make_app, register, upload


@pytest.fixture()
def app(tmp_path):
    configure(tmp_path)
    return make_app()


def _login(app, email):
    c = app.test_client()
    register(c, email)
    grant(email)
    return c


def _org(c):
    r = c.get("/api/accounting/status")
    assert r.status_code == 200, r.json
    return r.json["orgs"][0]["id"]


def _set_tax(c, org, tax="0012345678"):
    assert c.post(f"/api/accounting/o/{org}/settings", json={"tax_id": tax}).status_code == 200


def _run(c, org, conv, command, files=None):
    from modules.accounting import jobs

    r = c.post(f"/api/accounting/o/{org}/conversations/{conv}/messages", json={"content": command, "file_ids": files or []})
    assert r.status_code == 200, r.json
    tid = r.json["task_id"]
    for _ in range(10):
        if not jobs.run_once("test"):
            break
    return c.get(f"/api/accounting/o/{org}/tasks/{tid}").json


def _conv(c, org):
    return c.post(f"/api/accounting/o/{org}/conversations", json={"title": "t"}).json["conversation"]["id"]


def test_hub_permission_required(app):
    c = app.test_client()
    assert c.get("/api/accounting/status").status_code == 401
    register(c, "nouser@x.com")  # auto_approve không tự cấp công cụ nhạy cảm
    r = c.get("/api/accounting/status")
    assert r.status_code == 403 and r.json["code"] == "no_permission"


def test_full_workflow_invoices(app, golden):
    c = _login(app, "ketoan@x.com")
    org = _org(c)
    _set_tax(c, org)
    conv = _conv(c, org)
    up = upload(c, org, [golden / "hoa_don_thang3.zip", golden / "inv_sale_011.pdf", golden / "inv_injection_205.xml",
                         golden / "inv_purchase_103_vat_wrong.xml"], conv)
    assert len(up["file_ids"]) == 7
    v = _run(c, org, conv, "Kiểm tra tất cả hoá đơn, phát hiện trùng lặp, tổng hợp theo nhà cung cấp, lọc các hoá đơn trên 20 triệu và xuất báo cáo Excel kèm PDF")
    t = v["task"]
    assert t["status"] in ("COMPLETED", "PARTIALLY_COMPLETED"), t
    tools_run = [s["tool"] for s in v["steps"]]
    for name in ("extract_documents", "validate_invoices", "detect_duplicates", "summarize_invoices", "filter_invoices",
                 "generate_excel", "generate_pdf"):
        assert name in tools_run
    assert "request_posting" not in tools_run and "propose_journal_entries" not in tools_run
    kinds = [e["kind"] for e in v["events"]]
    assert "plan" in kinds and "step_start" in kinds and "artifact" in kinds
    xl = next(s for s in v["steps"] if s["tool"] == "generate_excel")["data"]
    assert xl["verified"] is True
    art = c.get(f"/api/accounting/o/{org}/artifacts/{xl['artifact_id']}").json["artifact"]
    names = [s["name"] for s in art["preview"]["sheets"]]
    assert {"Tóm tắt", "Hoá đơn", "Trùng lặp", "Theo đối tượng", "Hoá đơn đã lọc"} <= set(names)
    filt = next(s for s in art["preview"]["sheets"] if s["name"] == "Hoá đơn đã lọc")
    assert {r["number"] for r in filt["rows"]} == {"0000202", "0000011"}  # > 20 triệu: 21,6tr và 27,5tr (bản trùng 011 vẫn liệt kê)
    dl = c.get(f"/api/accounting/o/{org}/artifacts/{xl['artifact_id']}/download")
    assert dl.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(dl.data))
    assert "Nguồn dữ liệu" in wb.sheetnames and "Cảnh báo" in wb.sheetnames
    ws = wb["Theo đối tượng"]
    assert ws.freeze_panes == "A6" and ws.auto_filter.ref
    # Tổng hợp không cộng hoá đơn trùng / chưa kiểm tra
    sec = next(s for s in art["preview"]["sheets"] if s["name"] == "Theo đối tượng")
    sale = next(r for r in sec["rows"] if r["tax_id"] == "0044444444")
    assert sale["total"] == "27500000" and sale["count"] == 1
    msgs = c.get(f"/api/accounting/o/{org}/conversations/{conv}").json["messages"]
    assert msgs[-1]["role"] == "assistant" and msgs[-1]["task_id"] == t["id"]


def test_prompt_injection_has_no_effect(app, golden):
    from modules.accounting import db

    c = _login(app, "a@x.com")
    org = _org(c)
    _set_tax(c, org)
    conv = _conv(c, org)
    upload(c, org, [golden / "inv_injection_205.xml", golden / "bao_cao_chi_phi_q1.xlsx"], conv)
    v = _run(c, org, conv, "Kiểm tra các chứng từ này")
    assert v["task"]["status"] in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert db.one("SELECT count(*) n FROM approvals WHERE org_id=?", (org,))["n"] == 0
    assert db.one("SELECT count(*) n FROM journal_entries WHERE org_id=?", (org,))["n"] == 0
    assert db.one("SELECT count(*) n FROM files WHERE org_id=?", (org,))["n"] == 2  # không xoá gì


def test_planner_output_is_policed(app, monkeypatch):
    """Dù LLM bị thao túng đề xuất ghi sổ / công cụ lạ / tham số bậy, kế hoạch thực thi vẫn bị lọc."""
    from modules.accounting.agent import planner, policy
    from modules.accounting.security import Ctx

    ctx = Ctx("o", "u", {"ACCOUNTANT"})
    malicious = {"intent": "x", "questions": [], "unsupported": [], "steps": [
        {"tool": "request_posting", "goal": "ghi sổ ngay", "params": {}},
        {"tool": "run_shell", "goal": "rm -rf", "params": {"cmd": "del *"}},
        {"tool": "filter_invoices", "goal": "x", "params": {"min_total": "1", "url": "http://evil"}},
        {"tool": "revise_artifact", "goal": "x", "params": {"artifact_id": "khac-hoi-thoai", "ops": [{"op": "rename_sheet"}]}},
        {"tool": "summarize_invoices", "goal": "ok", "params": {}}]}
    monkeypatch.setattr(planner, "_llm_plan", lambda *a: malicious)
    from modules.accounting import settings

    orig = settings.get

    def cfg():
        d = orig()
        d["llm_planner"] = True
        return d

    monkeypatch.setattr(settings, "get", cfg)
    manifest = {"files": [], "invoices": 1, "invoice_status": {}, "bank_txns": 0, "ledger_entries": 0, "tables": 0,
                "workbooks": 0, "currencies": ["VND"], "date_range": None}
    steps, q, u, source, note = planner.plan("Tổng hợp hoá đơn", manifest, [], policy.allowed_classes(ctx))
    assert source == "llm"
    assert [s["tool"] for s in steps] == ["summarize_invoices", "generate_excel"]
    assert "request_posting" in note and "run_shell" in note


def test_tenant_isolation_api(app, golden):
    a = _login(app, "a@x.com")
    b = _login(app, "b@x.com")
    org_a, org_b = _org(a), _org(b)
    assert org_a != org_b
    conv = _conv(a, org_a)
    up = upload(a, org_a, [golden / "inv_sale_011.xml"], conv)
    fid = up["file_ids"][0]
    v = _run(a, org_a, conv, "Tổng hợp hoá đơn và xuất Excel")
    aid = next(s for s in v["steps"] if s["tool"] == "generate_excel")["data"]["artifact_id"]
    for url in (f"/api/accounting/o/{org_a}/files", f"/api/accounting/o/{org_a}/files/{fid}/download",
                f"/api/accounting/o/{org_a}/artifacts/{aid}", f"/api/accounting/o/{org_a}/artifacts/{aid}/download",
                f"/api/accounting/o/{org_a}/conversations/{conv}", f"/api/accounting/o/{org_a}/tasks/{v['task']['id']}"):
        assert b.get(url).status_code == 404, url
    # Dùng org của mình nhưng id tài nguyên của người khác
    assert b.get(f"/api/accounting/o/{org_b}/files/{fid}/download").status_code == 404
    assert b.get(f"/api/accounting/o/{org_b}/artifacts/{aid}").status_code == 404
    r = b.post(f"/api/accounting/o/{org_b}/conversations/{_conv(b, org_b)}/messages", json={"content": "x", "file_ids": [fid]})
    assert r.status_code == 400  # không được dùng file của tổ chức khác
    assert b.get(f"/api/accounting/o/{org_b}/files").json["files"] == []


def test_role_enforcement_api(app, golden):
    a = _login(app, "admin@x.com")
    org = _org(a)
    v = _login(app, "viewer@x.com")
    assert a.post(f"/api/accounting/o/{org}/members", json={"email": "viewer@x.com", "roles": ["VIEWER"]}).status_code == 200
    resp = v.post(f"/api/accounting/o/{org}/files", data={"files": [(io.BytesIO(b"<x/>"), "a.xml")]}, content_type="multipart/form-data")
    assert resp.status_code == 403
    assert v.get(f"/api/accounting/o/{org}/audit").status_code == 403
    assert v.post(f"/api/accounting/o/{org}/conversations", json={}).status_code == 403
    assert v.get(f"/api/accounting/o/{org}/files").status_code == 200  # VIEWER được đọc
    assert a.get(f"/api/accounting/o/{org}/audit/verify").json["ok"] is True


def test_journal_scenario_e_and_approval(app, golden):
    """Scenario E: thiếu dữ liệu → hỏi; trả lời → đề xuất; ghi sổ chỉ khi người khác phê duyệt."""
    from modules.accounting import db

    a = _login(app, "ketoan@x.com")
    org = _org(a)
    _set_tax(a, org)
    conv = _conv(a, org)
    upload(a, org, [golden / "inv_purchase_101.xml", golden / "inv_sale_012.xml", golden / "inv_purchase_103_vat_wrong.xml"], conv)
    v = _run(a, org, conv, "Tự động định khoản các hoá đơn")
    step = next(s for s in v["steps"] if s["tool"] == "propose_journal_entries")
    assert step["status"] == "COMPLETED"
    assert v["task"]["status"] == "COMPLETED"
    entries = a.get(f"/api/accounting/o/{org}/journal").json["entries"]
    assert len(entries) == 1 and entries[0]["status"] == "PROPOSED"  # chỉ HĐ bán ra (131/511/33311)
    assert {ln["account_code"] for ln in entries[0]["lines"]} == {"131", "511", "33311"}
    reviews = a.get(f"/api/accounting/o/{org}/reviews").json["items"]
    missing = [r for r in reviews if r["kind"] == "missing_data"]
    assert len(missing) == 1 and "tài khoản" in missing[0]["title"]  # HĐ mua 101: hỏi TK Nợ
    assert db.one("SELECT count(*) n FROM ledger_entries WHERE org_id=?", (org,))["n"] == 0
    inv101 = missing[0]["target_id"]
    r = a.post(f"/api/accounting/o/{org}/answers", json={"answers": {inv101: "642"}, "save_rule": True})
    assert r.status_code == 200 and len(r.json["proposed"]) == 1 and r.json["rule_ids"]
    entries = a.get(f"/api/accounting/o/{org}/journal").json["entries"]
    purchase = next(e for e in entries if any(ln["account_code"] == "642" for ln in e["lines"]))
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in purchase["lines"]} == {
        ("642", "4250000", "0"), ("1331", "425000", "0"), ("331", "0", "4675000")}
    appr = a.post(f"/api/accounting/o/{org}/journal/{purchase['id']}/request-post").json["approval_id"]
    r = a.post(f"/api/accounting/o/{org}/approvals/{appr}/approve")
    assert r.status_code == 403 and r.json["code"] == "sod"
    b = _login(app, "truongphong@x.com")
    assert a.post(f"/api/accounting/o/{org}/members", json={"email": "truongphong@x.com", "roles": ["APPROVER"]}).status_code == 200
    pend = b.get(f"/api/accounting/o/{org}/approvals").json["approvals"]
    assert pend[0]["can_approve"] is True
    assert b.post(f"/api/accounting/o/{org}/approvals/{appr}/approve").status_code == 200
    tb = a.get(f"/api/accounting/o/{org}/ledger/trial-balance").json
    assert tb["balanced"] and tb["total_debit"] == "4675000"
    # Quy tắc do người dùng đề xuất chưa có hiệu lực cho tới khi người khác duyệt
    rule = a.get(f"/api/accounting/o/{org}/rules").json["rules"][0]
    assert rule["status"] == "PROPOSED"
    assert a.post(f"/api/accounting/o/{org}/rules/{rule['id']}/decide", json={"approve": True}).status_code == 403
    assert b.post(f"/api/accounting/o/{org}/rules/{rule['id']}/decide", json={"approve": True}).status_code == 200


def test_scenario_c_and_d_revise_keeps_old_version(app, golden):
    c = _login(app, "a@x.com")
    org = _org(c)
    conv = _conv(c, org)
    upload(c, org, [golden / f"so_quy_T{m}_2026.xlsx" for m in (1, 2, 3)] + [golden / "doanh_thu_q1_2026.csv"], conv)
    v = _run(c, org, conv, "Tổng hợp dữ liệu, so sánh thu chi và doanh thu theo tháng, tạo dashboard Excel")
    assert "monthly_summary" in [s["tool"] for s in v["steps"]]
    a1 = next(s for s in v["steps"] if s["tool"] == "generate_excel")["data"]["artifact_id"]
    sheet = next(s for s in c.get(f"/api/accounting/o/{org}/artifacts/{a1}").json["artifact"]["preview"]["sheets"] if s["name"] == "Theo tháng")
    assert sheet["totals"]["cash_in"] == "97000000" and sheet["totals"]["revenue"] == "116000000"
    assert sheet["charts"]
    v2 = _run(c, org, conv, "Thêm cột lợi nhuận gộp và biểu đồ so sánh 6 tháng")
    rev = next(s for s in v2["steps"] if s["tool"] == "revise_artifact")
    # Báo cáo không có cột giá vốn → không bịa lợi nhuận gộp: thêm biểu đồ, hỏi lại phần còn thiếu
    assert rev["status"] == "COMPLETED" and rev["data"]["changes"] == ["Thêm biểu đồ bar 'So sánh 6 tháng' vào sheet 'Theo tháng'"]
    assert v2["task"]["status"] == "PARTIALLY_COMPLETED"
    assert any("giá vốn" in q for q in v2["task"]["summary"]["questions"])
    a2 = rev["data"]["artifact_id"]
    v3 = _run(c, org, conv, "Sắp xếp theo doanh thu giảm dần")
    rev3 = next(s for s in v3["steps"] if s["tool"] == "revise_artifact")
    assert rev3["status"] == "COMPLETED", rev3
    a3 = rev3["data"]["artifact_id"]
    art3 = c.get(f"/api/accounting/o/{org}/artifacts/{a3}").json["artifact"]
    assert art3["version"] == 3 and art3["parent_id"] == a2
    assert [x["version"] for x in art3["versions"]] == [1, 2, 3]
    assert c.get(f"/api/accounting/o/{org}/artifacts/{a1}/download").status_code == 200  # bản cũ còn nguyên
    months = [r["month"] for r in next(s for s in art3["preview"]["sheets"] if s["name"] == "Theo tháng")["rows"]]
    assert months == ["2026-01", "2026-02", "2026-03"]  # doanh thu 45 > 38 > 33
    v1_months = [r["month"] for r in next(s for s in c.get(f"/api/accounting/o/{org}/artifacts/{a1}").json["artifact"]["preview"]["sheets"] if s["name"] == "Theo tháng")["rows"]]
    assert v1_months == months and not next(s for s in c.get(f"/api/accounting/o/{org}/artifacts/{a1}").json["artifact"]["preview"]["sheets"] if s["name"] == "Theo tháng")["charts"][1:]


def test_revise_gross_profit_formula(app):
    """Scenario D trực tiếp trên spec có cột doanh thu và giá vốn: thêm cột tính + biểu đồ → công thức Excel đúng."""
    from modules.accounting.reports import excel as xl
    from modules.accounting.reports import spec as S

    sp = S.new_spec("Test", "Org", "Q1")
    sp["sheets"].append(S.table("KQKD", [{"key": "month", "label": "Tháng"}, {"key": "rev", "label": "Doanh thu", "type": "money"},
                                         {"key": "cogs", "label": "Giá vốn", "type": "money"}],
                                [{"month": f"2026-{m:02d}", "rev": str(100 + m), "cogs": str(60 + m)} for m in range(1, 7)], totals=["rev", "cogs"]))
    from modules.accounting.agent.planner import rule_ops

    art = {"sheets": [{"name": "KQKD", "columns": sp["sheets"][0]["columns"], "rows_preview": sp["sheets"][0]["rows"]}]}
    ops, qs = rule_ops("Thêm cột lợi nhuận gộp và biểu đồ so sánh 6 tháng", art)
    assert not qs and [o["op"] for o in ops] == ["add_computed_column", "add_chart"]
    new, log = S.apply_ops(sp, ops)
    data, layout = xl.render(new)
    assert xl.verify(data, new, layout)["ok"]
    ws = openpyxl.load_workbook(io.BytesIO(data))["KQKD"]
    assert ws["D6"].value == "=B6-C6" and ws["D12"].value == "=SUBTOTAL(9,D6:D11)" and len(ws._charts) == 1
    assert S.totals(new["sheets"][0])["loi_nhuan_gop"] == "240"


def test_bank_reconciliation_task(app, golden):
    c = _login(app, "a@x.com")
    org = _org(c)
    conv = _conv(c, org)
    upload(c, org, [golden / "sao_ke_vcb_032026.xlsx", golden / "so_tien_gui_032026.xlsx"], conv)
    v = _run(c, org, conv, "Đối soát tất cả giao dịch, tìm khoản chưa khớp và tạo báo cáo sai lệch")
    rec = next(s for s in v["steps"] if s["tool"] == "reconcile_bank")
    assert rec["status"] == "COMPLETED" and "AMBIGUOUS 1" in rec["summary"]
    kinds = {r["kind"] for r in c.get(f"/api/accounting/o/{org}/reviews").json["items"]}
    assert {"recon_ambiguous", "recon_conflicted", "recon_potential_match", "dup_suspected_double_payment"} <= kinds


def test_worker_crash_resumes_without_duplicates(app, golden):
    from modules.accounting import db, jobs
    from modules.accounting.agent import runner

    c = _login(app, "a@x.com")
    org = _org(c)
    conv = _conv(c, org)
    upload(c, org, [golden / "inv_sale_011.xml", golden / "inv_sale_012.xml"], conv)
    r = c.post(f"/api/accounting/o/{org}/conversations/{conv}/messages", json={"content": "Tổng hợp hoá đơn, xuất Excel"})
    tid = r.json["task_id"]
    assert jobs.claim("dead-worker") == tid
    # Worker chạy được 2 bước rồi chết: mô phỏng bằng cách chạy tay 2 bước và để lease hết hạn
    run = runner.Run(db.one("SELECT * FROM tasks WHERE id=?", (tid,)))
    runner._insert_steps(run.task, [{"tool": "inspect_files", "goal": "a"}, {"tool": "extract_documents", "goal": "b"}], 1)
    for s in db.all_("SELECT * FROM task_steps WHERE task_id=? ORDER BY seq", (tid,)):
        runner._run_step(run, s)
    with db.tx() as cx:
        cx.execute("UPDATE tasks SET lease_until=? WHERE id=?", (db.now() - 1, tid))
        cx.execute("UPDATE task_steps SET status='RUNNING' WHERE task_id=? AND seq=2", (tid,))  # đang chạy dở
    assert jobs.run_once("rescuer") == tid
    t = db.one("SELECT status, attempts FROM tasks WHERE id=?", (tid,))
    assert t["status"] == "COMPLETED" and t["attempts"] == 1
    assert db.one("SELECT count(*) n FROM artifacts WHERE task_id=?", (tid,))["n"] == 1
    assert db.one("SELECT count(*) n FROM extractions WHERE org_id=?", (org,))["n"] == 2  # không trích xuất lại
    ev = [e["message"] for e in c.get(f"/api/accounting/o/{org}/tasks/{tid}").json["events"]]
    assert any("gián đoạn" in m for m in ev)


def test_transient_error_retried_with_backoff(app, golden, monkeypatch):
    from core import llm
    from modules.accounting import db, jobs
    from modules.accounting.agent import tools

    c = _login(app, "a@x.com")
    org = _org(c)
    conv = _conv(c, org)
    upload(c, org, [golden / "inv_sale_011.xml"], conv)
    calls = {"n": 0}
    orig = tools.REGISTRY["summarize_invoices"].handler

    def flaky(run, p):
        calls["n"] += 1
        if calls["n"] == 1:
            raise llm.LLMError("Ollama trả lời quá 240s")
        return orig(run, p)

    monkeypatch.setattr(tools.REGISTRY["summarize_invoices"], "handler", flaky)
    r = c.post(f"/api/accounting/o/{org}/conversations/{conv}/messages", json={"content": "Tổng hợp hoá đơn"})
    tid = r.json["task_id"]
    jobs.run_once("w")
    t = db.one("SELECT status, not_before FROM tasks WHERE id=?", (tid,))
    assert t["status"] == "RETRY_SCHEDULED" and t["not_before"] > db.now()
    assert jobs.run_once("w") is None  # chưa tới giờ thử lại → không chạy dồn dập
    with db.tx() as cx:
        cx.execute("UPDATE tasks SET not_before=0 WHERE id=?", (tid,))
    jobs.run_once("w")
    assert db.one("SELECT status FROM tasks WHERE id=?", (tid,))["status"] == "COMPLETED" and calls["n"] == 2


def test_cancel_and_waiting_for_input(app, golden):
    from modules.accounting import db, jobs

    c = _login(app, "a@x.com")
    org = _org(c)
    conv = _conv(c, org)
    r = c.post(f"/api/accounting/o/{org}/conversations/{conv}/messages", json={"content": "Đối soát sao kê"})
    tid = r.json["task_id"]
    assert c.post(f"/api/accounting/o/{org}/tasks/{tid}/cancel").status_code == 200
    assert db.one("SELECT status FROM tasks WHERE id=?", (tid,))["status"] == "CANCELLED"
    assert jobs.run_once("w") is None
    v = _run(c, org, conv, "Đối soát sao kê")  # không có file nào
    assert v["task"]["status"] == "WAITING_FOR_INPUT"
    assert "kéo thả" in c.get(f"/api/accounting/o/{org}/conversations/{conv}").json["messages"][-1]["content"]


def test_illegal_transition_rejected(app):
    from modules.accounting.agent import runner

    with pytest.raises(runner.TransitionError):
        runner.transition("khong-ton-tai", "COMPLETED")
    assert "COMPLETED" not in runner.TRANSITIONS["RUNNING"]  # phải qua VERIFYING


def test_missing_org_tax_id_never_silently_empties(app, golden, monkeypatch):
    """Hồi quy (phát hiện khi chạy LLM thật trên staging): LLM truyền direction=purchase khi tổ chức chưa có MST
    → trước đây trả 0 hoá đơn âm thầm. Nay: xử lý tất cả, cảnh báo, hỏi MST, task PARTIALLY_COMPLETED."""
    from modules.accounting import settings
    from modules.accounting.agent import planner

    orig = settings.get
    monkeypatch.setattr(settings, "get", lambda: {**orig(), "llm_planner": True})
    monkeypatch.setattr(planner, "_llm_plan", lambda *a: {"intent": "x", "questions": [], "unsupported": [], "steps": [
        {"tool": "summarize_invoices", "goal": "theo nhà cung cấp", "params": {"direction": "purchase"}},
        {"tool": "filter_invoices", "goal": "trên 20 triệu", "params": {"direction": "purchase", "min_total": 20000000}}]})
    c = _login(app, "a@x.com")
    org = _org(c)  # không khai báo MST
    conv = _conv(c, org)
    upload(c, org, [golden / "inv_purchase_202_vat8.xml", golden / "inv_sale_011.xml", golden / "inv_purchase_101.xml"], conv)
    v = _run(c, org, conv, "Phân loại theo nhà cung cấp, lọc hoá đơn trên 20 triệu")
    assert v["task"]["plan_source"] == "llm"
    assert v["task"]["status"] == "PARTIALLY_COMPLETED"
    assert any("mã số thuế" in q for q in v["task"]["summary"]["questions"])
    filt = next(s for s in v["steps"] if s["tool"] == "filter_invoices")
    assert filt["summary"].startswith("2 hoá đơn")  # 21,6tr và 27,5tr — không bị lọc rỗng
    summ = next(s for s in v["steps"] if s["tool"] == "summarize_invoices")
    assert "MST" in " ".join(summ["warnings"])


def test_duplicate_zip_attaches_members_and_bad_json_rejected(app, golden):
    c = _login(app, "a@x.com")
    org = _org(c)
    conv1, conv2 = _conv(c, org), _conv(c, org)
    upload(c, org, [golden / "hoa_don_thang3.zip"], conv1)
    up2 = upload(c, org, [golden / "hoa_don_thang3.zip"], conv2)
    assert up2["results"][0]["status"] == "duplicate" and len(up2["file_ids"]) == 4
    assert len(c.get(f"/api/accounting/o/{org}/conversations/{conv2}").json["files"]) == 5  # zip + 4 hoá đơn
    r = c.post(f"/api/accounting/o/{org}/settings", data=b"\xff\xfe{bad", content_type="application/json")
    assert r.status_code == 400


def test_report_summary_has_no_running_steps(app, golden):
    c = _login(app, "a@x.com")
    org = _org(c)
    conv = _conv(c, org)
    upload(c, org, [golden / "inv_sale_011.xml"], conv)
    v = _run(c, org, conv, "Tổng hợp hoá đơn, xuất Excel và PDF")
    aid = next(s for s in v["steps"] if s["tool"] == "generate_excel")["data"]["artifact_id"]
    summ = c.get(f"/api/accounting/o/{org}/artifacts/{aid}").json["artifact"]["preview"]["sheets"][0]
    assert summ["name"] == "Tóm tắt" and {r["status"] for r in summ["rows"]} == {"COMPLETED"}
    assert "generate_excel" not in {r["tool"] for r in summ["rows"]}
    pdf = next(s for s in v["steps"] if s["tool"] == "generate_pdf")["data"]
    r = c.get(f"/api/accounting/o/{org}/artifacts/{pdf['artifact_id']}/download")
    assert r.status_code == 200 and r.data[:5] == b"%PDF-"
