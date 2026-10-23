"""
Bút toán kép: đề xuất → yêu cầu ghi sổ → phê duyệt (người khác) → ghi sổ cái (append-only).

Bất biến:
- Tổng Nợ = tổng Có (Decimal, theo đồng tiền hạch toán), mỗi dòng chỉ Nợ hoặc Có, không âm.
- Tài khoản tồn tại và là tài khoản chi tiết; kỳ kế toán chưa khoá.
- Idempotency: (org_id, idempotency_key) duy nhất → đề xuất lại không tạo bút toán trùng.
- Bút toán đã ghi sổ không sửa/xoá (trigger DB); sửa bằng bút toán đảo (Luật Kế toán Điều 27).
- Agent chỉ được đề xuất. Ghi sổ chỉ xảy ra trong approve() bởi người có vai trò APPROVER,
  khác người yêu cầu và người tạo, và nội dung không đổi kể từ lúc yêu cầu (payload_hash).
"""

import hashlib
from datetime import date

from .. import audit, db, money
from ..security import Forbidden, self_approval


class JournalError(Exception):
    def __init__(self, code, msg, details=None):
        super().__init__(msg)
        self.code = code
        self.details = details or []


def check_lines(c, org_id, lines, currency="VND"):
    """Kiểm tra xác định. Trả về list lỗi (rỗng = hợp lệ)."""
    errs = []
    if len(lines) < 2:
        errs.append("Bút toán cần ít nhất 2 dòng")
    td = tc = money.ZERO
    for i, ln in enumerate(lines, start=1):
        try:
            d = money.to_decimal(ln.get("debit") or "0")
            cr = money.to_decimal(ln.get("credit") or "0")
        except Exception:
            errs.append(f"Dòng {i}: số tiền không hợp lệ")
            continue
        if d < 0 or cr < 0:
            errs.append(f"Dòng {i}: số tiền âm")
        if (d > 0) == (cr > 0):
            errs.append(f"Dòng {i}: phải có đúng một trong Nợ hoặc Có")
        if money.q(d, currency) != d or money.q(cr, currency) != cr:
            errs.append(f"Dòng {i}: số lẻ vượt độ chính xác của {currency}")
        td += d
        tc += cr
        acc = c.execute("SELECT postable FROM accounts WHERE org_id=? AND code=?",
                        (org_id, str(ln.get("account_code") or ""))).fetchone()
        if not acc:
            errs.append(f"Dòng {i}: tài khoản {ln.get('account_code')} không có trong hệ thống tài khoản")
        elif not acc[0]:
            errs.append(f"Dòng {i}: tài khoản {ln.get('account_code')} là tài khoản tổng hợp, cần tài khoản chi tiết")
    if td != tc:
        errs.append(f"Tổng Nợ {money.fmt(td)} ≠ tổng Có {money.fmt(tc)}")
    if td == 0:
        errs.append("Bút toán không có giá trị")
    return errs


def _period(c, org_id, d, create=True):
    month_start = d[:7] + "-01"
    row = c.execute("SELECT * FROM periods WHERE org_id=? AND start_date<=? AND end_date>=?", (org_id, d, d)).fetchone()
    if row or not create:
        return dict(row) if row else None
    y, m = int(d[:4]), int(d[5:7])
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    end = date.fromordinal(nxt.toordinal() - 1).isoformat()
    pid = db.new_id()
    db.insert(c, "periods", {"id": pid, "org_id": org_id, "start_date": month_start, "end_date": end,
                             "status": "open", "locked_by": None, "locked_at": None})
    return {"id": pid, "status": "open", "start_date": month_start, "end_date": end}


