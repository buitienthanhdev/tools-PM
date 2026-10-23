"""
Phát hiện trùng lặp, phân biệt rõ:
- FILE_DUPLICATE: trùng hoàn toàn nội dung file (SHA-256).
- INVOICE_DUPLICATE: cùng khoá nghiệp vụ (MST người bán + mẫu số + ký hiệu + số) và cùng số tiền.
- INVOICE_KEY_CONFLICT: cùng khoá nghiệp vụ nhưng khác số tiền → CONFLICTED.
- INVOICE_SUSPECTED: khác số nhưng cùng người bán + ngày + tổng tiền → chỉ là nghi vấn, cần kiểm duyệt.
- ROW_DUPLICATE: cùng dòng sao kê/sổ (ngày, số tiền, tham chiếu, diễn giải) xuất hiện nhiều lần.
- SUSPECTED_DOUBLE_PAYMENT: chi cho cùng đối tượng, cùng số tiền, gần ngày, khác tham chiếu.
Không bao giờ coi hai hoá đơn là trùng chỉ vì cùng số tiền.
"""

from collections import defaultdict
from datetime import date

from .. import db, money
from ..extract.base import fold


def _days(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return None


def _scope_invoices(org_id, file_ids):
    rows = db.all_(
        """SELECT i.*, f.original_name file_name FROM cur_invoices i JOIN files f ON f.id=i.file_id
           WHERE i.org_id=?""", (org_id,))
    scope = None if file_ids is None else set(file_ids)
    return rows, (lambda r: scope is None or r["file_id"] in scope)


def detect(org_id, file_ids=None, tolerance_days=3, conversation_id=None):
    """conversation_id: chỉ coi là trùng file khi cùng nội dung được tải nhiều lần trong cùng hội thoại
    (tải lại file cũ ở phiên mới để hỏi tiếp không phải là trùng chứng từ)."""
    groups = []
    scope = None if file_ids is None else set(file_ids)  # [] = không có file nào trong phạm vi

    # 1. Trùng file
    for r in db.all_(
        """SELECT u.file_id, f.original_name, count(*) n, group_concat(u.original_name, ' | ') names
           FROM uploads u JOIN files f ON f.id=u.file_id
           WHERE u.org_id=? AND u.file_id IS NOT NULL AND (? IS NULL OR u.conversation_id=?)
           GROUP BY u.file_id HAVING n > 1""", (org_id, conversation_id, conversation_id)):
        if scope is not None and r["file_id"] not in scope:
            continue
        groups.append({"type": "FILE_DUPLICATE", "status": "DUPLICATE", "file_ids": [r["file_id"]],
                       "reason": f"Cùng nội dung (SHA-256) được tải lên {r['n']} lần: {r['names']}"})

    invs, in_scope = _scope_invoices(org_id, file_ids)
    by_key = defaultdict(list)
    for inv in invs:
        if inv["business_key"]:
            by_key[inv["business_key"]].append(inv)
    for key, items in by_key.items():
        if len(items) < 2 or not any(in_scope(i) for i in items):
            continue
        totals = {i["total"] for i in items}
        evidence = [_inv_ev(i) for i in items]
        formats = sorted({i["source_format"] for i in items})
        if len(totals) == 1:
            reason = "Cùng MST người bán, mẫu số, ký hiệu, số hoá đơn và cùng tổng tiền"
            if len(formats) > 1:
                reason += f" (cùng một hoá đơn ở nhiều định dạng: {', '.join(formats)} — dùng bản XML làm nguồn)"
            groups.append({"type": "INVOICE_DUPLICATE", "status": "DUPLICATE", "business_key": key,
                           "invoice_ids": [i["id"] for i in items], "evidence": evidence, "reason": reason})
        else:
            groups.append({"type": "INVOICE_KEY_CONFLICT", "status": "CONFLICTED", "business_key": key,
                           "invoice_ids": [i["id"] for i in items], "evidence": evidence,
                           "reason": "Cùng khoá hoá đơn nhưng khác số tiền — cần đối chiếu bản gốc"})
    # Nghi vấn: khác số hoá đơn, cùng người bán + ngày + tổng tiền
    sus = defaultdict(list)
    for inv in invs:
        if inv["seller_tax_id"] and inv["issue_date"] and inv["total"]:
            sus[(inv["seller_tax_id"], inv["issue_date"], inv["total"])].append(inv)
    for (tax, d, total), items in sus.items():
        keys = {i["business_key"] for i in items}
        if len(items) < 2 or len(keys) < 2 or not any(in_scope(i) for i in items):
            continue
        groups.append({"type": "INVOICE_SUSPECTED", "status": "NEEDS_REVIEW", "invoice_ids": [i["id"] for i in items],
                       "evidence": [_inv_ev(i) for i in items],
                       "reason": f"Khác số hoá đơn nhưng cùng người bán {tax}, cùng ngày {d}, cùng tổng {total} — chỉ là nghi vấn"})

    # Dòng sao kê trùng
    q = "SELECT b.*, f.original_name file_name FROM cur_bank_transactions b JOIN files f ON f.id=b.file_id WHERE b.org_id=?"
    txns = [t for t in db.all_(q, (org_id,))]
    rows = defaultdict(list)
    for t in txns:
        rows[(t["txn_date"], t["amount"], (t["reference"] or "").strip(), fold(t["description"]))].append(t)
    for k, items in rows.items():
        if len(items) > 1 and k[2] and any(scope is None or t["file_id"] in scope for t in items):
            groups.append({"type": "ROW_DUPLICATE", "status": "NEEDS_REVIEW", "bank_ids": [t["id"] for t in items],
                           "evidence": [{"file": t["file_name"], "row": t["row_ref"]} for t in items],
                           "reason": f"Giao dịch {k[0]} {k[1]} tham chiếu {k[2]} xuất hiện {len(items)} lần"})
    # Nghi chi trùng
    outs = [t for t in txns if money.D(t["amount"]) < 0 and t["counterparty"]
            and (scope is None or t["file_id"] in scope)]
    by_cp = defaultdict(list)
    for t in outs:
        by_cp[(fold(t["counterparty"]), t["amount"])].append(t)
    for (cp, amt), items in by_cp.items():
        items.sort(key=lambda t: t["txn_date"] or "")
        for a, b in zip(items, items[1:]):
            dd = _days(a["txn_date"], b["txn_date"])
            if dd is not None and dd <= tolerance_days * 10 and (a["reference"] or "") != (b["reference"] or ""):
                groups.append({"type": "SUSPECTED_DOUBLE_PAYMENT", "status": "NEEDS_REVIEW",
                               "bank_ids": [a["id"], b["id"]],
                               "evidence": [{"file": t["file_name"], "row": t["row_ref"], "date": t["txn_date"],
                                             "ref": t["reference"]} for t in (a, b)],
                               "reason": f"Chi {money.fmt(-money.D(amt))} cho '{a['counterparty']}' hai lần cách {dd} ngày, khác tham chiếu"})
    return groups


def _inv_ev(i):
    return {"invoice_id": i["id"], "file": i["file_name"], "format": i["source_format"], "number": i["number"],
            "series": i["series"], "date": i["issue_date"], "total": i["total"], "seller": i["seller_name"]}
