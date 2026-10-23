"""
Đề xuất định khoản từ hoá đơn — xác định, có điều kiện, không tự bịa.

- Hoá đơn bán ra (MST người bán = MST tổ chức): Nợ 131 / Có 511 (tiền hàng) / Có 33311 (thuế).
  Đây là đề xuất có điều kiện: doanh thu khác (515, 711…) cần kế toán sửa trước khi ghi sổ.
- Hoá đơn mua vào: Nợ <TK chi phí/hàng tồn> / Nợ 1331 / Có 331. TK Nợ CHỈ lấy từ quy tắc nội bộ
  đã được phê duyệt (account_rules ACTIVE) hoặc từ câu trả lời của người dùng cho hoá đơn đó.
  Không có → NEEDS_INPUT kèm câu hỏi cụ thể. Không suy đoán bằng AI.
- Hoá đơn ngoại tệ: chỉ quy đổi bằng tỷ giá ghi trên hoá đơn (TGia); thiếu → NEEDS_EVIDENCE.
- Hoá đơn chưa qua kiểm tra (CONFLICTED / NEEDS_EVIDENCE / NEEDS_REVIEW) → không đề xuất.
"""

from .. import audit, db, money, settings
from ..extract.base import fold, norm_tax_id
from ..security import Forbidden
from . import journal

USABLE = ("VERIFIED", "VALID_EXTRACTED", "REVIEWED")
PURCHASE_ACCOUNT_CHOICES = [
    ("156", "Hàng hoá"), ("152", "Nguyên liệu, vật liệu"), ("153", "Công cụ, dụng cụ"),
    ("642", "Chi phí quản lý doanh nghiệp"), ("641", "Chi phí bán hàng"), ("242", "Chi phí trả trước"),
    ("211", "Tài sản cố định hữu hình"), ("632", "Giá vốn hàng bán"), ("811", "Chi phí khác"),
]


def active_rule_for(org_id, inv, line_text=""):
    rules = db.all_("SELECT * FROM account_rules WHERE org_id=? AND status='ACTIVE' ORDER BY decided_at", (org_id,))
    tax = norm_tax_id(inv.get("seller_tax_id"))
    for r in rules:
        if r["match_type"] == "seller_tax_id" and tax and norm_tax_id(r["match_value"]) == tax:
            return r
    text = fold(line_text)
    for r in rules:
        if r["match_type"] == "keyword" and fold(r["match_value"]) and fold(r["match_value"]) in text:
            return r
    return None


def propose_rule(ctx, match_type, match_value, account_code, note="", source=None):
    ctx.require("edit_draft")
    acc = db.one("SELECT postable FROM accounts WHERE org_id=? AND code=?", (ctx.org_id, str(account_code)))
    if not acc or not acc["postable"]:
        raise journal.JournalError("bad_account", f"Tài khoản {account_code} không hợp lệ")
    rid = db.new_id()
    with db.tx() as c:
        db.insert(c, "account_rules", {
            "id": rid, "org_id": ctx.org_id, "match_type": match_type, "match_value": str(match_value)[:200],
            "account_code": str(account_code), "note": (note or "")[:300], "status": "PROPOSED",
            "proposed_by": ctx.user, "proposed_at": db.now(), "decided_by": None, "decided_at": None,
            "source_json": db.dumps(source or {}),
        })
        audit.log(c, ctx.org_id, ctx.user, "rule.propose", "account_rule", rid, match_type=match_type,
                  match_value=match_value, account=account_code)
    return rid


