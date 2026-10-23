"""
Accounting engine: tiền tệ, bút toán kép, kỳ khoá, bất biến sổ cái, phân tách nhiệm vụ, nhật ký kiểm toán,
đối soát và phát hiện trùng trên golden dataset.  pytest tests_hub/test_accounting_engine.py -q
"""

import random
import sqlite3
from decimal import Decimal

import pytest
from accounting_fixture import configure, ingest, new_ctx


@pytest.fixture()
def env(tmp_path):
    configure(tmp_path)
    return tmp_path


# ── Tiền tệ ──────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,cur,value,status", [
    ("25.000.000", "VND", "25000000", "OK"),
    ("25.000.000 đ", "VND", "25000000", "OK"),
    ("1.234.567,50", "USD", "1234567.50", "OK"),
    ("1,234,567.50", "USD", "1234567.50", "OK"),
    ("(1.000)", "VND", "-1000", "OK"),
    ("1.234", "USD", None, "AMBIGUOUS"),
    ("1.234", "VND", "1234", "OK"),
    ("12,5", "USD", "12.5", "OK"),
    ("1.23.4", "VND", None, "INVALID"),
    ("abc", "VND", None, "INVALID"),
    ("", "VND", None, "EMPTY"),
])
def test_parse_amount(raw, cur, value, status):
    from modules.accounting import money

    p = money.parse_amount(raw, cur)
    assert p.status == status
    assert (p.value == Decimal(value)) if value is not None else p.value is None


def test_no_float_drift_property():
    """Tính chất: cộng 10.000 khoản ngẫu nhiên bằng Decimal luôn bằng tổng số nguyên đồng — không sai số float."""
    from modules.accounting import money

    rng = random.Random(20260323)
    cents = [rng.randint(-10**9, 10**9) for _ in range(10000)]
    assert money.sum_(Decimal(c) / 100 for c in cents) == Decimal(sum(cents)) / 100
    assert money.sum_(["0.1"] * 10) == Decimal("1")  # 0.1*10 bằng float ra 0.9999999999999999


def test_rounding_half_up_explicit():
    from modules.accounting import money

    assert money.q("2.5", "VND") == Decimal("3")
    assert money.q("-2.5", "VND") == Decimal("-3")
    assert money.q("1.005", "USD") == Decimal("1.01")


def test_vn_format_roundtrip_property():
    from modules.accounting import money

    rng = random.Random(7)
    for _ in range(2000):
        n = rng.randint(0, 10**13)
        s = f"{n:,}".replace(",", ".")
        assert money.parse_amount(s, "VND").value == n


# ── Bút toán kép ─────────────────────────────────────────────────
def _lines(d="1000000", c="1000000"):
    return [{"account_code": "1121", "debit": d}, {"account_code": "131", "credit": c}]


def test_unbalanced_entry_rejected(env):
    from modules.accounting.engine import journal

    ctx = new_ctx()
    with pytest.raises(journal.JournalError) as e:
        journal.create(ctx, ctx.org_id, "2026-03-01", "x", _lines("1000000", "999999"), source="test", idempotency_key="k1")
    assert any("≠" in d for d in e.value.details)


def test_entry_rules(env):
    from modules.accounting.engine import journal

    ctx = new_ctx()
    bad = [
        [{"account_code": "1121", "debit": "100", "credit": "100"}, {"account_code": "131", "credit": "0"}],  # cả Nợ và Có
        [{"account_code": "9999", "debit": "100"}, {"account_code": "131", "credit": "100"}],  # TK không tồn tại
        [{"account_code": "112", "debit": "100"}, {"account_code": "131", "credit": "100"}],  # TK tổng hợp
        [{"account_code": "1121", "debit": "-100"}, {"account_code": "131", "credit": "-100"}],  # âm
        [{"account_code": "1121", "debit": "100.5"}, {"account_code": "131", "credit": "100.5"}],  # VND có số lẻ
    ]
    for i, lines in enumerate(bad):
        with pytest.raises(journal.JournalError):
            journal.create(ctx, ctx.org_id, "2026-03-01", "x", lines, source="test", idempotency_key=f"b{i}")


