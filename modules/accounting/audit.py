"""
Nhật ký kiểm toán chỉ-thêm, nối chuỗi băm: hash = sha256(prev_hash + nội dung chuẩn hoá).
Trigger trong DB chặn UPDATE/DELETE; verify() phát hiện mọi sửa đổi ngoài ứng dụng.
Không ghi mật khẩu, token, khoá API.
"""

import hashlib

from . import db

GENESIS = "0" * 64
_SECRET_KEYS = ("password", "token", "secret", "api_key", "apikey", "authorization", "cookie")


def _clean(v):
    if isinstance(v, dict):
        return {
            k: ("[redacted]" if any(s in k.lower() for s in _SECRET_KEYS) else _clean(x))
            for k, x in v.items()
        }
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, str) and len(v) > 2000:
        return v[:2000] + "…"
    return v


def _digest(prev, row):
    body = db.dumps(
        {k: row[k] for k in ("id", "org_id", "ts", "actor", "action", "target_type", "target_id", "details_json")}
    )
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def log(c, org_id, actor, action, target_type=None, target_id=None, **details):
    """Ghi trong giao dịch đang mở (c) để nhật ký và thay đổi nghiệp vụ cùng thành công/thất bại."""
    last = c.execute("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
    prev = last[0] if last else GENESIS
    row = {
        "id": db.new_id(),
        "org_id": org_id,
        "ts": round(db.now(), 6),
        "actor": actor or "system",
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details_json": db.dumps(_clean(details)),
    }
    row["prev_hash"] = prev
    row["hash"] = _digest(prev, row)
    db.insert(c, "audit_events", row)
    return row["id"]


def record(org_id, actor, action, target_type=None, target_id=None, **details):
    with db.tx() as c:
        return log(c, org_id, actor, action, target_type, target_id, **details)


def verify():
    """Kiểm tra toàn chuỗi. Trả về (ok, seq lỗi đầu tiên hoặc None, số bản ghi)."""
    prev = GENESIS
    n = 0
    for r in db.conn().execute("SELECT * FROM audit_events ORDER BY seq"):
        r = dict(r)
        n += 1
        if r["prev_hash"] != prev or _digest(prev, r) != r["hash"]:
            return False, r["seq"], n
        prev = r["hash"]
    return True, None, n


def list_events(org_id, limit=200, before_seq=None):
    sql = "SELECT seq, id, ts, actor, action, target_type, target_id, details_json, hash FROM audit_events WHERE org_id=?"
    args = [org_id]
    if before_seq:
        sql += " AND seq < ?"
        args.append(before_seq)
    sql += " ORDER BY seq DESC LIMIT ?"
    args.append(min(int(limit), 1000))
    rows = db.all_(sql, args)
    for r in rows:
        r["details"] = db.loads(r.pop("details_json"), {})
    return rows
