"""
Thực thi tác vụ: state machine bền vững + checkpoint theo bước.

CREATED → VALIDATING → QUEUED → RUNNING → VERIFYING → COMPLETED
phụ: WAITING_FOR_INPUT, WAITING_FOR_APPROVAL, RETRY_SCHEDULED, FAILED, CANCELLED, PARTIALLY_COMPLETED

- Mỗi bước hoàn tất được ghi (output_json) trước khi sang bước sau → worker chết giữa chừng thì
  worker khác tiếp tục từ bước chưa xong, không chạy lại bước đã xong.
- Bước có side effect đều idempotent (khoá idempotency / UNIQUE) nên thử lại không nhân đôi.
- Chỉ thử lại lỗi tạm thời (AI timeout, DB bận), có giới hạn, backoff mũ + jitter.
- Không báo COMPLETED nếu báo cáo bắt buộc chưa được tạo và xác minh.
"""

import random
import re
import sqlite3
import time
import traceback

from core import llm

from .. import audit, db, security, settings, storage, telemetry
from ..extract.base import fold
from ..reports import excel as xl
from ..reports import pdf as pdfr
from ..reports import spec as S
from . import planner, policy, tools
from .schema import SchemaError

TRANSITIONS = {
    "CREATED": {"VALIDATING", "FAILED"},
    "VALIDATING": {"QUEUED", "FAILED"},
    "QUEUED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"VERIFYING", "RETRY_SCHEDULED", "FAILED", "CANCELLED", "WAITING_FOR_INPUT", "WAITING_FOR_APPROVAL", "QUEUED"},
    "RETRY_SCHEDULED": {"RUNNING", "CANCELLED", "FAILED"},
    "VERIFYING": {"COMPLETED", "PARTIALLY_COMPLETED", "FAILED"},
    "WAITING_FOR_INPUT": {"QUEUED", "CANCELLED"},
    "WAITING_FOR_APPROVAL": {"QUEUED", "CANCELLED", "COMPLETED"},
    "COMPLETED": set(), "PARTIALLY_COMPLETED": set(), "FAILED": set(), "CANCELLED": set(),
}
TERMINAL = {"COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"}


class TransitionError(Exception):
    pass


class Retry(Exception):
    def __init__(self, reason, delay):
        super().__init__(reason)
        self.delay = delay