def create(ctx_or_actor, org_id, entry_date, description, lines, *, source, source_refs=(), idempotency_key,
           currency="VND", task_id=None, status="PROPOSED"):
    """Tạo bút toán DRAFT/PROPOSED (không ghi sổ). Idempotent theo idempotency_key."""
    actor = getattr(ctx_or_actor, "user", ctx_or_actor)
    try:
        date.fromisoformat(entry_date)
    except (TypeError, ValueError) as e:
        raise JournalError("bad_date", "Ngày bút toán không hợp lệ") from e
    with db.tx() as c:
        ex = c.execute("SELECT id FROM journal_entries WHERE org_id=? AND idempotency_key=?",
                       (org_id, idempotency_key)).fetchone()
        if ex:
            return ex[0], False
        errs = check_lines(c, org_id, lines, currency)
        if errs:
            raise JournalError("invalid_entry", "Bút toán không hợp lệ", errs)
        eid = db.new_id()
        db.insert(c, "journal_entries", {
            "id": eid, "org_id": org_id, "entry_date": entry_date, "description": description[:500],
            "currency": currency, "status": status, "source": source, "source_refs_json": db.dumps(list(source_refs)),
            "task_id": task_id, "reversal_of": None, "idempotency_key": idempotency_key, "version": 1,
            "created_by": actor, "created_at": db.now(), "posted_by": None, "posted_at": None,
        })
        for i, ln in enumerate(lines, start=1):
            db.insert(c, "journal_lines", {
                "id": db.new_id(), "org_id": org_id, "entry_id": eid, "line_no": i,
                "account_code": str(ln["account_code"]),
                "debit": money.fmt(money.to_decimal(ln.get("debit") or "0")),
                "credit": money.fmt(money.to_decimal(ln.get("credit") or "0")),
                "counterparty": ln.get("counterparty"), "memo": (ln.get("memo") or "")[:300],
                "evidence_json": db.dumps(ln.get("evidence") or []),
            })
        audit.log(c, org_id, actor, "journal.propose", "journal_entry", eid, source=source,
                  idempotency_key=idempotency_key, lines=len(lines))
    return eid, True


def get(org_id, entry_id):
    e = db.one("SELECT * FROM journal_entries WHERE id=? AND org_id=?", (entry_id, org_id))
    if not e:
        return None
    e["lines"] = db.all_("SELECT * FROM journal_lines WHERE entry_id=? AND org_id=? ORDER BY line_no", (entry_id, org_id))
    for ln in e["lines"]:
        ln["evidence"] = db.loads(ln.pop("evidence_json"), [])
    e["source_refs"] = db.loads(e.pop("source_refs_json"), [])
    return e


def payload_hash(e):
    body = db.dumps({
        "date": e["entry_date"], "desc": e["description"], "cur": e["currency"], "v": e["version"],
        "lines": [(ln["account_code"], ln["debit"], ln["credit"]) for ln in e["lines"]],
    })
    return hashlib.sha256(body.encode()).hexdigest()


def update_draft(ctx, entry_id, description=None, lines=None):
    ctx.require("edit_draft")
    with db.tx() as c:
        e = get(ctx.org_id, entry_id)
        if not e:
            raise JournalError("not_found", "Không có bút toán")
        if e["status"] not in ("DRAFT", "PROPOSED"):
            raise JournalError("immutable", f"Bút toán ở trạng thái {e['status']} không sửa được")
        if lines is not None:
            errs = check_lines(c, ctx.org_id, lines, e["currency"])
            if errs:
                raise JournalError("invalid_entry", "Bút toán không hợp lệ", errs)
            c.execute("DELETE FROM journal_lines WHERE entry_id=? AND org_id=?", (entry_id, ctx.org_id))
            for i, ln in enumerate(lines, start=1):
                db.insert(c, "journal_lines", {
                    "id": db.new_id(), "org_id": ctx.org_id, "entry_id": entry_id, "line_no": i,
                    "account_code": str(ln["account_code"]),
                    "debit": money.fmt(money.to_decimal(ln.get("debit") or "0")),
                    "credit": money.fmt(money.to_decimal(ln.get("credit") or "0")),
                    "counterparty": ln.get("counterparty"), "memo": (ln.get("memo") or "")[:300],
                    "evidence_json": db.dumps(ln.get("evidence") or []),
                })
        c.execute("UPDATE journal_entries SET description=coalesce(?, description), version=version+1 WHERE id=? AND org_id=?",
                  (description, entry_id, ctx.org_id))
        # Yêu cầu ghi sổ cũ không còn hiệu lực vì nội dung đã đổi
        c.execute("UPDATE approvals SET status='CANCELLED', reason='bút toán đã được sửa' "
                  "WHERE org_id=? AND target_id=? AND status='PENDING'", (ctx.org_id, entry_id))
        audit.log(c, ctx.org_id, ctx.user, "journal.edit", "journal_entry", entry_id, lines=len(lines or []))