def decide_rule(ctx, rule_id, approve, reason=""):
    if not (ctx.can("approve") or ctx.can("manage")):
        raise Forbidden("Cần vai trò APPROVER hoặc ADMIN để duyệt quy tắc hạch toán", "no_role")
    with db.tx() as c:
        r = c.execute("SELECT * FROM account_rules WHERE id=? AND org_id=?", (rule_id, ctx.org_id)).fetchone()
        if not r or r["status"] != "PROPOSED":
            raise journal.JournalError("bad_state", "Quy tắc không ở trạng thái chờ duyệt")
        if r["proposed_by"] == ctx.user and not settings.get()["allow_self_approval"]:
            raise Forbidden("Quy tắc phải được người khác duyệt", "sod")
        status = "ACTIVE" if approve else "REJECTED"
        c.execute("UPDATE account_rules SET status=?, decided_by=?, decided_at=? WHERE id=?",
                  (status, ctx.user, db.now(), rule_id))
        audit.log(c, ctx.org_id, ctx.user, f"rule.{status.lower()}", "account_rule", rule_id, reason=reason)


def _vnd(amount, inv):
    cur = (inv.get("currency") or "VND").upper()
    if cur == "VND":
        return money.D(amount), None
    rate = money.D(inv.get("fx_rate")) if inv.get("fx_rate") else None
    if not rate:
        return None, f"Hoá đơn {cur} không có tỷ giá trên chứng từ"
    return money.q(money.D(amount) * rate, "VND"), f"quy đổi {cur}→VND theo tỷ giá {inv['fx_rate']} ghi trên hoá đơn"