def transition(task_id, to, expect=None, **fields):
    """Chuyển trạng thái có kiểm tra bảng TRANSITIONS + optimistic concurrency (version)."""
    with db.tx() as c:
        t = c.execute("SELECT status, version, org_id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not t:
            raise TransitionError("task không tồn tại")
        if expect and t["status"] not in expect:
            raise TransitionError(f"trạng thái hiện tại {t['status']} ∉ {expect}")
        if to not in TRANSITIONS[t["status"]] and not (to == t["status"] == "RUNNING"):
            raise TransitionError(f"không cho phép {t['status']} → {to}")
        sets = ", ".join(f"{k}=?" for k in fields)
        n = c.execute(f"UPDATE tasks SET status=?, version=version+1, updated_at=?{', ' + sets if sets else ''} "
                      "WHERE id=? AND version=?", (to, db.now(), *fields.values(), task_id, t["version"])).rowcount
        if n != 1:
            raise TransitionError("xung đột cập nhật đồng thời")
        _event(c, t["org_id"], task_id, "status", f"{t['status']} → {to}", {"from": t["status"], "to": to})
    return t["status"]


def _event(c, org_id, task_id, kind, message, data=None):
    c.execute("INSERT INTO task_events (org_id, task_id, ts, kind, message, data_json) VALUES (?,?,?,?,?,?)",
              (org_id, task_id, db.now(), kind, str(message)[:1000], db.dumps(data) if data is not None else None))


def event(org_id, task_id, kind, message, data=None):
    with db.tx() as c:
        _event(c, org_id, task_id, kind, message, data)


class Run:
    """Ngữ cảnh thực thi cho công cụ: phạm vi file, tổ chức, ghi sự kiện, heartbeat, tạo artifact."""

    def __init__(self, task, worker_id=None):
        self.task = task
        self.ctx = security.context(task["org_id"], task["created_by"])  # quyền tính tại thời điểm chạy
        self.org = db.one("SELECT * FROM orgs WHERE id=?", (task["org_id"],))
        self.file_ids = db.loads(task["file_ids_json"], [])
        self.settings = settings.get()
        self.worker_id = worker_id
        self._warnings, self._notes, self._questions = [], [], []
        self._manifest = None
        self._last_progress = 0.0
        self.step = None

    # sự kiện
    def warn(self, msg):
        self._warnings.append(str(msg))
        event(self.ctx.org_id, self.task["id"], "warning", msg, {"step": self.step})

    def ask(self, question):
        """Câu hỏi cần người dùng trả lời; task sẽ không được báo hoàn thành trọn vẹn."""
        if question not in self._questions:
            self._questions.append(str(question))

    def note(self, msg):
        if msg not in self._notes:
            self._notes.append(str(msg))

    def progress(self, msg, i=None, n=None):
        now = time.time()
        if now - self._last_progress < 0.5 and i not in (1, n):
            return
        self._last_progress = now
        event(self.ctx.org_id, self.task["id"], "progress", msg, {"i": i, "n": n, "step": self.step})

    def heartbeat(self):
        with db.tx() as c:
            c.execute("UPDATE tasks SET lease_until=? WHERE id=? AND status='RUNNING'",
                      (db.now() + float(self.settings["lease_s"]), self.task["id"]))

    def cancelled(self):
        r = db.one("SELECT cancel_requested FROM tasks WHERE id=?", (self.task["id"],))
        return bool(r and r["cancel_requested"])

    # dữ liệu
    def files(self):
        if not self.file_ids:
            return []
        q = ",".join("?" for _ in self.file_ids)
        return db.all_(f"SELECT * FROM files WHERE org_id=? AND id IN ({q}) ORDER BY original_name", (self.ctx.org_id, *self.file_ids))

    def manifest(self, refresh=False):
        if self._manifest is not None and not refresh:
            return self._manifest
        org, ids = self.ctx.org_id, self.file_ids
        q = ",".join("?" for _ in ids) or "''"
        a = (org, *ids)
        inv = db.all_(f"SELECT status, currency, issue_date FROM cur_invoices WHERE org_id=? AND file_id IN ({q})", a)
        st = {}
        for i in inv:
            st[i["status"]] = st.get(i["status"], 0) + 1
        dates = [i["issue_date"] for i in inv if i["issue_date"]]
        dates += [r["d"] for r in db.all_(f"SELECT txn_date d FROM cur_bank_transactions WHERE org_id=? AND file_id IN ({q}) AND txn_date IS NOT NULL", a)]
        dates += [r["d"] for r in db.all_(f"SELECT entry_date d FROM cur_imported_entries WHERE org_id=? AND file_id IN ({q}) AND entry_date IS NOT NULL", a)]
        self._manifest = {
            "files": [{"name": f["original_name"], "kind": f["kind"]} for f in self.files()],
            "invoices": len(inv), "invoice_status": st,
            "bank_txns": db.one(f"SELECT count(*) n FROM cur_bank_transactions WHERE org_id=? AND file_id IN ({q})", a)["n"],
            "ledger_entries": db.one(f"SELECT count(*) n FROM cur_imported_entries WHERE org_id=? AND file_id IN ({q})", a)["n"],
            "tables": db.one(f"SELECT count(*) n FROM cur_documents WHERE org_id=? AND doc_type IN ('table') AND file_id IN ({q})", a)["n"],
            "workbooks": sum(1 for f in self.files() if f["kind"] in ("xlsx", "xlsm")),
            "currencies": sorted({i["currency"] or "VND" for i in inv}),
            "date_range": [min(dates), max(dates)] if dates else None,
        }
        return self._manifest

    def completed_outputs(self):
        rows = db.all_("SELECT seq, tool, goal, status, output_json, error_json FROM task_steps WHERE task_id=? ORDER BY seq",
                       (self.task["id"],))
        for r in rows:
            r["output"] = db.loads(r.pop("output_json"), None)
            r["error"] = db.loads(r.pop("error_json"), None)
        return rows

    # artifact
    def compose_spec(self, title=None):
        m = self.manifest()
        period = f"{_vn(m['date_range'][0])} – {_vn(m['date_range'][1])}" if m["date_range"] else "—"
        cur = m["currencies"][0] if len(m["currencies"]) == 1 else "VND"
        title = title or f"Báo cáo: {self.task['command'][:90]}"
        sp = S.new_spec(title, self.org["name"], period, cur)
        src_ids = {}
        for f in self.files():
            src_ids[f["id"]] = S.add_source(sp, f["original_name"], f["id"], f["sha256"],
                                            f["archive_path"] or "", f["kind"])
        # Chỉ các bước trước bước đang dựng báo cáo (bước hiện tại chưa có kết quả)
        steps = [x for x in self.completed_outputs() if self.step is None or x["seq"] < self.step]
        summary_rows = []
        for s in steps:
            out = s["output"] or {}
            summary_rows.append({"seq": s["seq"], "tool": s["tool"], "goal": s["goal"], "status": s["status"],
                                 "summary": out.get("summary") or (s["error"] or {}).get("message")})
        sp["sheets"].append(S.table("Tóm tắt", [
            {"key": "seq", "label": "#", "type": "number"}, {"key": "tool", "label": "Công cụ"}, {"key": "goal", "label": "Mục tiêu"},
            {"key": "status", "label": "Trạng thái"}, {"key": "summary", "label": "Kết quả"}], summary_rows,
            title="Tóm tắt các bước đã thực hiện"))
        used = {"Tóm tắt"}
        for s in steps:
            out = s["output"] or {}
            for sec in out.get("sections") or []:
                name = sec["name"][:28]
                base, k = name, 2
                while fold(name) in {fold(u) for u in used}:
                    name, k = f"{base[:26]} {k}", k + 1
                used.add(name)
                rows = []
                for r in sec["rows"]:
                    r = dict(r)
                    if r.get("_src"):
                        r["_src"] = [f"{src_ids.get(fid, '?')}" + (f" · {loc}" if loc else "") for fid, loc in r["_src"] if fid][:4]
                    rows.append(r)
                sp["sheets"].append(S.table(name, [dict(c) for c in sec["columns"]], rows, title=sec.get("title"),
                                            totals=sec.get("totals") or [], charts=sec.get("charts") or [], notes=sec.get("notes") or []))
            for w in out.get("warnings") or []:
                sp["warnings"].append({"level": "warning", "message": w})
            for n in out.get("notes") or []:
                if n not in sp["notes"]:
                    sp["notes"].append(n)
        for s in steps:
            if s["status"] in ("FAILED", "NEEDS_INPUT"):
                sp["warnings"].append({"level": "error" if s["status"] == "FAILED" else "input",
                                       "message": f"Bước {s['seq']} ({s['tool']}) {s['status']}: {(s['error'] or {}).get('message', '')}"})
        if sp["notes"]:
            sp["sheets"][0]["notes"] = sp["notes"][:20]
        return sp

    def make_artifact(self, kind, title=None):
        if kind == "pdf":
            prev = db.one("SELECT * FROM artifacts WHERE org_id=? AND task_id=? AND kind='xlsx' ORDER BY created_at DESC LIMIT 1",
                          (self.ctx.org_id, self.task["id"]))
            sp = db.loads(prev["spec_json"]) if prev else self.compose_spec(title)
            data = pdfr.render(sp)
            validation = {"ok": True, "checks": [{"ok": True, "check": "PDF dựng từ cùng spec đã xác minh của báo cáo Excel"
                                                  if prev else "PDF dựng từ spec"}]}
            return self._store(kind, sp, data, validation, root=None, parent=None, version=1)
        sp = self.compose_spec(title)
        data, layout = xl.render(sp)
        validation = xl.verify(data, sp, layout)
        if not validation["ok"]:
            raise tools.ToolInputError("Báo cáo Excel không qua xác minh: " + "; ".join(c["check"] for c in validation["checks"] if not c["ok"])[:500])
        return self._store("xlsx", sp, data, validation, root=None, parent=None, version=1)

    def revise_artifact(self, artifact_id, ops):
        a = db.one("SELECT * FROM artifacts WHERE id=? AND org_id=?", (artifact_id, self.ctx.org_id))
        if not a or a["kind"] != "xlsx" or not a["spec_json"]:
            raise tools.ToolInputError("Không tìm thấy báo cáo Excel để sửa")
        try:
            sp, log = S.apply_ops(db.loads(a["spec_json"]), ops)
        except S.OpError as e:
            raise tools.NeedsInput(str(e), e.details) from e
        data, layout = xl.render(sp)
        validation = xl.verify(data, sp, layout)
        if not validation["ok"]:
            raise tools.ToolInputError("Phiên bản mới không qua xác minh")
        latest = db.one("SELECT max(version) v FROM artifacts WHERE root_id=?", (a["root_id"],))["v"]
        out = self._store("xlsx", sp, data, validation, root=a["root_id"], parent=a["id"], version=latest + 1)
        out["summary"] = f"Phiên bản {latest + 1}: " + "; ".join(log)
        out["data"]["changes"] = log
        return out

    def _store(self, kind, sp, data, validation, root, parent, version):
        aid = db.new_id()
        root = root or aid
        slug = re.sub(r"[^0-9a-z]+", "_", fold(sp["title"]))[:50].strip("_") or "bao_cao"
        name = f"{slug}_v{version}.{kind}"
        rel, sha, size = storage.put_artifact(self.ctx.org_id, aid, kind, data)
        with db.tx() as c:
            db.insert(c, "artifacts", {
                "id": aid, "org_id": self.ctx.org_id, "task_id": self.task["id"], "conversation_id": self.task["conversation_id"],
                "root_id": root, "parent_id": parent, "version": version, "name": name, "kind": kind,
                "spec_json": db.dumps(sp), "sha256": sha, "size": size, "storage_path": rel,
                "validation_json": db.dumps(validation), "created_by": self.ctx.user, "created_at": db.now(),
            })
            audit.log(c, self.ctx.org_id, self.ctx.user, "artifact.create", "artifact", aid, kind=kind, sha256=sha,
                      version=version, parent=parent, task=self.task["id"], verified=validation["ok"])
            _event(c, self.ctx.org_id, self.task["id"], "artifact", f"Đã tạo {name}", {"artifact_id": aid, "name": name, "kind": kind})
        return {"summary": f"Đã tạo {name} ({size // 1024 + 1} KB), xác minh: {'đạt' if validation['ok'] else 'KHÔNG đạt'}",
                "data": {"artifact_id": aid, "name": name, "kind": kind, "version": version, "verified": validation["ok"],
                         "checks": len(validation.get("checks", []))}, "sections": []}


def _vn(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso and len(iso) >= 10 else (iso or "")


def conversation_artifacts(org_id, conversation_id):
    """Phiên bản mới nhất của mỗi báo cáo Excel trong hội thoại (cho planner)."""
    if not conversation_id:
        return []
    rows = db.all_("""SELECT a.* FROM artifacts a WHERE a.org_id=? AND a.conversation_id=? AND a.kind='xlsx'
                      AND a.version=(SELECT max(version) FROM artifacts b WHERE b.root_id=a.root_id)
                      ORDER BY a.created_at DESC LIMIT 5""", (org_id, conversation_id))
    out = []
    for a in rows:
        sp = db.loads(a["spec_json"], {})
        out.append({"id": a["id"], "name": a["name"], "version": a["version"],
                    "sheets": [{"name": s["name"], "columns": s["columns"], "rows_preview": s["rows"][:500]} for s in sp.get("sheets", [])]})
    return out


# ── Thực thi ─────────────────────────────────────────────────────
TRANSIENT = (llm.LLMError, TimeoutError, sqlite3.OperationalError, ConnectionError)


def _insert_steps(task, steps, start_seq):
    with db.tx() as c:
        for i, s in enumerate(steps):
            t = tools.REGISTRY[s["tool"]]
            db.insert(c, "task_steps", {
                "id": db.new_id(), "org_id": task["org_id"], "task_id": task["id"], "seq": start_seq + i, "tool": s["tool"],
                "goal": s["goal"], "params_json": db.dumps(s.get("params") or {}), "depends_json": db.dumps(s.get("depends") or []),
                "task_class": t.task_class, "risk": t.risk, "approval_required": 1 if t.task_class == tools.COMMIT else 0,
                "status": "PENDING", "attempts": 0, "started_at": None, "finished_at": None, "output_json": None, "error_json": None,
            })


def execute(task_id, worker_id="w"):
    with telemetry.span("task", task=task_id, org=db.current_org() or "", worker=worker_id) as sp:
        _execute(task_id, worker_id)
        t = db.one("SELECT status, plan_source FROM tasks WHERE id=?", (task_id,))
        sp.set_attribute("status", t["status"])
        sp.set_attribute("plan_source", t["plan_source"] or "")


def _execute(task_id, worker_id):
    task = db.one("SELECT * FROM tasks WHERE id=?", (task_id,))
    cfg = settings.get()
    try:
        run = Run(task, worker_id)
    except security.NotFound:
        transition(task_id, "FAILED", error_json=db.dumps({"code": "no_access", "message": "Người tạo không còn quyền trong tổ chức"}))
        return
    org = task["org_id"]
    started = task["created_at"]
    steps = db.all_("SELECT * FROM task_steps WHERE task_id=? ORDER BY seq", (task_id,))
    if not steps:
        _insert_steps(task, [{"tool": "inspect_files", "goal": "Kiểm tra chứng từ đầu vào"},
                             {"tool": "extract_documents", "goal": "Đọc và trích xuất dữ liệu có provenance"}], 1)
    try:
        while True:
            if run.cancelled():
                transition(task_id, "CANCELLED", expect={"RUNNING"})
                return
            if time.time() - started > float(cfg["task_timeout_s"]):
                raise _Fatal("timeout", "Tác vụ vượt quá thời gian tối đa")
            step = db.one("SELECT * FROM task_steps WHERE task_id=? AND status IN ('PENDING','RUNNING') ORDER BY seq LIMIT 1", (task_id,))
            if step is None:
                task = db.one("SELECT * FROM tasks WHERE id=?", (task_id,))
                if task["plan_json"] is None:
                    if _plan(run, task):
                        continue
                    return  # WAITING_FOR_INPUT
                break
            _run_step(run, step)
        _verify_and_finish(run)
    except Retry as r:
        transition(task_id, "RETRY_SCHEDULED", expect={"RUNNING"}, not_before=db.now() + r.delay, lease_until=None,
                   worker_id=None, attempts=task["attempts"] + 1)
        event(org, task_id, "info", f"Sẽ thử lại sau {r.delay:.0f} giây: {r}")
    except _Fatal as f:
        _fail(task_id, org, f.code, str(f))
    except Exception as e:  # lỗi không lường trước: dừng an toàn, giữ toàn bộ dữ liệu đã xử lý
        traceback.print_exc()
        _fail(task_id, org, "internal", f"Lỗi nội bộ ({type(e).__name__}) — dữ liệu đã xử lý được giữ nguyên")


class _Fatal(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def _fail(task_id, org, code, msg, dead_letter=False):
    try:
        transition(task_id, "FAILED", error_json=db.dumps({"code": code, "message": msg, "dead_letter": dead_letter}),
                   lease_until=None)
    except TransitionError:
        return
    with db.tx() as c:
        audit.log(c, org, "agent", "task.fail", "task", task_id, code=code, message=msg)
    _assistant_message(task_id)


def _plan(run, task):
    m = run.manifest(refresh=True)
    arts = conversation_artifacts(task["org_id"], task["conversation_id"])
    event(task["org_id"], task["id"], "info", "Đang lập kế hoạch thực hiện…")
    with telemetry.span("plan", task=task["id"]) as sp:
        history = [r["command"] for r in db.all_(
            "SELECT command FROM tasks WHERE org_id=? AND conversation_id=? AND created_at<? AND id!=? ORDER BY created_at DESC LIMIT 4",
            (task["org_id"], task["conversation_id"], task["created_at"], task["id"]))][::-1] if task["conversation_id"] else []
        steps, questions, unsupported, source, note = planner.plan(task["command"], m, arts, policy.allowed_classes(run.ctx), history)
        sp.set_attribute("source", source)
        sp.set_attribute("steps", len(steps))
    if note:
        event(task["org_id"], task["id"], "warning", note)
    if not run.file_ids:
        # Phiên chưa có chứng từ: chỉ giữ truy vấn sổ sách của tổ chức, không xử lý dữ liệu ở phiên khác
        kept = [s for s in steps if s["tool"] in ORG_WIDE_TOOLS]
        if len(kept) < len([s for s in steps if s["tool"] not in ("generate_excel", "generate_pdf")]) or (not steps and not questions and not unsupported):
            questions = ["Phiên làm việc này chưa có chứng từ nào — hãy kéo thả file cần xử lý rồi gửi lại yêu cầu."] + questions
        steps = kept + ([s for s in steps if s["tool"] in ("generate_excel", "generate_pdf")] if kept else [])
    if not steps and not questions and run.file_ids and not unsupported:
        # Không có phân tích phù hợp: vẫn trả báo cáo kết quả đọc chứng từ để người dùng thấy dữ liệu đã nhận diện
        steps = [{"tool": "generate_excel", "goal": "Tạo báo cáo kết quả đọc chứng từ", "params": {}}]
    with db.tx() as c:
        c.execute("UPDATE tasks SET plan_json=?, plan_source=?, updated_at=? WHERE id=?",
                  (db.dumps({"steps": steps, "questions": questions, "unsupported": unsupported}), source, db.now(), task["id"]))
        _event(c, task["org_id"], task["id"], "plan", f"Kế hoạch {len(steps)} bước ({'AI' if source == 'llm' else 'quy tắc'})",
               {"steps": [{"tool": s["tool"], "goal": s["goal"]} for s in steps], "questions": questions,
                "unsupported": unsupported, "source": source})
        audit.log(c, task["org_id"], "agent", "task.plan", "task", task["id"], source=source,
                  model=planner.hubcfg.model("genreport") if source == "llm" else None, steps=[s["tool"] for s in steps])
    if steps:
        _insert_steps(task, steps, 3)
        return True
    if questions:
        with db.tx() as c:
            c.execute("UPDATE tasks SET summary_json=? WHERE id=?", (db.dumps({"questions": questions, "unsupported": unsupported}), task["id"]))
        transition(task["id"], "WAITING_FOR_INPUT", expect={"RUNNING"}, lease_until=None, worker_id=None)
        _assistant_message(task["id"])
        return False
    return True  # không có bước phân tích: vẫn tổng kết phần trích xuất


# Không cần chứng từ của phiên: đọc sổ sách đã ghi của tổ chức; sửa báo cáo đã có trong hội thoại
ORG_WIDE_TOOLS = ("query_accounting_database", "revise_artifact")
NO_ANSWER_TOOLS = ("inspect_files", "extract_documents", "generate_excel", "generate_pdf", "revise_artifact", "create_review_request")


def _has_report_content(run):
    """Có kết quả phân tích để đưa vào file chưa (ngoài danh sách chứng từ / kết quả đọc)?"""
    steps = [s for s in run.completed_outputs() if s["seq"] < run.step and s["tool"] not in NO_ANSWER_TOOLS]
    if not steps:
        return True  # chỉ có báo cáo kết quả đọc chứng từ (người dùng không yêu cầu phân tích cụ thể)
    return any(s["status"] == "COMPLETED" and any(sec.get("rows") for sec in (s["output"] or {}).get("sections") or [])
               for s in steps)


def _backoff(attempt):
    base = min(300, 5 * (2 ** attempt))
    return base * (0.5 + random.random() / 2)  # jitter: tránh dồn dập thử lại


def _run_step(run, step):
    tool = tools.REGISTRY[step["tool"]]
    cfg = run.settings
    run.step = step["seq"]
    run._warnings, run._notes, run._questions = [], [], []
    with db.tx() as c:
        c.execute("UPDATE task_steps SET status='RUNNING', attempts=attempts+1, started_at=? WHERE id=?", (db.now(), step["id"]))
        c.execute("UPDATE tasks SET lease_until=? WHERE id=?", (db.now() + float(cfg["lease_s"]), step["task_id"]))
        _event(c, step["org_id"], step["task_id"], "step_start", f"Bước {step['seq']}: {step['goal']}",
               {"seq": step["seq"], "tool": step["tool"], "class": step["task_class"]})
    params = db.loads(step["params_json"], {})
    ok, why = policy.allow(tool, run.task["command"], policy.allowed_classes(run.ctx))
    t0 = time.time()
    try:
        if step["tool"] in ("generate_excel", "generate_pdf") and not _has_report_content(run):
            _finish_step(step, "SKIPPED", {"summary": "Không tạo file vì các bước phân tích không có kết quả", "sections": []}, None,
                         "Bỏ qua tạo file: không có kết quả để đưa vào báo cáo")
            return
        if not ok:
            raise tools.ToolInputError(f"Bị chính sách từ chối: {why}")
        if not run.ctx.can(tool.permission):
            raise tools.ToolInputError(f"Vai trò không có quyền '{tool.permission}'")
        tools.check_params(step["tool"], params)
        with telemetry.span("tool", tool=step["tool"], task=step["task_id"], task_class=step["task_class"]):
            out = tool.handler(run, params)
        out.setdefault("sections", [])
        out["warnings"] = run._warnings
        out["notes"] = run._notes
        out["questions"] = run._questions
        out["elapsed_s"] = round(time.time() - t0, 2)
        if time.time() - t0 > tool.timeout_s:
            run.warn(f"Bước {step['seq']} chạy {time.time() - t0:.0f}s, vượt timeout khai báo {tool.timeout_s}s")
        _finish_step(step, "COMPLETED", out, None, f"Xong: {out.get('summary', '')}")
    except tools.NeedsInput as e:
        _finish_step(step, "NEEDS_INPUT", {"summary": str(e), "sections": [], "warnings": run._warnings, "notes": run._notes},
                     {"code": "needs_input", "message": str(e), "details": e.details}, f"Cần bổ sung: {e}")
    except (tools.ToolInputError, SchemaError, S.OpError, ValueError) as e:
        _finish_step(step, "FAILED", None, {"code": "input", "message": str(e)}, f"Lỗi: {e}")
        if tool.failure == "fail_task":
            raise _Fatal("step_failed", f"Bước {step['seq']} ({step['tool']}) thất bại: {e}") from e
    except TRANSIENT as e:
        if step["attempts"] + 1 < int(cfg["step_max_attempts"]):
            with db.tx() as c:
                c.execute("UPDATE task_steps SET status='PENDING', error_json=? WHERE id=?",
                          (db.dumps({"code": "transient", "message": str(e)[:300]}), step["id"]))
            raise Retry(f"{step['tool']}: {str(e)[:200]}", _backoff(step["attempts"])) from e
        _finish_step(step, "FAILED", None, {"code": "transient_exhausted", "message": str(e)[:300]}, f"Lỗi sau {step['attempts'] + 1} lần thử: {e}")
        if tool.failure == "fail_task":
            raise _Fatal("step_failed", str(e)) from e


def _finish_step(step, status, out, err, msg):
    with db.tx() as c:
        c.execute("UPDATE task_steps SET status=?, finished_at=?, output_json=?, error_json=? WHERE id=?",
                  (status, db.now(), db.dumps(out) if out is not None else None, db.dumps(err) if err else None, step["id"]))
        _event(c, step["org_id"], step["task_id"], "step_done" if status == "COMPLETED" else "step_error", msg[:500],
               {"seq": step["seq"], "tool": step["tool"], "status": status})
        audit.log(c, step["org_id"], "agent", "tool.invoke", "task_step", step["id"], tool=step["tool"], status=status,
                  params=db.loads(step["params_json"], {}), error=err)


def _verify_and_finish(run):
    task_id, org = run.task["id"], run.ctx.org_id
    transition(task_id, "VERIFYING", expect={"RUNNING"})
    steps = run.completed_outputs()
    problems = []
    for s in steps:
        if s["tool"] in ("generate_excel", "revise_artifact") and s["status"] == "COMPLETED":
            aid = s["output"]["data"]["artifact_id"]
            a = db.one("SELECT * FROM artifacts WHERE id=? AND org_id=?", (aid, org))
            if not a or not storage.verify(a["storage_path"], a["sha256"]) or not db.loads(a["validation_json"], {}).get("ok"):
                problems.append(f"Artifact {aid[:8]} không toàn vẹn hoặc chưa qua xác minh")
    required = [s for s in steps if s["tool"] in ("generate_excel", "revise_artifact") and s["status"] != "SKIPPED"]
    if any(s["status"] != "COMPLETED" for s in required) or problems:
        _fail(task_id, org, "verification", "; ".join(problems) or "Không tạo được báo cáo bắt buộc")
        return
    bad = [s for s in steps if s["status"] in ("FAILED", "NEEDS_INPUT")]
    summary = {"steps": [{"seq": s["seq"], "tool": s["tool"], "status": s["status"],
                          "summary": (s["output"] or {}).get("summary") or (s["error"] or {}).get("message"),
                          "answer": (s["output"] or {}).get("answer") if s["status"] == "COMPLETED" else None} for s in steps],
               "questions": [(s["error"] or {}).get("message") for s in steps if s["status"] == "NEEDS_INPUT"]}
    plan = db.loads(db.one("SELECT plan_json FROM tasks WHERE id=?", (task_id,))["plan_json"], {}) or {}
    summary["unsupported"] = plan.get("unsupported") or []
    summary["questions"] += plan.get("questions") or []
    for s in steps:
        for q in (s["output"] or {}).get("questions") or []:
            if q not in summary["questions"]:
                summary["questions"].append(q)
    # Còn câu hỏi / phần không làm được → không báo hoàn thành trọn vẹn
    status = "PARTIALLY_COMPLETED" if bad or summary["questions"] or summary["unsupported"] else "COMPLETED"
    transition(task_id, status, expect={"VERIFYING"}, summary_json=db.dumps(summary), lease_until=None)
    with db.tx() as c:
        audit.log(c, org, "agent", "task.finish", "task", task_id, status=status)
    _assistant_message(task_id)


def _assistant_message(task_id):
    """Tin nhắn kết quả trong hội thoại — tổng hợp xác định từ kết quả công cụ (không để AI viết số liệu)."""
    t = db.one("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not t["conversation_id"]:
        return
    summ = db.loads(t["summary_json"], {}) or {}
    steps = summ.get("steps") or []
    # Đoạn đầu: câu trả lời trực tiếp (số liệu do công cụ tính, không do AI viết); sau một dòng trống: chi tiết các bước
    answer = []
    tools_run = {s["tool"] for s in steps if s["status"] == "COMPLETED"}
    # Kiểm tra/trùng lặp là bước phụ khi người dùng hỏi tổng hợp, định khoản… → để ở phần chi tiết
    asked_check = any(w in fold(t["command"]) for w in ("kiem tra", "doc ", "doc hoa don", "van de", "loi", "sai", "hop le", "check", "trung"))
    secondary = {"validate_invoices", "detect_duplicates"} if tools_run & set(planner.NEEDS_VALIDATION) and not asked_check else set()
    for s in steps:
        if s["status"] != "COMPLETED" or s["tool"] in NO_ANSWER_TOOLS or s["tool"] in secondary:
            continue
        a = s.get("answer") or s.get("summary")
        if a and a not in answer:
            answer.append(a)
    questions = [q for q in summ.get("questions") or [] if q]
    unsupported = summ.get("unsupported") or []
    if t["status"] == "FAILED":
        answer = [f"Không hoàn thành: {(db.loads(t['error_json'], {}) or {}).get('message', '')}"] + answer
    elif not answer and unsupported and not questions:
        answer = ["Yêu cầu này nằm ngoài những việc trợ lý kế toán làm được: " + " ".join(unsupported)]
        unsupported = []
    elif not answer and questions:
        answer = ["Mình cần thêm thông tin để trả lời:"]
    elif not answer:
        answer = ["Đã xử lý xong nhưng không có kết quả phân tích nào để báo." if t["status"] == "COMPLETED"
                  else "Chưa trả lời được yêu cầu — xem chi tiết bên dưới."]
    lines = answer[:]
    for q in questions:
        lines.append(f"❓ {q}")
    for u in unsupported:
        lines.append(f"⛔ {u}")
    detail = []
    for s in steps:
        if s["tool"] in ("inspect_files",) or not s.get("summary"):
            continue
        if s["status"] == "COMPLETED" and s.get("summary") in answer:
            continue
        mark = {"COMPLETED": "✓", "FAILED": "✗", "NEEDS_INPUT": "?", "SKIPPED": "–"}.get(s["status"], "•")
        detail.append(f"{mark} {s['summary']}")
    if detail:
        lines += ["", "Chi tiết:"] + detail
    with db.tx() as c:
        db.insert(c, "messages", {"id": db.new_id(), "org_id": t["org_id"], "conversation_id": t["conversation_id"],
                                  "role": "assistant", "content": "\n".join(lines)[:8000], "task_id": task_id,
                                  "created_by": "agent", "created_at": db.now()})
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (db.now(), t["conversation_id"]))

