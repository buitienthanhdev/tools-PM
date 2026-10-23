"""
API của module kế toán: /api/accounting/...

Hub đã chặn: chưa đăng nhập (401), tài khoản chưa duyệt / chưa được cấp công cụ "accounting" (403).
Ở đây: mọi route /o/<org_id>/ kiểm tra thành viên + vai trò từ DB (security.context). Không phải thành viên → 404.
"""

import re
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import Blueprint, Response, jsonify, request, send_file

from core import auth as hubauth

from . import audit, db, jobs, security, settings, storage, tenancy
from .agent import review, runner
from .engine import journal, proposals, rules
from .extract import ocr
from .extract import pdf as pdfx
from .ingest import pipeline, scanner

bp = Blueprint("accounting", __name__, url_prefix="/api/accounting")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ── tiện ích ─────────────────────────────────────────────────────
def err(code, msg, status, **extra):
    return jsonify({"error": msg, "code": code, **extra}), status


def user():
    u = hubauth.current_user()
    return u["email"], u.get("name") or u["email"]


_buckets = defaultdict(deque)
_rl_lock = threading.Lock()


def rate_limit(name, per_minute):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            key = (name, user()[0])
            now = time.time()
            with _rl_lock:
                q = _buckets[key]
                while q and now - q[0] > 60:
                    q.popleft()
                if len(q) >= per_minute:
                    return err("rate_limited", "Thao tác quá nhanh, vui lòng thử lại sau ít giây", 429)
                q.append(now)
            return fn(*a, **kw)
        return wrapper
    return deco


def org_route(perm="read"):
    """Giải quyết org_id → Ctx; kiểm tra vai trò. Không phải thành viên → 404."""
    def deco(fn):
        @wraps(fn)
        def wrapper(org_id, *a, **kw):
            if not UUID.match(org_id):
                return err("not_found", "Không tìm thấy", 404)
            for k, v in kw.items():
                if k.endswith("_id") and not UUID.match(str(v)):
                    return err("not_found", "Không tìm thấy", 404)
            try:
                ctx = security.context(org_id, user()[0])  # danh bạ trung tâm
                ctx.require(perm)
                with db.use_org(org_id):  # dữ liệu: file database riêng của tổ chức
                    return fn(ctx, *a, **kw)
            except security.NotFound:
                return err("not_found", "Không tìm thấy", 404)
            except security.Forbidden as e:
                return err(e.code, str(e), 403)
            except journal.JournalError as e:
                return err(e.code, str(e), 400, details=e.details)
            except (LookupError,) as e:
                return err("not_found", str(e) or "Không tìm thấy", 404)
            except ValueError as e:
                return err("bad_request", str(e), 400)
        return wrapper
    return deco


def body():
    if not request.get_data(cache=True):
        return {}
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("Dữ liệu gửi lên không phải JSON hợp lệ (UTF-8)")
    return d


def one_or_404(sql, args):
    r = db.one(sql, args)
    if not r:
        raise LookupError("Không tìm thấy")
    return r


def _tax_ok(tax):
    from stdnum.vn import mst as vn_mst

    return vn_mst.is_valid(tax)


# ── trạng thái & tổ chức ─────────────────────────────────────────
@bp.route("/status")
def status():
    from core import config as hubcfg
    from core import llm

    email, name = user()
    security.ensure_personal_org(email, name)
    cfg = settings.get()
    model = cfg["planner_model"] or hubcfg.model("genreport")
    return jsonify({
        "enabled": True, "orgs": security.orgs_of(email),
        "capabilities": {"antivirus": scanner.available(), "ocr": ocr.available(),
                         "llm_planner": bool(cfg["llm_planner"]), "planner_model": model, "llm": llm.status(model),
                         "cloud_ai_allowed": bool(cfg["cloud_ai_allowed"])},
        "limits": {k: cfg[k] for k in ("max_file_mb", "max_files_per_upload", "max_pdf_pages", "max_zip_members")},
        "roles": list(security.ROLES),
    })


@bp.route("/orgs", methods=["POST"])
@rate_limit("org_create", 10)
def create_org():
    email, _ = user()
    d = body()
    name = str(d.get("name") or "").strip()
    if not name:
        return err("bad_request", "Cần tên tổ chức", 400)
    tax = re.sub(r"[^0-9-]", "", str(d.get("tax_id") or "")) or None
    if tax and not _tax_ok(tax):
        return err("bad_tax_id", f"Mã số thuế {tax} không hợp lệ (sai độ dài hoặc chữ số kiểm tra)", 400)
    oid = security.create_org(name, email, tax_id=tax, base_currency=str(d.get("base_currency") or "VND").upper()[:3])
    return jsonify({"org_id": oid, "orgs": security.orgs_of(email)})