def request_post(ctx, entry_id):
    ctx.require("request_commit")
    with db.tx() as c:
        e = get(ctx.org_id, entry_id)
        if not e:
            raise JournalError("not_found", "Không có bút toán")
        if e["status"] != "PROPOSED":
            raise JournalError("bad_state", f"Chỉ bút toán PROPOSED mới yêu cầu ghi sổ được (hiện: {e['status']})")
        errs = check_lines(c, ctx.org_id, e["lines"], e["currency"])
        if errs:
            raise JournalError("invalid_entry", "Bút toán không hợp lệ", errs)
        pending = c.execute("SELECT id FROM approvals WHERE org_id=? AND target_id=? AND status='PENDING'",
                            (ctx.org_id, entry_id)).fetchone()
        if pending:
            return pending[0]
        aid = db.new_id()
        db.insert(c, "approvals", {
            "id": aid, "org_id": ctx.org_id, "action": "COMMIT_ACCOUNTING", "target_type": "journal_entry",
            "target_id": entry_id, "payload_hash": payload_hash(e), "status": "PENDING",
            "requested_by": ctx.user, "requested_at": db.now(), "decided_by": None, "decided_at": None, "reason": None,
        })
        audit.log(c, ctx.org_id, ctx.user, "approval.request", "journal_entry", entry_id, approval_id=aid)
    return aid


def approve(ctx, approval_id, confirm_self=False):
    """Phê duyệt và ghi sổ trong cùng một giao dịch. Kiểm tra lại mọi bất biến tại thời điểm ghi."""
    ctx.require("approve")
    self_mode = self_approval(ctx)
    with db.tx() as c:
        a = c.execute("SELECT * FROM approvals WHERE id=? AND org_id=?", (approval_id, ctx.org_id)).fetchone()
        if not a:
            raise JournalError("not_found", "Không có yêu cầu phê duyệt")
        a = dict(a)
        if a["status"] != "PENDING":
            raise JournalError("bad_state", f"Yêu cầu đã ở trạng thái {a['status']}")
        e = get(ctx.org_id, a["target_id"])
        is_self = ctx.user in (a["requested_by"], e["created_by"])
        if is_self and not self_mode:
            raise Forbidden("Người phê duyệt phải khác người tạo và người yêu cầu (phân tách nhiệm vụ)", "sod")
        if is_self and self_mode == "single_member" and not confirm_self:
            raise Forbidden("Tổ chức chỉ có một thành viên nên bạn tự phê duyệt bút toán của chính mình — cần xác nhận", "confirm_self")
        if e["status"] != "PROPOSED":
            raise JournalError("bad_state", f"Bút toán đang ở trạng thái {e['status']}")
        if payload_hash(e) != a["payload_hash"]:
            raise JournalError("changed", "Bút toán đã bị thay đổi sau khi yêu cầu phê duyệt")
        errs = check_lines(c, ctx.org_id, e["lines"], e["currency"])
        if errs:
            raise JournalError("invalid_entry", "Bút toán không hợp lệ", errs)
        p = _period(c, ctx.org_id, e["entry_date"])
        if p["status"] == "locked":
            raise JournalError("period_locked", f"Kỳ {p['start_date']}…{p['end_date']} đã khoá sổ")
        ts = db.now()
        for ln in e["lines"]:
            db.insert(c, "ledger_entries", {
                "id": db.new_id(), "org_id": ctx.org_id, "entry_id": e["id"], "line_id": ln["id"],
                "entry_date": e["entry_date"], "account_code": ln["account_code"],
                "debit": ln["debit"], "credit": ln["credit"], "posted_at": ts,
            })
        c.execute("UPDATE journal_entries SET status='POSTED', posted_by=?, posted_at=? WHERE id=? AND org_id=?",
                  (ctx.user, ts, e["id"], ctx.org_id))
        if e["reversal_of"]:
            c.execute("UPDATE journal_entries SET status='REVERSED' WHERE id=? AND org_id=? AND status='POSTED'",
                      (e["reversal_of"], ctx.org_id))
        c.execute("UPDATE approvals SET status='EXECUTED', decided_by=?, decided_at=? WHERE id=?",
                  (ctx.user, ts, approval_id))
        audit.log(c, ctx.org_id, ctx.user, "journal.post", "journal_entry", e["id"], approval_id=approval_id,
                  payload_hash=a["payload_hash"], requested_by=a["requested_by"],
                  self_approved=is_self, self_approval_basis=self_mode if is_self else None)
    return e["id"]


