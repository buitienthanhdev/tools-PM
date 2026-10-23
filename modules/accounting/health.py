"""Tình trạng module kế toán cho trang Quản trị (/api/health/tools)."""

import threading

from . import db, settings


def status():
    from core import config as hubcfg
    from core import llm

    from .extract import ocr
    from .ingest import scanner

    cfg = settings.get()
    parts, ok = [], True
    from . import tenancy

    q = {"waiting": 0, "running": 0, "failed": 0}
    try:
        orgs = tenancy.all_org_ids()
        for org in orgs:  # mỗi tổ chức một file database
            if not db.tenant_exists(org):
                continue
            with db.use_org(org):
                r = db.one("""SELECT sum(status IN ('QUEUED','RETRY_SCHEDULED')) waiting, sum(status='RUNNING') running,
                              sum(status='FAILED' AND updated_at > ?) failed FROM tasks""", (db.now() - 86400,))
            for k in q:
                q[k] += r[k] or 0
        parts.append(f"DB ổn · {len(orgs)} database riêng")
    except Exception as e:  # DB hỏng/khoá: báo lỗi, không làm sập trang quản trị
        return {"ok": False, "detail": f"DB lỗi: {type(e).__name__}"}
    want = max(1, int(cfg["workers"]))
    alive = sum(1 for t in threading.enumerate() if t.name.startswith("accounting-worker-") and t.is_alive())
    if alive < want:
        ok = False
    parts.append(f"worker {alive}/{want}")
    parts.append(f"chờ {q['waiting'] or 0} · chạy {q['running'] or 0}" + (f" · lỗi 24h {q['failed']}" if q["failed"] else ""))
    if cfg["llm_planner"]:
        model = cfg["planner_model"] or hubcfg.model("genreport")
        st = llm.status(model)
        parts.append(f"AI {model}" + ("" if st["ok"] else " không sẵn sàng → lập kế hoạch theo quy tắc"))
    else:
        parts.append("AI tắt (quy tắc)")
    parts.append("OCR có" if ocr.available() else "không OCR")
    parts.append("Defender" if scanner.available() else "chưa quét virus")
    return {"ok": ok, "detail": " · ".join(parts)}