@bp.route("/o/<org_id>/settings", methods=["GET"])
@org_route("read")
def org_settings(ctx):
    org = db.one("SELECT * FROM orgs WHERE id=?", (ctx.org_id,))
    return jsonify({"org": org, "roles": sorted(ctx.roles), "tax_id_valid": _tax_ok(org["tax_id"]) if org["tax_id"] else None,
                    "members": security.members(ctx) if ctx.can("manage") else None})


@bp.route("/o/<org_id>/settings", methods=["POST"])
@org_route("manage")
def org_settings_update(ctx):
    d = body()
    if "tax_id" in d:
        t = re.sub(r"[^0-9-]", "", str(d.get("tax_id") or ""))
        if t and not _tax_ok(t):
            return err("bad_tax_id", f"Mã số thuế {t} không hợp lệ (sai độ dài hoặc chữ số kiểm tra) — chưa lưu", 400)
    with db.tx() as c:
        before = dict(c.execute("SELECT name, tax_id, base_currency FROM orgs WHERE id=?", (ctx.org_id,)).fetchone())
        name = str(d.get("name") or before["name"]).strip()[:120]
        tax = re.sub(r"[^0-9-]", "", str(d.get("tax_id"))) if "tax_id" in d else before["tax_id"]
        c.execute("UPDATE orgs SET name=?, tax_id=? WHERE id=?", (name, tax or None, ctx.org_id))
        if tax and tax != before["tax_id"]:
            # Chiều hoá đơn (mua/bán) phụ thuộc MST tổ chức → tính lại cho hoá đơn chưa xác định
            from .engine.validate import direction
            for inv in c.execute("SELECT id, seller_tax_id, buyer_tax_id FROM invoices WHERE org_id=?", (ctx.org_id,)).fetchall():
                c.execute("UPDATE invoices SET direction=? WHERE id=?", (direction(dict(inv), tax), inv["id"]))
        audit.log(c, ctx.org_id, ctx.user, "org.update", "org", ctx.org_id, before=before, after={"name": name, "tax_id": tax})
    with db.central(), db.tx() as c:
        c.execute("UPDATE orgs SET name=?, tax_id=? WHERE id=?", (name, tax or None, ctx.org_id))
    return org_settings.__wrapped__(ctx)


@bp.route("/o/<org_id>/members", methods=["POST"])
@org_route("manage")
def set_member(ctx):
    d = body()
    security.set_member(ctx, d.get("email"), d.get("roles") or [])
    return jsonify({"members": security.members(ctx)})


# ── file ─────────────────────────────────────────────────────────
@bp.route("/o/<org_id>/files", methods=["POST"])
@rate_limit("upload", 240)
@org_route("upload")
def upload(ctx):
    files = request.files.getlist("files")
    cid = request.form.get("conversation_id") or None
    if cid and not db.one("SELECT 1 FROM conversations WHERE id=? AND org_id=? AND created_by=?", (cid, ctx.org_id, ctx.user)):
        return err("not_found", "Không có hội thoại", 404)
    if not files:
        return err("bad_request", "Chưa chọn file", 400)
    if len(files) > int(settings.get()["max_files_per_upload"]):
        return err("too_many", "Quá nhiều file trong một lần tải", 400)
    results = []
    for f in files:
        name = re.sub(r"[\x00-\x1f\\/:*?\"<>|]", "_", f.filename or "file")[:200]
        results.append(pipeline.ingest_stream(ctx, f.stream, name, cid))
    return jsonify({"results": results, "file_ids": pipeline.flatten(results)})


def _file_row(f):
    meta = db.loads(f.get("error_json"), {}) or {}
    ex = db.one("SELECT id, parser, parser_version, status, error_json, stats_json FROM extractions WHERE file_id=? ORDER BY created_at DESC LIMIT 1", (f["id"],))
    return {"id": f["id"], "name": f["original_name"], "kind": f["kind"], "size": f["size"], "sha256": f["sha256"],
            "scan": f["scan_status"], "status": f["status"], "warnings": meta.get("warnings") or [],
            "archive_path": f["archive_path"], "parent_file_id": f["parent_file_id"], "uploaded_at": f["uploaded_at"],
            "uploaded_by": f["uploaded_by"],
            "extraction": None if not ex else {"parser": ex["parser"], "version": ex["parser_version"], "status": ex["status"],
                                               "error": db.loads(ex["error_json"], None), "stats": db.loads(ex["stats_json"], {})}}


