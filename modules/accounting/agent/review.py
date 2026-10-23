"""Hàng đợi kiểm duyệt (human-in-the-loop): mục mở theo (loại, đối tượng) duy nhất — chạy lại không tạo trùng."""

from .. import audit, db
from ..security import Forbidden


def open_item(run, kind, target_type, target_id, title, detail):
    org_id = run.ctx.org_id
    task_id = run.task["id"] if run.task else None
    with db.tx() as c:
        ex = c.execute("SELECT id, status FROM review_items WHERE org_id=? AND kind=? AND target_type=? AND target_id=?",
                       (org_id, kind, target_type, str(target_id)[:500])).fetchone()
        if ex:
            return ex[0]
        rid = db.new_id()
        db.insert(c, "review_items", {
            "id": rid, "org_id": org_id, "task_id": task_id, "kind": kind, "target_type": target_type,
            "target_id": str(target_id)[:500], "title": str(title)[:300], "detail_json": db.dumps(detail),
            "status": "OPEN", "created_at": db.now(), "resolved_by": None, "resolved_at": None, "resolution_json": None,
        })
    return rid


def list_items(ctx, status="OPEN", limit=200):
    rows = db.all_("SELECT * FROM review_items WHERE org_id=? AND status=? ORDER BY created_at DESC LIMIT ?",
                   (ctx.org_id, status, min(int(limit), 1000)))
    for r in rows:
        r["detail"] = db.loads(r.pop("detail_json"), {})
        r["resolution"] = db.loads(r.pop("resolution_json"), None)
    return rows


def resolve(ctx, item_id, action, note="", correction=None):
    """action: accept | dismiss | correct. Sửa giá trị → lưu feedback có provenance, không sửa chứng từ gốc."""
    if not (ctx.can("review") or ctx.can("edit_draft")):
        raise Forbidden("Cần vai trò REVIEWER hoặc ACCOUNTANT để xử lý mục kiểm duyệt", "no_role")
    if action not in ("accept", "dismiss", "correct"):
        raise ValueError("action không hợp lệ")
    with db.tx() as c:
        it = c.execute("SELECT * FROM review_items WHERE id=? AND org_id=?", (item_id, ctx.org_id)).fetchone()
        if not it:
            raise LookupError("Không có mục kiểm duyệt")
        if it["status"] != "OPEN":
            raise ValueError("Mục đã được xử lý")
        if action == "correct":
            corr = correction or {}
            db.insert(c, "feedback", {
                "id": db.new_id(), "org_id": ctx.org_id, "user_email": ctx.user, "target_type": it["target_type"],
                "target_id": it["target_id"], "field_name": str(corr.get("field") or "")[:120],
                "old_value": str(corr.get("old") or "")[:500], "new_value": str(corr.get("new") or "")[:500],
                "note": (note or "")[:1000], "status": "RECORDED", "created_at": db.now(),
            })
        if action == "accept" and it["target_type"] == "invoice" and it["kind"] == "invoice_check":
            # Người kiểm duyệt xác nhận hoá đơn sau khi xem bằng chứng → REVIEWED (vẫn giữ danh sách vấn đề)
            c.execute("UPDATE invoices SET status='REVIEWED' WHERE id=? AND org_id=? AND status IN ('NEEDS_REVIEW')",
                      (it["target_id"], ctx.org_id))
        c.execute("UPDATE review_items SET status=?, resolved_by=?, resolved_at=?, resolution_json=? WHERE id=?",
                  ("DISMISSED" if action == "dismiss" else "RESOLVED", ctx.user, db.now(),
                   db.dumps({"action": action, "note": note, "correction": correction}), item_id))
        audit.log(c, ctx.org_id, ctx.user, f"review.{action}", "review_item", item_id, kind=it["kind"], note=note)
