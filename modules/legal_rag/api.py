"""Flask blueprint: /api/legal/*"""

import os
import threading
import uuid

from flask import Blueprint, jsonify, request

from . import engine

bp = Blueprint("legal", __name__, url_prefix="/api/legal")
_jobs = {}


def _guard():
    from core import auth

    if auth.is_admin():
        return None
    return jsonify({"error": "Chỉ admin mới nạp hoặc xoá văn bản luật"}), 403


@bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    q = (data.get("question") or "").strip()
    if not q:
        return jsonify({"error": "Vui lòng nhập câu hỏi"}), 400
    return jsonify(engine.answer(q[:2000], data.get("history") or []))


@bp.route("/status")
def status():
    from core import config as hubcfg
    from core import llm

    st = llm.status(hubcfg.model("legal"))
    return jsonify(
        {
            "laws": len(engine.list_laws()),
            "llm": st["ok"],
            "model": st["model"],
            "error": st.get("error"),
            "index": engine.index_status(),
        }
    )


@bp.route("/admin/login", methods=["POST"])
def admin_login():
    return _guard() or jsonify({"ok": True})


@bp.route("/admin/laws", methods=["GET"])
def admin_list():
    return _guard() or jsonify({"laws": engine.list_laws()})


def _run_job(job, name, filename, data):
    try:
        text = engine.extract_text(
            filename,
            data,
            lambda d, t: job.update(msg=f"Đang đọc trang {d}/{t}…", pct=d * 100 // t),
        )
        if not text.strip():
            raise ValueError("Không đọc được chữ nào từ file")
        doc = engine.add_law(name, text)
        job.update(msg="Đang tạo chỉ mục vector…", pct=90)
        idx = engine.get_index(rebuild=True)
        job.update(
            status="done",
            pct=100,
            articles=len(doc["chunks"]),
            warnings=doc["quality"]["warnings"],
            vectors=idx.vecs is not None,
        )
    except ImportError as e:
        job.update(status="error", error=f"Thiếu thư viện đọc file: {e.name}")
    except Exception as e:
        job.update(status="error", error=str(e))


@bp.route("/admin/laws", methods=["POST"])
def admin_add():
    if (g := _guard()) is not None:
        return g
    name = (request.form.get("name") or "").strip()
    text = request.form.get("text") or ""
    f = request.files.get("file")
    if f:  # file có thể là PDF scan cần OCR lâu → chạy nền, client poll
        name = name or os.path.splitext(f.filename)[0]
        job = {"status": "running", "pct": 0, "msg": "Đang xử lý file…"}
        jid = uuid.uuid4().hex[:8]
        _jobs[jid] = job
        threading.Thread(
            target=_run_job, args=(job, name, f.filename, f.read()), daemon=True
        ).start()
        return jsonify({"ok": True, "job": jid})
    try:
        if not name or not text.strip():
            return (
                jsonify({"error": "Cần tên luật và nội dung (dán text hoặc tải file)"}),
                400,
            )
        doc = engine.add_law(name, text)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    idx = engine.get_index(rebuild=True)
    return jsonify(
        {
            "ok": True,
            "articles": len(doc["chunks"]),
            "warnings": doc["quality"]["warnings"],
            "vectors": idx.vecs is not None,
        }
    )


@bp.route("/admin/jobs/<jid>")
def admin_job(jid):
    if (g := _guard()) is not None:
        return g
    return jsonify(_jobs.get(jid) or {"status": "error", "error": "Không thấy tác vụ"})


@bp.route("/admin/reindex", methods=["POST"])
def admin_reindex():
    if (g := _guard()) is not None:
        return g
    try:
        return jsonify({"ok": True, **engine.reindex()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/admin/laws/<doc_id>", methods=["DELETE"])
def admin_delete(doc_id):
    if (g := _guard()) is not None:
        return g
    return jsonify({"ok": engine.delete_law(doc_id)})