@bp.route("/o/<org_id>/files")
@org_route("read")
def list_files(ctx):
    cid = request.args.get("conversation_id")
    if cid:
        one_or_404("SELECT id FROM conversations WHERE id=? AND org_id=? AND created_by=?", (cid, ctx.org_id, ctx.user))
        rows = db.all_("""SELECT DISTINCT f.* FROM files f JOIN uploads u ON u.file_id=f.id
                          WHERE f.org_id=? AND u.conversation_id=? ORDER BY f.uploaded_at""", (ctx.org_id, cid))
    else:
        rows = db.all_("SELECT * FROM files WHERE org_id=? ORDER BY uploaded_at DESC LIMIT 1000", (ctx.org_id,))
    return jsonify({"files": [_file_row(f) for f in rows]})


@bp.route("/o/<org_id>/files/<file_id>")
@org_route("read")
def file_detail(ctx, file_id):
    f = one_or_404("SELECT * FROM files WHERE id=? AND org_id=?", (file_id, ctx.org_id))
    docs = db.all_("SELECT id, doc_type, title, status, data_json FROM cur_documents WHERE file_id=? AND org_id=?", (file_id, ctx.org_id))
    for d in docs:
        data = db.loads(d.pop("data_json"), {})
        d["warnings"] = data.get("warnings") or []
        d["table"] = {k: data.get(k) for k in ("sheet", "header_row", "header", "roles", "semantics", "row_count", "rows_with_issues")} if "header" in data else None
    invs = db.all_("SELECT id, series, number, issue_date, seller_name, total, currency, status FROM cur_invoices WHERE file_id=? AND org_id=?", (file_id, ctx.org_id))
    return jsonify({"file": _file_row(f), "documents": docs, "invoices": invs})


@bp.route("/o/<org_id>/files/<file_id>/download")
@org_route("read")
def file_download(ctx, file_id):
    f = one_or_404("SELECT * FROM files WHERE id=? AND org_id=?", (file_id, ctx.org_id))
    inline = request.args.get("inline") == "1" and f["kind"] in ("pdf", "png", "jpeg")
    resp = send_file(storage.abspath(f["storage_path"]), mimetype=f["mime"] or "application/octet-stream",
                     as_attachment=not inline, download_name=f["original_name"])
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    audit.record(ctx.org_id, ctx.user, "file.download", "file", file_id)
    return resp


@bp.route("/o/<org_id>/files/<file_id>/page/<int:page>.png")
@org_route("read")
def file_page(ctx, file_id, page):
    f = one_or_404("SELECT * FROM files WHERE id=? AND org_id=?", (file_id, ctx.org_id))
    if f["kind"] != "pdf":
        return err("bad_request", "Chỉ PDF có trang", 400)
    bbox = None
    if request.args.get("bbox"):
        try:
            bbox = [float(x) for x in request.args["bbox"].split(",")][:4]
        except ValueError:
            bbox = None
    png = pdfx.render_page(storage.read(f["storage_path"]), page, bbox)
    return Response(png, mimetype="image/png")


@bp.route("/o/<org_id>/files/<file_id>/preview")
@org_route("read")
def file_preview(ctx, file_id):
    f = one_or_404("SELECT * FROM files WHERE id=? AND org_id=?", (file_id, ctx.org_id))
    out = {"kind": f["kind"], "name": f["original_name"]}
    if f["kind"] in ("xlsx", "xlsm", "csv", "tsv", "json"):
        docs = db.all_("SELECT data_json FROM cur_documents WHERE file_id=? AND org_id=?", (file_id, ctx.org_id))
        out["tables"] = []
        for d in docs:
            data = db.loads(d["data_json"], {})
            if data.get("header"):
                out["tables"].append({"sheet": data.get("sheet"), "header": data["header"], "header_row": data.get("header_row"),
                                      "rows": (data.get("rows") or [])[:300], "row_numbers": (data.get("row_numbers") or [])[:300],
                                      "roles": data.get("roles"), "kind": data.get("table_kind")})
    elif f["kind"] == "pdf":
        ex = db.one("SELECT stats_json FROM extractions WHERE file_id=? AND status IN ('OK','PARTIAL') ORDER BY created_at DESC LIMIT 1", (file_id,))
        out["pages"] = (db.loads(ex["stats_json"], {}) or {}).get("pages") if ex else None
    else:
        ex = db.one("SELECT text_content FROM extractions WHERE file_id=? ORDER BY created_at DESC LIMIT 1", (file_id,))
        out["text"] = (ex["text_content"] if ex else None) or (storage.read(f["storage_path"])[:200000].decode("utf-8", "replace")
                                                               if f["kind"] in ("xml", "txt") else None)
    return jsonify(out)


