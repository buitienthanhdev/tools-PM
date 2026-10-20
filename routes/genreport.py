"""GenReport: AI viết báo cáo tiến độ + xuất Word."""

import threading
import traceback

from flask import Blueprint, jsonify, request

from core.jobs import jobs, new_job

bp = Blueprint("genreport", __name__)


def worker_genreport(job_id, form_data):
    jobs[job_id].update(
        {
            "status": "processing",
            "progress": 15,
            "message": "[1/3] Đang nạp dữ liệu & khởi tạo AI local...",
        }
    )
    try:
        import genreport_service

        jobs[job_id].update(
            {
                "progress": 40,
                "message": "[2/3] AI local đang tổng hợp suy luận kỹ thuật chuyên sâu...",
            }
        )

        res = genreport_service.generate_word_report(form_data)

        jobs[job_id].update(
            {
                "progress": 90,
                "message": "[3/3] Đang đóng gói & map dữ liệu vào mẫu Word chuẩn (.docx)...",
            }
        )

        jobs[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "message": "🎉 Đã tạo báo cáo tiến độ kỹ thuật & file Word thành công!",
                "result": res,
            }
        )
    except Exception as e:
        jobs[job_id].update(
            {
                "status": "failed",
                "progress": 0,
                "message": f"Lỗi tạo báo cáo: {e}",
                "error": traceback.format_exc(),
            }
        )


# ── API: GenReport Generate ──────────────────────────────────
@bp.route("/api/genreport/generate", methods=["POST"])
def api_genreport_generate():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            data = request.form.to_dict()

        if not data:
            return jsonify({"error": "Dữ liệu báo cáo không hợp lệ"}), 400

        job_id = new_job("Khởi tạo tác vụ GenReport...")
        threading.Thread(
            target=worker_genreport, args=(job_id, data), daemon=True
        ).start()
        return jsonify({"job_id": job_id, "status": "queued"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
