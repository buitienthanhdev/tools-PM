"""Trạng thái tác vụ (có kiểm tra chủ sở hữu) + xuất file bóc băng."""

import json
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from core import auth
from core.jobs import jobs

bp = Blueprint("jobs", __name__)


# ── API: Job Status & SSE Stream ─────────────────────────────
@bp.route("/api/job/<job_id>")
def api_job(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Tác vụ không tồn tại"}), 404
    denied = auth.check_job_owner(jobs[job_id])
    if denied:
        return denied
    return jsonify({k: v for k, v in jobs[job_id].items() if k != "owner"})


@bp.route("/api/job/<job_id>/stream")
def api_job_stream(job_id):
    if job_id in jobs:
        denied = auth.check_job_owner(jobs[job_id])
        if denied:
            return denied

    def generate():
        # Giới hạn 2 phút/kết nối: client mất mạng mà không đóng thì luồng vẫn được trả lại;
        # EventSource phía trình duyệt tự nối lại (jobTracker.verifyAndStreamJob).
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if job_id not in jobs:
                yield f'data: {json.dumps({"error": "Tác vụ không tìm thấy"})}\n\n'
                break
            job = jobs[job_id]
            pub = {k: v for k, v in job.items() if k != "owner"}
            yield f"data: {json.dumps(pub)}\n\n"
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.4)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── API: Export ───────────────────────────────────────────────
@bp.route("/api/export/<fmt>", methods=["POST"])
def api_export(fmt):
    data = request.json or {}
    result = data.get("result", {})
    text = result.get("text", "")
    segments = result.get("segments", [])

    def srt_time(s):
        m, sc = divmod(int(s), 60)
        h, m = divmod(m, 60)
        ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"

    def vtt_time(s):
        m, sc = divmod(int(s), 60)
        h, m = divmod(m, 60)
        ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sc:02d}.{ms:03d}"

    if fmt == "txt":
        content, mime, name = text, "text/plain", "transcription.txt"
    elif fmt == "srt":
        lines = [
            f'{i}\n{srt_time(s["start"])} --> {srt_time(s["end"])}\n{s["text"]}\n'
            for i, s in enumerate(segments, 1)
        ]
        content, mime, name = "\n".join(lines), "text/plain", "transcription.srt"
    elif fmt == "vtt":
        lines = ["WEBVTT\n"] + [
            f'{vtt_time(s["start"])} --> {vtt_time(s["end"])}\n{s["text"]}\n'
            for s in segments
        ]
        content, mime, name = "\n".join(lines), "text/vtt", "transcription.vtt"
    else:
        return jsonify({"error": f"Unsupported format: {fmt}"}), 400

    return Response(
        content,
        mimetype=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