def test_balance_property_random(env):
    """Tính chất: mọi bút toán sinh ngẫu nhiên đã cân thì được nhận; lệch 1 đồng thì bị từ chối."""
    from modules.accounting.engine import journal

    ctx = new_ctx()
    rng = random.Random(42)
    accounts = ["1111", "1121", "131", "1331", "156", "331", "33311", "511", "642"]
    for i in range(60):
        n = rng.randint(1, 4)
        debits = [rng.randint(1, 10**9) for _ in range(n)]
        total = sum(debits)
        k = rng.randint(1, 3)
        cuts = sorted(rng.sample(range(1, total), k - 1)) if total > k and k > 1 else []
        credits = [b - a for a, b in zip([0] + cuts, cuts + [total])]
        lines = [{"account_code": rng.choice(accounts), "debit": str(d)} for d in debits] + \
                [{"account_code": rng.choice(accounts), "credit": str(c)} for c in credits]
        journal.create(ctx, ctx.org_id, "2026-03-01", "ok", lines, source="test", idempotency_key=f"p{i}")
        lines[-1]["credit"] = str(int(lines[-1]["credit"]) + 1)
        with pytest.raises(journal.JournalError):
            journal.create(ctx, ctx.org_id, "2026-03-01", "bad", lines, source="test", idempotency_key=f"q{i}")


def test_idempotent_no_duplicate_posting(env):
    from modules.accounting import db
    from modules.accounting.engine import journal

    ctx = new_ctx()
    a, created1 = journal.create(ctx, ctx.org_id, "2026-03-01", "x", _lines(), source="t", idempotency_key="same")
    b, created2 = journal.create(ctx, ctx.org_id, "2026-03-01", "x", _lines(), source="t", idempotency_key="same")
    assert a == b and created1 and not created2
    assert db.one("SELECT count(*) n FROM journal_entries WHERE org_id=?", (ctx.org_id,))["n"] == 1


def _second_user(ctx, email="approver@x.com", roles=("APPROVER",)):
    from modules.accounting import security

    admin = security.context(ctx.org_id, ctx.user)
    security.set_member(admin, email, list(roles))
    return security.context(ctx.org_id, email)


def test_no_posting_without_approval_and_sod(env):
    from modules.accounting import db
    from modules.accounting.engine import journal
    from modules.accounting.security import Forbidden

    ctx = new_ctx()  # ADMIN, ACCOUNTANT, REVIEWER, APPROVER
    eid, _ = journal.create(ctx, ctx.org_id, "2026-03-05", "x", _lines(), source="t", idempotency_key="e1")
    assert db.one("SELECT count(*) n FROM ledger_entries WHERE org_id=?", (ctx.org_id,))["n"] == 0
    aid = journal.request_post(ctx, eid)
    with pytest.raises(Forbidden):  # cùng người tạo/yêu cầu không được tự duyệt
        journal.approve(ctx, aid)
    viewer = _second_user(ctx, "viewer@x.com", ("VIEWER",))
    with pytest.raises(Forbidden):
        viewer.require("approve")
    approver = _second_user(ctx)
    journal.approve(approver, aid)
    assert db.one("SELECT status FROM journal_entries WHERE id=?", (eid,))["status"] == "POSTED"
    tb = journal.trial_balance(ctx.org_id)
    assert tb["balanced"] and tb["total_debit"] == "1000000"


def test_changed_after_request_cannot_be_approved(env):
    from modules.accounting.engine import journal

    ctx = new_ctx()
    eid, _ = journal.create(ctx, ctx.org_id, "2026-03-05", "x", _lines(), source="t", idempotency_key="e1")
    aid = journal.request_post(ctx, eid)
    journal.update_draft(ctx, eid, lines=_lines("2000000", "2000000"))  # sửa sau khi yêu cầu → yêu cầu cũ bị huỷ
    with pytest.raises(journal.JournalError):
        journal.approve(_second_user(ctx), aid)


def test_locked_period_rejected(env):
    from modules.accounting.engine import journal

    ctx = new_ctx()
    p = journal.ensure_period(ctx.org_id, "2026-02-10")
    journal.lock_period(ctx, p["id"])
    eid, _ = journal.create(ctx, ctx.org_id, "2026-02-10", "x", _lines(), source="t", idempotency_key="e1")
    aid = journal.request_post(ctx, eid)
    with pytest.raises(journal.JournalError) as e:
        journal.approve(_second_user(ctx), aid)
    assert e.value.code == "period_locked"