@bp.route("/o/<org_id>/invoices/<invoice_id>/evidence")
@org_route("read")
def invoice_evidence(ctx, invoice_id):
    inv = one_or_404("SELECT * FROM invoices WHERE id=? AND org_id=?", (invoice_id, ctx.org_id))
    inv["issues"] = db.loads(inv.pop("issues_json"), [])
    fields = db.all_("SELECT * FROM fields WHERE document_id=? AND org_id=? ORDER BY field_name", (inv["document_id"], ctx.org_id))
    for fl in fields:
        fl["location"] = db.loads(fl.pop("source_location_json"), None)
    lines = db.all_("SELECT * FROM invoice_lines WHERE invoice_id=? AND org_id=? ORDER BY line_no", (invoice_id, ctx.org_id))
    f = one_or_404("SELECT * FROM files WHERE id=? AND org_id=?", (inv["file_id"], ctx.org_id))
    return jsonify({"invoice": inv, "fields": fields, "lines": lines, "file": _file_row(f)})


# ── hội thoại & tác vụ ───────────────────────────────────────────
@bp.route("/o/<org_id>/conversations")
@org_route("read")
def conversations(ctx):
    rows = db.all_("SELECT * FROM conversations WHERE org_id=? AND created_by=? ORDER BY updated_at DESC LIMIT 200", (ctx.org_id, ctx.user))
    return jsonify({"conversations": rows})


@bp.route("/o/<org_id>/conversations", methods=["POST"])
@org_route("run_task")
def conversation_create(ctx):
    title = str(body().get("title") or "Phiên làm việc mới").strip()[:120]
    cid = db.new_id()
    with db.tx() as c:
        db.insert(c, "conversations", {"id": cid, "org_id": ctx.org_id, "created_by": ctx.user, "title": title,
                                       "created_at": db.now(), "updated_at": db.now()})
    return jsonify({"conversation": db.one("SELECT * FROM conversations WHERE id=?", (cid,))})


@bp.route("/o/<org_id>/conversations/<conversation_id>")
@org_route("read")
def conversation(ctx, conversation_id):
    conv = one_or_404("SELECT * FROM conversations WHERE id=? AND org_id=? AND created_by=?", (conversation_id, ctx.org_id, ctx.user))
    msgs = db.all_("SELECT * FROM messages WHERE conversation_id=? AND org_id=? ORDER BY created_at", (conversation_id, ctx.org_id))
    tasks_ = db.all_("SELECT id, status, command, plan_source, created_at, updated_at FROM tasks WHERE conversation_id=? AND org_id=? ORDER BY created_at",
                     (conversation_id, ctx.org_id))
    arts = db.all_("SELECT id, task_id, root_id, parent_id, version, name, kind, size, created_at, validation_json FROM artifacts WHERE conversation_id=? AND org_id=? ORDER BY created_at",
                   (conversation_id, ctx.org_id))
    for a in arts:
        a["verified"] = (db.loads(a.pop("validation_json"), {}) or {}).get("ok")
    files = [
        _file_row(f) for f in db.all_("""SELECT DISTINCT f.* FROM files f JOIN uploads u ON u.file_id=f.id
                                         WHERE f.org_id=? AND u.conversation_id=? ORDER BY f.uploaded_at""", (ctx.org_id, conversation_id))]
    return jsonify({"conversation": conv, "messages": msgs, "tasks": tasks_, "artifacts": arts, "files": files})


