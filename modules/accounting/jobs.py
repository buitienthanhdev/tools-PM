"""
Hàng đợi tác vụ bền vững trên bảng tasks (SQLite) + worker thread.

- Nhận việc bằng giao dịch BEGIN IMMEDIATE (một worker một task), có lease có hạn.
- Task RUNNING mà lease hết hạn (worker/process chết) được nhận lại và chạy tiếp từ bước chưa xong.
- RETRY_SCHEDULED chỉ được nhận sau not_before (backoff + jitter đã tính ở runner).
- Quá số lần thử → FAILED với dead_letter=true (giữ nguyên dữ liệu để điều tra).
Worker có thể chạy trong tiến trình web (mặc định) hoặc tiến trình riêng: python -m modules.accounting.jobs
"""

import os
import threading
import time
import uuid

from . import db, settings

MAX_TASK_ATTEMPTS = 5
_wake = threading.Event()
_started = False
_lock = threading.Lock()


def wake():
    _wake.set()


def claim(worker_id):
    lease = float(settings.get()["lease_s"])
    now = db.now()
    with db.tx() as c:
        row = c.execute(
            """SELECT id, status, attempts FROM tasks
               WHERE (status IN ('QUEUED','RETRY_SCHEDULED') AND not_before <= ?)
                  OR (status = 'RUNNING' AND lease_until IS NOT NULL AND lease_until < ?)
               ORDER BY created_at LIMIT 1""", (now, now)).fetchone()
        if not row:
            return None
        if row["status"] == "RUNNING" or row["attempts"] >= MAX_TASK_ATTEMPTS:
            recovered = row["status"] == "RUNNING"
            if row["attempts"] >= MAX_TASK_ATTEMPTS:
                c.execute("""UPDATE tasks SET status='FAILED', version=version+1, updated_at=?, lease_until=NULL,
                             error_json=? WHERE id=?""",
                          (now, db.dumps({"code": "dead_letter", "message": "Vượt số lần thử tối đa", "dead_letter": True}), row["id"]))
                c.execute("INSERT INTO task_events (org_id, task_id, ts, kind, message) SELECT org_id, id, ?, 'status', ? FROM tasks WHERE id=?",
                          (now, f"{row['status']} → FAILED (dead letter)", row["id"]))
                return None
            if recovered:
                c.execute("INSERT INTO task_events (org_id, task_id, ts, kind, message) SELECT org_id, id, ?, 'info', ? FROM tasks WHERE id=?",
                          (now, "Tiếp tục tác vụ bị gián đoạn từ bước chưa hoàn tất", row["id"]))
        n = c.execute("""UPDATE tasks SET status='RUNNING', worker_id=?, lease_until=?, version=version+1, updated_at=?,
                         attempts=attempts + (CASE WHEN status='RUNNING' THEN 1 ELSE 0 END)
                         WHERE id=? AND status=?""", (worker_id, now + lease, now, row["id"], row["status"])).rowcount
        if n != 1:
            return None
        if row["status"] != "RUNNING":
            c.execute("INSERT INTO task_events (org_id, task_id, ts, kind, message) SELECT org_id, id, ?, 'status', ? FROM tasks WHERE id=?",
                      (now, f"{row['status']} → RUNNING", row["id"]))
        # Bước đang RUNNING của lần chạy trước (bị gián đoạn) quay về PENDING để chạy lại (bước idempotent)
        c.execute("UPDATE task_steps SET status='PENDING' WHERE task_id=? AND status='RUNNING'", (row["id"],))
        return row["id"]


def run_once(worker_id="inline"):
    """Nhận và chạy một task (dùng trong test và worker)."""
    from .agent import runner

    tid = claim(worker_id)
    if tid:
        runner.execute(tid, worker_id)
    return tid


def _loop(worker_id):
    while True:
        try:
            if not run_once(worker_id):
                _wake.wait(2.0)
                _wake.clear()
        except Exception as e:  # worker không bao giờ chết vì một task lỗi
            print(f"[accounting-worker {worker_id}] {type(e).__name__}: {e}")
            time.sleep(2)


def start_workers():
    global _started
    with _lock:
        if _started:
            return
        _started = True
    n = max(1, int(settings.get()["workers"]))
    for i in range(n):
        wid = f"{os.getpid()}-{i}-{uuid.uuid4().hex[:6]}"
        threading.Thread(target=_loop, args=(wid,), daemon=True, name=f"accounting-worker-{i}").start()


if __name__ == "__main__":
    print("[accounting] worker riêng đang chạy")
    _loop(f"standalone-{os.getpid()}")
