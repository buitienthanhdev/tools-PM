"""Flask blueprint: /api/cv/*"""

import threading
import time
import traceback
import uuid

from flask import Blueprint, jsonify, request

from core import auth

from . import engine

bp = Blueprint("reviewingcv", __name__, url_prefix="/api/cv")
_jobs = {}
JOB_TTL = 3600


def _run(job, cv_text, job_text, notes, lang, cover):
    try:
        job["msg"] = "Đang chấm"
        job.update(
            result=engine.review(cv_text, job_text, notes, lang, cover),
            status="done",
        )
    except Exception as e:
        traceback.print_exc()
        job.update(status="error", error=str(e))


@bp.route("/status")
def status():
    return jsonify(engine.status())


@bp.route("/review", methods=["POST"])
def review():
    st = engine.status()
    if not st["llm"]:
        return jsonify({"error": st["error"]}), 503
    cv_text = request.form.get("cv_text") or ""
    f = request.files.get("cv_file")
    try:
        if f and f.filename:
            cv_text = engine.extract_text(f.filename, f.read())
    except ImportError as e:
        return jsonify({"error": f"Thiếu thư viện đọc file: {e.name}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    job_text = (request.form.get("job_text") or "").strip()
    if len(cv_text.strip()) < 50:
        return jsonify({"error": "Cần CV (tải file hoặc dán nội dung)"}), 400
    if len(job_text) < 50:
        return jsonify({"error": "Cần dán nội dung tin tuyển dụng"}), 400

    now = time.time()
    for k in [k for k, j in _jobs.items() if now - j["t"] > JOB_TTL]:
        _jobs.pop(k, None)
    jid = uuid.uuid4().hex[:10]
    user = auth.current_user()
    job = _jobs[jid] = {
        "status": "running",
        "msg": "Đang chờ lượt",
        "t": now,
        "owner": user["email"] if user else None,
    }
    threading.Thread(
        target=_run,
        args=(
            job,
            cv_text,
            job_text,
            (request.form.get("notes") or "").strip()[:4000],
            request.form.get("lang") or "vi",
            request.form.get("cover") == "1",
        ),
        daemon=True,
    ).start()
    return jsonify({"job": jid, "cv_chars": len(cv_text)})


@bp.route("/jobs/<jid>")
def job_status(jid):
    job = _jobs.get(jid)
    if not job:
        return jsonify(
            {
                "status": "error",
                "error": "Không thấy tác vụ (có thể server vừa khởi động lại)",
            }
        )
    denied = auth.check_job_owner(job)
    if denied:
        return denied
    return jsonify({k: v for k, v in job.items() if k not in ("t", "owner")})