@bp.route("/o/<org_id>/conversations/<conversation_id>/messages", methods=["POST"])
@rate_limit("message", 30)
@org_route("run_task")
def send_message(ctx, conversation_id):
    one_or_404("SELECT id FROM conversations WHERE id=? AND org_id=? AND created_by=?", (conversation_id, ctx.org_id, ctx.user))
    d = body()
    content = str(d.get("content") or "").strip()
    if not content:
        return err("bad_request", "Hãy nhập yêu cầu", 400)
    if len(content) > 4000:
        return err("bad_request", "Yêu cầu quá dài (tối đa 4000 ký tự)", 400)
    file_ids = [str(x) for x in (d.get("file_ids") or []) if UUID.match(str(x))]
    if not file_ids:  # mặc định: mọi file đã tải lên trong hội thoại
        file_ids = [r["file_id"] for r in db.all_("""SELECT DISTINCT u.file_id FROM uploads u JOIN files f ON f.id=u.file_id
                                                     WHERE u.org_id=? AND u.conversation_id=? AND u.file_id IS NOT NULL AND f.kind!='zip'""",
                                                  (ctx.org_id, conversation_id))]
    tid = db.new_id()
    with db.tx() as c:
        db.insert(c, "messages", {"id": db.new_id(), "org_id": ctx.org_id, "conversation_id": conversation_id, "role": "user",
                                  "content": content, "task_id": tid, "created_by": ctx.user, "created_at": db.now()})
        db.insert(c, "tasks", {"id": tid, "org_id": ctx.org_id, "conversation_id": conversation_id, "created_by": ctx.user,
                               "command": content, "file_ids_json": db.dumps(file_ids), "status": "CREATED", "plan_json": None,
                               "plan_source": None, "summary_json": None, "error_json": None, "attempts": 0, "not_before": 0,
                               "lease_until": None, "worker_id": None, "cancel_requested": 0, "version": 1,
                               "created_at": db.now(), "updated_at": db.now()})
        c.execute("UPDATE conversations SET updated_at=?, title=CASE WHEN title='Phiên làm việc mới' THEN ? ELSE title END WHERE id=?",
                  (db.now(), content[:80], conversation_id))
        audit.log(c, ctx.org_id, ctx.user, "task.create", "task", tid, files=len(file_ids), command=content[:500])
    runner.transition(tid, "VALIDATING")
    # Kiểm tra: mọi file thuộc tổ chức này
    q = ",".join("?" for _ in file_ids) or "''"
    owned = db.one(f"SELECT count(*) n FROM files WHERE org_id=? AND id IN ({q})", (ctx.org_id, *file_ids))["n"] if file_ids else 0
    if owned != len(file_ids):
        runner.transition(tid, "FAILED", error_json=db.dumps({"code": "bad_files", "message": "File không thuộc tổ chức"}))
        return err("bad_request", "File không hợp lệ", 400)
    runner.transition(tid, "QUEUED")
    jobs.wake()
    return jsonify({"task_id": tid})


def _task_view(ctx, task_id, after=0):
    t = one_or_404("SELECT * FROM tasks WHERE id=? AND org_id=? AND created_by=?", (task_id, ctx.org_id, ctx.user))
    for k in ("plan_json", "summary_json", "error_json", "file_ids_json"):
        t[k.replace("_json", "")] = db.loads(t.pop(k), None)
    steps = db.all_("SELECT seq, tool, goal, task_class, risk, approval_required, status, attempts, started_at, finished_at, error_json, output_json FROM task_steps WHERE task_id=? ORDER BY seq", (task_id,))
    for s in steps:
        out = db.loads(s.pop("output_json"), None) or {}
        s["summary"] = out.get("summary")
        s["data"] = {k: v for k, v in (out.get("data") or {}).items() if k in ("artifact_id", "name", "kind", "verified", "changes")}
        s["warnings"] = out.get("warnings") or []
        s["error"] = db.loads(s.pop("error_json"), None)
    events = db.all_("SELECT id, ts, kind, message, data_json FROM task_events WHERE task_id=? AND id>? ORDER BY id LIMIT 500", (task_id, after))
    for e in events:
        e["data"] = db.loads(e.pop("data_json"), None)
    return {"task": t, "steps": steps, "events": events}


@bp.route("/o/<org_id>/tasks/<task_id>")
@org_route("read")
def task(ctx, task_id):
    return jsonify(_task_view(ctx, task_id, int(request.args.get("after") or 0)))


@bp.route("/o/<org_id>/tasks/<task_id>/cancel", methods=["POST"])
@org_route("run_task")
def task_cancel(ctx, task_id):
    t = one_or_404("SELECT status FROM tasks WHERE id=? AND org_id=? AND created_by=?", (task_id, ctx.org_id, ctx.user))
    if t["status"] in runner.TERMINAL:
        return err("bad_state", "Tác vụ đã kết thúc", 400)
    with db.tx() as c:
        c.execute("UPDATE tasks SET cancel_requested=1 WHERE id=?", (task_id,))
        audit.log(c, ctx.org_id, ctx.user, "task.cancel_request", "task", task_id)
    if t["status"] in ("QUEUED", "WAITING_FOR_INPUT", "WAITING_FOR_APPROVAL", "RETRY_SCHEDULED"):
        runner.transition(task_id, "CANCELLED")
    return jsonify({"ok": True})