def reject(ctx, approval_id, reason):
    ctx.require("approve")
    with db.tx() as c:
        a = c.execute("SELECT * FROM approvals WHERE id=? AND org_id=?", (approval_id, ctx.org_id)).fetchone()
        if not a or a["status"] != "PENDING":
            raise JournalError("bad_state", "Yêu cầu không còn chờ duyệt")
        c.execute("UPDATE approvals SET status='REJECTED', decided_by=?, decided_at=?, reason=? WHERE id=?",
                  (ctx.user, db.now(), (reason or "")[:500], approval_id))
        audit.log(c, ctx.org_id, ctx.user, "approval.reject", a["target_type"], a["target_id"], reason=reason)


def reverse(ctx, entry_id, reason):
    """Tạo bút toán đảo (PROPOSED) cho bút toán đã ghi sổ; vẫn phải qua phê duyệt để ghi."""
    ctx.require("edit_draft")
    e = get(ctx.org_id, entry_id)
    if not e or e["status"] != "POSTED":
        raise JournalError("bad_state", "Chỉ đảo được bút toán đã ghi sổ")
    lines = [{"account_code": ln["account_code"], "debit": ln["credit"], "credit": ln["debit"],
              "counterparty": ln["counterparty"], "memo": f"Đảo: {ln['memo'] or ''}"} for ln in e["lines"]]
    eid, _ = create(ctx, ctx.org_id, date.today().isoformat(), f"Bút toán đảo của {entry_id[:8]}: {reason}"[:500],
                    lines, source="reversal", source_refs=[{"journal_entry": entry_id}],
                    idempotency_key=f"reversal:{entry_id}", currency=e["currency"])
    with db.tx() as c:
        c.execute("UPDATE journal_entries SET reversal_of=? WHERE id=? AND org_id=?", (entry_id, eid, ctx.org_id))
    return eid


def lock_period(ctx, period_id):
    ctx.require("lock_period")
    with db.tx() as c:
        n = c.execute("UPDATE periods SET status='locked', locked_by=?, locked_at=? WHERE id=? AND org_id=? AND status='open'",
                      (ctx.user, db.now(), period_id, ctx.org_id)).rowcount
        if not n:
            raise JournalError("bad_state", "Kỳ không tồn tại hoặc đã khoá")
        audit.log(c, ctx.org_id, ctx.user, "period.lock", "period", period_id)


def ensure_period(org_id, d):
    with db.tx() as c:
        return _period(c, org_id, d)


def trial_balance(org_id, as_of=None):
    sql = "SELECT account_code, debit, credit FROM ledger_entries WHERE org_id=?"
    args = [org_id]
    if as_of:
        sql += " AND entry_date<=?"
        args.append(as_of)
    acc = {}
    for r in db.all_(sql, args):
        a = acc.setdefault(r["account_code"], [money.ZERO, money.ZERO])
        a[0] += money.D(r["debit"])
        a[1] += money.D(r["credit"])
    names = {r["code"]: r["name"] for r in db.all_("SELECT code, name FROM accounts WHERE org_id=?", (org_id,))}
    rows = [{"account": k, "name": names.get(k, ""), "debit": money.fmt(v[0]), "credit": money.fmt(v[1]),
             "balance": money.fmt(v[0] - v[1])} for k, v in sorted(acc.items())]
    td = money.sum_(money.D(r["debit"]) for r in rows)
    tc = money.sum_(money.D(r["credit"]) for r in rows)
    return {"rows": rows, "total_debit": money.fmt(td), "total_credit": money.fmt(tc), "balanced": td == tc}