def test_posted_entry_immutable_and_reversal(env):
    from modules.accounting import db
    from modules.accounting.engine import journal

    ctx = new_ctx()
    approver = _second_user(ctx)
    eid, _ = journal.create(ctx, ctx.org_id, "2026-03-05", "x", _lines(), source="t", idempotency_key="e1")
    journal.approve(approver, journal.request_post(ctx, eid))
    c = db.conn()
    for sql in ("UPDATE journal_lines SET debit='1' WHERE entry_id=?", "DELETE FROM journal_lines WHERE entry_id=?",
                "DELETE FROM journal_entries WHERE id=?", "UPDATE journal_entries SET description='hack' WHERE id=?",
                "UPDATE ledger_entries SET debit='1' WHERE entry_id=?", "DELETE FROM ledger_entries WHERE entry_id=?"):
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(sql, (eid,))
    with pytest.raises(journal.JournalError):
        journal.update_draft(ctx, eid, description="sửa")
    rid = journal.reverse(ctx, eid, "ghi nhầm")
    journal.approve(approver, journal.request_post(ctx, rid))
    assert db.one("SELECT status FROM journal_entries WHERE id=?", (eid,))["status"] == "REVERSED"
    tb = journal.trial_balance(ctx.org_id)
    assert all(r["balance"] == "0" for r in tb["rows"])
    assert db.one("SELECT count(*) n FROM ledger_entries WHERE org_id=?", (ctx.org_id,))["n"] == 4  # lịch sử còn nguyên


def test_coa_seeded_and_marked_unverified(env):
    from modules.accounting import db
    from modules.accounting.engine import rules

    ctx = new_ctx()
    rows = db.all_("SELECT code, verification, regime FROM accounts WHERE org_id=?", (ctx.org_id,))
    assert {"111", "1121", "131", "331", "511", "642", "911"} <= {r["code"] for r in rows}
    assert {r["verification"] for r in rows} == {"UNVERIFIED_APPENDIX_II"}
    assert rules.get("R-COA-TT99").implementation_status == "NEEDS_EXPERT_REVIEW"
    assert all(r["legal_source"] and r["validation_test"] for r in rules.as_dicts())


# ── Nhật ký kiểm toán ────────────────────────────────────────────
def test_audit_chain_tamper_evident(env):
    from modules.accounting import audit, db

    ctx = new_ctx()
    audit.record(ctx.org_id, ctx.user, "x.test", "t", "1", password="secret", note="ok")
    ok, bad, n = audit.verify()
    assert ok and n >= 2
    ev = audit.list_events(ctx.org_id)[0]
    assert ev["details"]["password"] == "[redacted]"
    c = db.conn()
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE audit_events SET actor='x'")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("DELETE FROM audit_events")
    # Kẻ có quyền ghi file DB bỏ trigger rồi sửa → verify phát hiện
    c.execute("DROP TRIGGER audit_no_update")
    c.execute("UPDATE audit_events SET details_json='{}' WHERE seq=(SELECT max(seq) FROM audit_events)")
    ok, bad, _ = audit.verify()
    assert not ok and bad is not None


def test_original_files_cannot_be_deleted(env, golden):
    from modules.accounting import db, storage

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / "inv_purchase_101.xml"])
    f = db.one("SELECT * FROM files WHERE id=?", (ids[0],))
    with pytest.raises(sqlite3.IntegrityError):
        db.conn().execute("DELETE FROM files WHERE id=?", (ids[0],))
    with pytest.raises(sqlite3.IntegrityError):
        db.conn().execute("UPDATE files SET sha256='x' WHERE id=?", (ids[0],))
    assert storage.verify(f["storage_path"], f["sha256"])
    with pytest.raises(PermissionError):
        open(storage.abspath(f["storage_path"]), "ab").close()  # bản gốc chỉ-đọc


# ── Đối soát & trùng lặp trên golden dataset ─────────────────────
def test_reconciliation_golden(env, golden, expected):
    from modules.accounting import db
    from modules.accounting.engine import reconcile

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / "sao_ke_vcb_032026.xlsx", golden / "so_tien_gui_032026.xlsx"])
    bank = db.all_("SELECT id, txn_date date, amount, reference, description, counterparty FROM bank_transactions WHERE org_id=?", (ctx.org_id,))
    book = db.all_("SELECT id, entry_date date, amount, doc_no reference, description, counterparty FROM imported_entries WHERE org_id=?", (ctx.org_id,))
    assert len(bank) == 10 and len(book) == 12
    matches, summ = reconcile.reconcile(bank, book, 3)
    by = {}
    for m in matches:
        key = m["status"] if m["status"] != "UNMATCHED" else ("UNMATCHED_bank" if m["bank"] else "UNMATCHED_book")
        by[key] = by.get(key, 0) + 1
    exp = {k: v for k, v in expected["reconciliation"].items() if k != "notes"}
    assert by == {k: v for k, v in exp.items() if v}
    # Không tự chọn: nhóm AMBIGUOUS giữ nguyên cả hai bút toán 5.000.000
    amb = next(m for m in matches if m["status"] == "AMBIGUOUS")
    assert len(amb["book"]) == 2
    # Chênh lệch chỉ báo cáo, không có bút toán nào được tạo
    assert db.one("SELECT count(*) n FROM journal_entries WHERE org_id=?", (ctx.org_id,))["n"] == 0
    assert Decimal(summ["difference"]) == Decimal(summ["bank_total"]) - Decimal(summ["book_total"])