# ── artifact ─────────────────────────────────────────────────────
@bp.route("/o/<org_id>/artifacts")
@org_route("read")
def artifacts(ctx):
    rows = db.all_("SELECT id, task_id, conversation_id, root_id, parent_id, version, name, kind, size, created_at, created_by FROM artifacts WHERE org_id=? AND created_by=? ORDER BY created_at DESC LIMIT 500", (ctx.org_id, ctx.user))
    return jsonify({"artifacts": rows})


@bp.route("/o/<org_id>/artifacts/<artifact_id>")
@org_route("read")
def artifact(ctx, artifact_id):
    a = one_or_404("SELECT * FROM artifacts WHERE id=? AND org_id=? AND created_by=?", (artifact_id, ctx.org_id, ctx.user))
    sp = db.loads(a.pop("spec_json"), {}) or {}
    a["validation"] = db.loads(a.pop("validation_json"), {})
    a["versions"] = db.all_("SELECT id, version, name, kind, created_at, parent_id FROM artifacts WHERE root_id=? AND org_id=? AND created_by=? ORDER BY version", (a["root_id"], ctx.org_id, ctx.user))
    from .reports import spec as S
    a["preview"] = {"title": sp.get("title"), "period": sp.get("period"), "currency": sp.get("currency"), "warnings": sp.get("warnings", []),
                    "sources": sp.get("sources", []),
                    "sheets": [{"name": s["name"], "title": s["title"], "columns": s["columns"], "rows": s["rows"][:500],
                                "row_count": len(s["rows"]), "totals": S.totals(s), "charts": s.get("charts", [])} for s in sp.get("sheets", [])]}
    return jsonify({"artifact": a})


@bp.route("/o/<org_id>/artifacts/<artifact_id>/download")
@org_route("read")
def artifact_download(ctx, artifact_id):
    a = one_or_404("SELECT * FROM artifacts WHERE id=? AND org_id=? AND created_by=?", (artifact_id, ctx.org_id, ctx.user))
    if not storage.verify(a["storage_path"], a["sha256"]):
        return err("integrity", "File báo cáo không khớp SHA-256 đã lưu", 500)
    mime = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}.get(a["kind"], "application/octet-stream")
    inline = request.args.get("inline") == "1" and a["kind"] == "pdf"
    audit.record(ctx.org_id, ctx.user, "artifact.export", "artifact", artifact_id, name=a["name"])
    return send_file(storage.abspath(a["storage_path"]), mimetype=mime, as_attachment=not inline, download_name=a["name"])


# ── kiểm duyệt, bút toán, phê duyệt ─────────────────────────────
@bp.route("/o/<org_id>/reviews")
@org_route("read")
def reviews(ctx):
    return jsonify({"items": review.list_items(ctx, request.args.get("status") or "OPEN")})


@bp.route("/o/<org_id>/reviews/<item_id>", methods=["POST"])
@org_route("read")
def review_resolve(ctx, item_id):
    d = body()
    review.resolve(ctx, item_id, d.get("action"), str(d.get("note") or "")[:1000], d.get("correction"))
    return jsonify({"ok": True})


@bp.route("/o/<org_id>/answers", methods=["POST"])
@org_route("edit_draft")
def answers(ctx):
    """Câu trả lời cho hoá đơn thiếu thông tin: {answers: {invoice_id: account_code}, save_rule: bool}."""
    d = body()
    ans = {k: str(v) for k, v in (d.get("answers") or {}).items() if UUID.match(k)}
    if not ans:
        return err("bad_request", "Không có câu trả lời", 400)
    res = proposals.propose_for_invoices(ctx, list(ans), answers=ans)
    rule_ids = []
    if d.get("save_rule"):
        for iid, acct in ans.items():
            inv = db.one("SELECT seller_tax_id FROM invoices WHERE id=? AND org_id=?", (iid, ctx.org_id))
            if inv and inv["seller_tax_id"]:
                rule_ids.append(proposals.propose_rule(ctx, "seller_tax_id", inv["seller_tax_id"], acct,
                                                       "Từ câu trả lời của người dùng", {"invoice_id": iid}))
    with db.tx() as c:
        for iid in ans:
            c.execute("UPDATE review_items SET status='RESOLVED', resolved_by=?, resolved_at=? WHERE org_id=? AND kind='missing_data' AND target_id=? AND status='OPEN'",
                      (ctx.user, db.now(), ctx.org_id, iid))
    return jsonify({**res, "rule_ids": rule_ids})