def propose_for_invoices(ctx, invoice_ids, task_id=None, answers=None):
    """
    answers: {invoice_id: account_code} — câu trả lời của người dùng cho từng hoá đơn (chỉ áp dụng hoá đơn đó).
    Trả về {"proposed": [...], "needs_input": [...], "skipped": [...]}.
    """
    answers = answers or {}
    out = {"proposed": [], "needs_input": [], "skipped": []}
    org = db.one("SELECT * FROM orgs WHERE id=?", (ctx.org_id,))
    for iid in invoice_ids:
        inv = db.one("SELECT * FROM invoices WHERE id=? AND org_id=?", (iid, ctx.org_id))
        if not inv:
            continue
        label = f"{inv['series'] or ''}/{inv['number'] or '?'} ({inv['seller_name'] or '?'})"
        if inv["status"] not in USABLE:
            out["skipped"].append({"invoice_id": iid, "invoice": label, "reason": f"hoá đơn đang {inv['status']} — cần xử lý kiểm tra trước"})
            continue
        if inv["invoice_kind"] != "original":
            out["needs_input"].append({"invoice_id": iid, "invoice": label, "missing": ["xử lý hoá đơn điều chỉnh/thay thế"],
                                       "question": "Hoá đơn điều chỉnh/thay thế cần kế toán xác định bút toán điều chỉnh tương ứng với hoá đơn gốc."})
            continue
        direction = inv["direction"]
        if direction == "unknown" and org.get("tax_id"):
            from .validate import direction as _dir

            direction = _dir(inv, org["tax_id"])
        if direction not in ("sale", "purchase"):
            out["needs_input"].append({
                "invoice_id": iid, "invoice": label, "missing": ["mst_to_chuc" if not org.get("tax_id") else "chieu_hoa_don"],
                "question": "Chưa xác định được hoá đơn mua vào hay bán ra: hãy khai báo MST của tổ chức trong Cài đặt."
                if not org.get("tax_id") else "MST tổ chức không phải người bán cũng không phải người mua trên hoá đơn này."})
            continue
        sub, vat, total = money.D(inv["subtotal"]), money.D(inv["vat_amount"]), money.D(inv["total"])
        if total is None or sub is None or vat is None:
            out["needs_input"].append({"invoice_id": iid, "invoice": label, "missing": [k for k, v in (("subtotal", sub), ("vat_amount", vat), ("total", total)) if v is None],
                                       "question": "Hoá đơn thiếu tiền hàng/tiền thuế/tổng tiền — cần chứng từ đầy đủ."})
            continue
        sub_v, note1 = _vnd(sub, inv)
        vat_v, _ = _vnd(vat, inv)
        tot_v, _ = _vnd(total, inv)
        if sub_v is None:
            out["needs_input"].append({"invoice_id": iid, "invoice": label, "missing": ["fx_rate"], "question": note1})
            continue
        memo_fx = f" ({note1})" if note1 else ""
        if sub_v + vat_v != tot_v:
            # Quy đổi từng thành phần rồi làm tròn có thể lệch tổng quy đổi; công nợ lấy tổng thành phần và ghi rõ
            memo_fx += f" [chênh lệch làm tròn quy đổi {money.fmt(sub_v + vat_v - tot_v)} VND]"
            tot_v = sub_v + vat_v
        ev = [{"invoice_id": iid, "file_id": inv["file_id"]}]
        if direction == "sale":
            lines = [
                {"account_code": "131", "debit": tot_v, "counterparty": inv["buyer_name"], "memo": f"Phải thu theo HĐ {label}{memo_fx}", "evidence": ev},
                {"account_code": "511", "credit": sub_v, "memo": "Doanh thu bán hàng (đề xuất có điều kiện)", "evidence": ev},
            ]
            if vat_v:
                lines.append({"account_code": "33311", "credit": vat_v, "memo": "Thuế GTGT đầu ra", "evidence": ev})
            assumption = "Giả định doanh thu bán hàng và cung cấp dịch vụ (TK 511)"
        else:
            acct = answers.get(iid)
            rule = None
            if not acct:
                lines_text = " ".join(r["description"] or "" for r in db.all_(
                    "SELECT description FROM invoice_lines WHERE invoice_id=? AND org_id=?", (iid, ctx.org_id)))
                rule = active_rule_for(ctx.org_id, inv, lines_text)
                acct = rule["account_code"] if rule else None
            if not acct:
                out["needs_input"].append({
                    "invoice_id": iid, "invoice": label, "missing": ["tai_khoan_no"],
                    "question": f"Hoá đơn mua vào từ {inv['seller_name'] or inv['seller_tax_id']}: hàng hoá/dịch vụ này hạch toán vào tài khoản nào?",
                    "choices": [{"code": c, "name": n} for c, n in PURCHASE_ACCOUNT_CHOICES],
                    "hint": "Có thể lưu thành quy tắc cho người bán này (cần người khác phê duyệt).",
                })
                continue
            lines = [{"account_code": str(acct), "debit": sub_v, "counterparty": inv["seller_name"],
                      "memo": f"Mua theo HĐ {label}{memo_fx}", "evidence": ev}]
            if vat_v:
                lines.append({"account_code": "1331", "debit": vat_v, "memo": "Thuế GTGT đầu vào (cần đủ điều kiện khấu trừ)", "evidence": ev})
            lines.append({"account_code": "331", "credit": tot_v, "counterparty": inv["seller_name"], "memo": "Phải trả người bán", "evidence": ev})
            assumption = (f"TK {acct} theo quy tắc nội bộ đã duyệt" if rule else f"TK {acct} do người dùng chỉ định cho hoá đơn này")
        try:
            eid, created = journal.create(ctx, ctx.org_id, inv["issue_date"], f"HĐ {label} — {assumption}", lines,
                                          source="invoice", source_refs=[{"invoice_id": iid}],
                                          idempotency_key=f"invoice:{iid}:v1", task_id=task_id)
        except journal.JournalError as e:
            out["skipped"].append({"invoice_id": iid, "invoice": label, "reason": f"{e}: {'; '.join(e.details)}"})
            continue
        out["proposed"].append({"invoice_id": iid, "invoice": label, "entry_id": eid, "created": created,
                                "direction": direction, "assumption": assumption})
    audit.record(ctx.org_id, ctx.user, "journal.propose_batch", "task", task_id,
                 proposed=len(out["proposed"]), needs_input=len(out["needs_input"]), skipped=len(out["skipped"]))
    return out