def test_same_amount_is_not_duplicate(env, golden):
    from modules.accounting import db
    from modules.accounting.engine import duplicates

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / n for n in ("inv_purchase_101.xml", "inv_purchase_105_suspect.xml",
                                                "inv_purchase_203_same_amount.xml", "inv_sale_011.xml",
                                                "inv_sale_011_copy.xml", "inv_sale_011.pdf")])
    groups = duplicates.detect(ctx.org_id, ids)
    num = {r["id"]: r["number"] for r in db.all_("SELECT id, number FROM invoices WHERE org_id=?", (ctx.org_id,))}
    dup = [g for g in groups if g["type"] == "INVOICE_DUPLICATE"]
    assert len(dup) == 1 and len(dup[0]["invoice_ids"]) == 3  # XML + bản sao định dạng khác + PDF
    sus = [g for g in groups if g["type"] == "INVOICE_SUSPECTED"]
    assert len(sus) == 1 and {num[i] for i in sus[0]["invoice_ids"]} == {"0000101", "0000105"}
    flagged = {num[i] for g in groups for i in g.get("invoice_ids", [])}
    assert "0000203" not in flagged  # cùng 4.675.000 nhưng khác người bán, khác ngày


def test_double_payment_suspected(env, golden):
    from modules.accounting.engine import duplicates

    ctx = new_ctx()
    _, ids = ingest(ctx, [golden / "sao_ke_vcb_032026.xlsx"])
    groups = duplicates.detect(ctx.org_id, ids)
    dp = [g for g in groups if g["type"] == "SUSPECTED_DOUBLE_PAYMENT"]
    assert len(dp) == 1 and dp[0]["status"] == "NEEDS_REVIEW"


def test_tenant_isolation_engine(env, golden):
    """Mỗi tổ chức một FILE database: dữ liệu A không tồn tại trong file của B; ghi nhầm database bị chặn."""
    import sqlite3

    from modules.accounting import db, security
    from modules.accounting.engine import analysis, duplicates

    a = new_ctx("A", "a@x.com")
    b = new_ctx("B", "b@x.com")
    ingest(a, [golden / "inv_purchase_101.xml"])
    ingest(b, [golden / "inv_purchase_105_suspect.xml"])
    assert db.tenant_path(a.org_id) != db.tenant_path(b.org_id)
    with db.use_org(a.org_id):
        assert len(analysis.invoices(a.org_id)) == 1
    with db.use_org(b.org_id):
        assert len(analysis.invoices(b.org_id)) == 1
        assert analysis.invoices(a.org_id) == []  # dữ liệu A không có trong file của B
        assert not [g for g in duplicates.detect(b.org_id) if g["type"] == "INVOICE_SUSPECTED"]
        with pytest.raises(sqlite3.IntegrityError):  # trigger: file của B không nhận dòng của A
            db.conn().execute("INSERT INTO conversations (id, org_id, created_by, title, created_at, updated_at) VALUES ('x', ?, 'a@x.com', 't', 0, 0)", (a.org_id,))
    raw = sqlite3.connect(db.tenant_path(b.org_id))
    assert raw.execute("SELECT count(*) FROM invoices WHERE org_id=?", (a.org_id,)).fetchone()[0] == 0
    assert raw.execute("SELECT count(*) FROM orgs").fetchone()[0] == 1
    raw.close()
    with db.central():  # danh bạ trung tâm không chứa dữ liệu nghiệp vụ
        assert db.one("SELECT count(*) n FROM invoices")["n"] == 0 and db.one("SELECT count(*) n FROM orgs")["n"] == 2
    with pytest.raises(security.NotFound):
        security.context(a.org_id, "b@x.com")


def test_backup_and_restore_verification(env, golden):
    import os
    import stat

    from modules.accounting import backup

    ctx = new_ctx()
    ingest(ctx, [golden / "inv_purchase_101.xml", golden / "inv_sale_011.pdf"])
    out = backup.create(env / "bk")
    r = backup.verify(out)
    assert r["ok"], r["problems"]
    assert r["files"] == 2 and r["audit_events"] >= 3
    victim = next((out / "objects").rglob("*"), None)
    victim = next(p for p in (out / "objects").rglob("*") if p.is_file())
    os.chmod(victim, stat.S_IWRITE)
    victim.write_bytes(b"tampered")
    bad = backup.verify(out)
    assert not bad["ok"] and any("không khớp" in p or "hỏng" in p for p in bad["problems"])