@bp.route("/o/<org_id>/journal")
@org_route("read")
def journal_list(ctx):
    st = request.args.get("status")
    sql = "SELECT * FROM journal_entries WHERE org_id=?" + (" AND status=?" if st else "") + " ORDER BY created_at DESC LIMIT 500"
    rows = db.all_(sql, (ctx.org_id, st) if st else (ctx.org_id,))
    out = []
    for e in rows:
        full = journal.get(ctx.org_id, e["id"])
        full["pending_approval"] = db.one("SELECT id, requested_by FROM approvals WHERE target_id=? AND status='PENDING'", (e["id"],))
        out.append(full)
    return jsonify({"entries": out})


@bp.route("/o/<org_id>/journal/<entry_id>", methods=["POST"])
@org_route("edit_draft")
def journal_update(ctx, entry_id):
    d = body()
    journal.update_draft(ctx, entry_id, d.get("description"), d.get("lines"))
    return jsonify({"entry": journal.get(ctx.org_id, entry_id)})


@bp.route("/o/<org_id>/journal/<entry_id>/request-post", methods=["POST"])
@org_route("request_commit")
def journal_request(ctx, entry_id):
    return jsonify({"approval_id": journal.request_post(ctx, entry_id)})


@bp.route("/o/<org_id>/journal/<entry_id>/reverse", methods=["POST"])
@org_route("edit_draft")
def journal_reverse(ctx, entry_id):
    return jsonify({"entry_id": journal.reverse(ctx, entry_id, str(body().get("reason") or "")[:300])})


@bp.route("/o/<org_id>/approvals")
@org_route("read")
def approvals(ctx):
    rows = db.all_("SELECT * FROM approvals WHERE org_id=? AND status=? ORDER BY requested_at DESC LIMIT 500",
                   (ctx.org_id, request.args.get("status") or "PENDING"))
    mode = security.self_approval(ctx)
    for a in rows:
        a["entry"] = journal.get(ctx.org_id, a["target_id"]) if a["target_type"] == "journal_entry" else None
        is_self = ctx.user == a["requested_by"] or bool(a["entry"] and ctx.user == a["entry"]["created_by"])
        a["self_approval"] = mode if is_self else None
        a["can_approve"] = ctx.can("approve") and (not is_self or mode is not None)
    return jsonify({"approvals": rows})


@bp.route("/o/<org_id>/approvals/<approval_id>/approve", methods=["POST"])
@org_route("approve")
def approval_approve(ctx, approval_id):
    return jsonify({"posted_entry": journal.approve(ctx, approval_id, confirm_self=bool(body().get("confirm_self")))})


@bp.route("/o/<org_id>/approvals/<approval_id>/reject", methods=["POST"])
@org_route("approve")
def approval_reject(ctx, approval_id):
    journal.reject(ctx, approval_id, str(body().get("reason") or "")[:500])
    return jsonify({"ok": True})


@bp.route("/o/<org_id>/rules")
@org_route("read")
def rules_list(ctx):
    return jsonify({"rules": db.all_("SELECT * FROM account_rules WHERE org_id=? ORDER BY proposed_at DESC", (ctx.org_id,)),
                    "legal_rules": rules.as_dicts(),
                    "accounts": db.all_("SELECT code, name, acct_type, postable, regime, verification FROM accounts WHERE org_id=? ORDER BY code", (ctx.org_id,))})


@bp.route("/o/<org_id>/rules/<rule_id>/decide", methods=["POST"])
@org_route("read")
def rules_decide(ctx, rule_id):
    proposals.decide_rule(ctx, rule_id, bool(body().get("approve")), str(body().get("reason") or ""))
    return jsonify({"ok": True})


@bp.route("/o/<org_id>/ledger/trial-balance")
@org_route("read")
def trial_balance(ctx):
    return jsonify(journal.trial_balance(ctx.org_id, request.args.get("as_of")))


@bp.route("/o/<org_id>/periods")
@org_route("read")
def periods(ctx):
    return jsonify({"periods": db.all_("SELECT * FROM periods WHERE org_id=? ORDER BY start_date DESC", (ctx.org_id,))})


@bp.route("/o/<org_id>/periods/<period_id>/lock", methods=["POST"])
@org_route("lock_period")
def period_lock(ctx, period_id):
    journal.lock_period(ctx, period_id)
    return jsonify({"ok": True})


@bp.route("/o/<org_id>/audit")
@org_route("audit")
def audit_list(ctx):
    return jsonify({"events": audit.list_events(ctx.org_id, request.args.get("limit") or 200, request.args.get("before"))})


@bp.route("/o/<org_id>/audit/verify")
@org_route("audit")
def audit_verify(ctx):
    ok, bad, n = audit.verify()
    return jsonify({"ok": ok, "first_bad_seq": bad, "events": n})


@bp.route("/o/<org_id>/overview")
@org_route("read")
def overview(ctx):
    """Số liệu cho màn hình Tổng quan — chỉ đọc, từ bản trích xuất hiện hành."""
    o = ctx.org_id
    n = lambda sql, *a: db.one(sql, (o, *a))["n"]  # noqa: E731
    week = db.now() - 7 * 86400
    inv = {r["status"]: r["n"] for r in db.all_("SELECT status, count(*) n FROM cur_invoices WHERE org_id=? GROUP BY status", (o,))}
    recent_tasks = db.all_("""SELECT t.id, t.conversation_id, t.command, t.status, t.created_at, c.title FROM tasks t
                              LEFT JOIN conversations c ON c.id=t.conversation_id WHERE t.org_id=? AND t.created_by=? ORDER BY t.created_at DESC LIMIT 8""", (o, ctx.user))
    recent_arts = db.all_("""SELECT a.id, a.name, a.kind, a.version, a.created_at, a.conversation_id FROM artifacts a WHERE a.org_id=? AND a.created_by=?
                             AND a.version=(SELECT max(version) FROM artifacts b WHERE b.root_id=a.root_id) ORDER BY a.created_at DESC LIMIT 6""", (o, ctx.user))
    return jsonify({
        "org": db.one("SELECT name, tax_id, base_currency FROM orgs WHERE id=?", (o,)),
        "files": n("SELECT count(*) n FROM files WHERE org_id=? AND kind!='zip'"),
        "files_7d": n("SELECT count(*) n FROM files WHERE org_id=? AND kind!='zip' AND uploaded_at>?", week),
        "invoices": {"total": sum(inv.values()), "by_status": inv},
        "bank_txns": n("SELECT count(*) n FROM cur_bank_transactions WHERE org_id=?"),
        "ledger_entries": n("SELECT count(*) n FROM cur_imported_entries WHERE org_id=?"),
        "tables": n("SELECT count(*) n FROM cur_documents WHERE org_id=? AND doc_type='table'"),
        "reviews_open": n("SELECT count(*) n FROM review_items WHERE org_id=? AND status='OPEN'"),
        "approvals_pending": n("SELECT count(*) n FROM approvals WHERE org_id=? AND status='PENDING'"),
        "journal": {"proposed": n("SELECT count(*) n FROM journal_entries WHERE org_id=? AND status='PROPOSED'"),
                    "posted": n("SELECT count(*) n FROM journal_entries WHERE org_id=? AND status='POSTED'")},
        "tasks": {"total": n("SELECT count(*) n FROM tasks WHERE org_id=? AND created_by=?", ctx.user),
                  "running": n("SELECT count(*) n FROM tasks WHERE org_id=? AND created_by=? AND status IN ('QUEUED','RUNNING','RETRY_SCHEDULED','VERIFYING')", ctx.user),
                  "week": n("SELECT count(*) n FROM tasks WHERE org_id=? AND created_by=? AND created_at>?", ctx.user, week)},
        "artifacts": n("SELECT count(DISTINCT root_id) n FROM artifacts WHERE org_id=? AND created_by=?", ctx.user),
        "recent_tasks": recent_tasks, "recent_artifacts": recent_arts,
    })


@bp.route("/o/<org_id>/review-count")
@org_route("read")
def review_count(ctx):
    return jsonify({
        "reviews": db.one("SELECT count(*) n FROM review_items WHERE org_id=? AND status='OPEN'", (ctx.org_id,))["n"],
        "approvals": db.one("SELECT count(*) n FROM approvals WHERE org_id=? AND status='PENDING'", (ctx.org_id,))["n"],
    })



def init_app(app):
    """Gắn module vào Hub (chỉ khi được bật) và khởi động worker."""
    app.register_blueprint(bp)
    with db.central():
        db.conn()  # migrate danh bạ trung tâm
    tenancy.split_legacy()  # bố cục cũ (một file chung) → mỗi tổ chức một file; chạy một lần
    for org in tenancy.all_org_ids():
        if not db.tenant_exists(org):
            with db.central():
                row = db.one("SELECT * FROM orgs WHERE id=?", (org,))
            tenancy.create_tenant(row)
    jobs.start_workers()
