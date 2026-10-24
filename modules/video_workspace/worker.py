"""
Worker chạy nền trong tiến trình Hub: lấy job từ hàng đợi SQLite, chạy pipeline (tiến trình con), ghi tiến độ.

- Một job mỗi "khe" GPU; số khe = gpu_concurrency. Khe là khoá file (msvcrt/fcntl) → giới hạn cả khi có nhiều tiến trình
  Hub (staging + production) dùng chung GPU; khoá tự nhả khi tiến trình chết.
- Bên trong khe dùng core.gpu.task → xếp hàng chung với Whisper/VoxCPM/Real-ESRGAN/Ollama và giải phóng VRAM của họ khác.
- Khởi động lại: job "running" cũ → diệt tiến trình con còn sót (theo PID + dòng lệnh chứa mã job), chạy lại nếu chưa quá
  max_attempts, ngược lại báo lỗi "bị gián đoạn". Không chạy trùng, không thử lại vô hạn.
- Dọn dẹp mỗi giờ: video/kết quả hết hạn, phiên tải lên dở, thư mục làm việc mồ côi.
"""

import os
import shutil
import socket
import threading
import time
import traceback

import psutil

from core import gpu

from . import db, models, pipeline, settings

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
_wake = threading.Event()
_started = False
_cancel_events = {}


def wake():
    _wake.set()


# ── Khe GPU liên tiến trình ──────────────────────────────────────
class Slot:
    def __init__(self, idx):
        cfg = settings.get()
        d = settings.data_dir("locks") if not cfg.get("slot_dir") else cfg["slot_dir"]
        # Khoá đặt cạnh thư mục model (dùng chung giữa các bản Hub) nếu ghi được, ngược lại trong data
        shared = cfg["models_dir"]
        if os.path.isdir(shared) and os.access(shared, os.W_OK):
            d = shared
        self.path = os.path.join(d, f"gpu{cfg['gpu_id']}.slot{idx}.lock")
        self.f = None

    def acquire(self):
        self.f = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.f.close()
            self.f = None
            return False

    def release(self):
        if not self.f:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.f.close()
        self.f = None


def _free_slot():
    for i in range(max(1, int(settings.get()["gpu_concurrency"]))):
        s = Slot(i)
        if s.acquire():
            return s
    return None


# ── Hàng đợi ─────────────────────────────────────────────────────
def claim():
    cfg = settings.get()
    with db.tx() as c:
        running = c.execute("SELECT count(*) FROM jobs WHERE status='running' AND worker=?", (WORKER_ID,)).fetchone()[0]
        if running >= int(cfg["gpu_concurrency"]):
            return None
        # Chia lượt công bằng: bản thử trước; rồi người đang có ít job chạy nhất; rồi người được chạy lâu nhất trước đây;
        # cuối cùng theo thời điểm tạo. Một người xếp nhiều job dài không chiếm GPU của người khác nhiều giờ liền.
        j = c.execute("""SELECT j.* FROM jobs j WHERE j.status='queued' AND j.cancel_requested=0
                         ORDER BY j.preview DESC,
                                  (SELECT count(*) FROM jobs r WHERE r.owner=j.owner AND r.status='running') ASC,
                                  coalesce((SELECT max(r.started_at) FROM jobs r WHERE r.owner=j.owner AND r.started_at IS NOT NULL), 0) ASC,
                                  j.created_at ASC LIMIT 1""").fetchone()
        if not j:
            return None
        n = c.execute("""UPDATE jobs SET status='running', stage='queued', worker=?, attempts=attempts+1, started_at=?,
                         lease_until=?, message='Đang chờ GPU' WHERE id=? AND status='queued'""",
                      (WORKER_ID, db.now(), db.now() + 120, j["id"])).rowcount
        return dict(j) | {"attempts": j["attempts"] + 1} if n == 1 else None


def _update(job_id, **f):
    if not f:
        return
    f["lease_until"] = db.now() + 120
    sets = ", ".join(f"{k}=?" for k in f)
    db.run(f"UPDATE jobs SET {sets} WHERE id=?", (*f.values(), job_id))


def _cancelled(job_id):
    r = db.one("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,))
    return not r or bool(r["cancel_requested"])


def _finish(job_id, status, **f):
    cfg = settings.get()
    f.update(status=status, finished_at=db.now(), lease_until=None, pid=None)
    if status == "completed":
        f["expires_at"] = db.now() + cfg["retention_hours"] * 3600
    sets = ", ".join(f"{k}=?" for k in f)
    db.run(f"UPDATE jobs SET {sets} WHERE id=?", (*f.values(), job_id))


def run_job(job):
    jid = job["id"]
    log_path = os.path.join(settings.data_dir("logs"), f"{jid}.log")
    db.run("UPDATE jobs SET log_path=? WHERE id=?", (log_path, jid))
    logf = open(log_path, "a", encoding="utf-8")

    def log(msg):
        logf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{jid}] {msg}\n")
        logf.flush()

    log(f"Bắt đầu (lần thử {job['attempts']}, worker {WORKER_ID})")
    video = db.one("SELECT * FROM videos WHERE id=?", (job["video_id"],))
    runner = None
    try:
        if not video or video["deleted_at"] or not os.path.isfile(video["path"]):
            raise pipeline.JobError("no_input", "Video gốc đã bị xoá hoặc hết hạn")
        runner = pipeline.Runner(job, video, lambda **f: _update(jid, **f), lambda: _cancelled(jid), log)
        caps = models.capabilities(wait=True)  # job tạo ngay sau khi Hub khởi động: chờ kiểm tra GPU xong ở đây
        if not caps or not caps.get("ok"):
            raise pipeline.JobError("not_ready", "Máy xử lý video chưa sẵn sàng: " + ((caps or {}).get("error") or "không nhận diện được GPU"))
        with gpu.task(f"video:{jid[:8]}", "video", should_abort=lambda: _cancelled(jid),
                      on_wait=lambda n: _update(jid, stage="queued", message=f"Đang chờ GPU ({n} tác vụ khác phía trước)")):
            if _cancelled(jid):
                raise pipeline.Cancelled()
            final, out = runner.run()
        _finish(jid, "completed", stage="done", message="Hoàn tất", progress=100.0, eta_s=0, output_path=final,
                output_size=os.path.getsize(final), output_json=db.dumps(out))
        log(f"Hoàn tất: {final} ({out['video']['width']}x{out['video']['height']} @ {out['video']['fps']} fps, {out['duration']}s)")
    except (pipeline.Cancelled, gpu.Aborted):
        _finish(jid, "cancelled", stage="cancelled", message="Đã huỷ theo yêu cầu")
        log("Đã huỷ")
    except pipeline.JobError as e:
        _finish(jid, "failed", stage="failed", error_code=e.code, error_message=str(e), message=str(e))
        log(f"LỖI {e.code}: {e}")
    except Exception as e:  # lỗi không lường trước: không để worker chết
        log("LỖI nội bộ:\n" + traceback.format_exc())
        _finish(jid, "failed", stage="failed", error_code="internal", error_message=f"Lỗi nội bộ ({type(e).__name__})",
                message="Lỗi nội bộ")
    finally:
        logf.close()
        work = os.path.join(settings.get()["data_dir"], "work", jid)
        shutil.rmtree(work, ignore_errors=True)  # file trung gian/tạm luôn được dọn


def recover():
    """Job đang chạy khi tiến trình trước dừng đột ngột: diệt tiến trình con sót lại, chạy lại có giới hạn."""
    cfg = settings.get()
    for j in db.all_("SELECT * FROM jobs WHERE status='running'"):
        if j["worker"] and j["worker"] != WORKER_ID and j["lease_until"] and j["lease_until"] > db.now() and _alive_worker(j["worker"]):
            continue  # tiến trình Hub khác (cùng DB) vẫn đang chạy job này
        if j["pid"]:
            try:
                p = psutil.Process(j["pid"])
                if j["id"] in " ".join(p.cmdline()) or "rve-backend.py" in " ".join(p.cmdline()):
                    pipeline.kill_tree(j["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        shutil.rmtree(os.path.join(cfg["data_dir"], "work", j["id"]), ignore_errors=True)
        if j["cancel_requested"]:
            _finish(j["id"], "cancelled", stage="cancelled", message="Đã huỷ")
        elif j["attempts"] < cfg["max_attempts"]:
            db.run("""UPDATE jobs SET status='queued', stage='queued', worker=NULL, pid=NULL, lease_until=NULL, progress=NULL,
                      frames_done=NULL, eta_s=NULL, message=? WHERE id=?""",
                   (f"Máy chủ khởi động lại khi đang xử lý — chạy lại (lần {j['attempts'] + 1}/{cfg['max_attempts']})", j["id"]))
        else:
            _finish(j["id"], "failed", stage="failed", error_code="interrupted",
                    error_message=f"Bị gián đoạn {j['attempts']} lần (máy chủ khởi động lại) — không chạy lại nữa",
                    message="Bị gián đoạn")


def _alive_worker(worker):
    host, _, pid = worker.rpartition(":")
    if host != socket.gethostname():
        return True
    try:
        return psutil.pid_exists(int(pid)) and int(pid) != os.getpid()
    except ValueError:
        return False


def cleanup():
    cfg = settings.get()
    now = db.now()
    for v in db.all_("SELECT id, path, info_json FROM videos WHERE deleted_at IS NULL AND expires_at < ?", (now,)):
        if db.one("SELECT 1 FROM jobs WHERE video_id=? AND status IN ('queued','running')", (v["id"],)):
            continue
        _rm(v["path"])
        _rm((db.loads(v["info_json"], {}) or {}).get("proxy_path"))  # bản xem trước H.264 (nếu có)
        db.run("UPDATE videos SET deleted_at=? WHERE id=?", (now, v["id"]))
    # Kết quả hết hạn: xoá file, giữ dòng job để người dùng vẫn thấy lịch sử ("đã hết hạn")
    for j in db.all_("SELECT id, output_path FROM jobs WHERE output_path IS NOT NULL AND expires_at IS NOT NULL AND expires_at < ?", (now,)):
        _rm(j["output_path"])
        db.run("UPDATE jobs SET output_path=NULL, message='Kết quả đã hết hạn lưu trữ và được xoá' WHERE id=?", (j["id"],))
    for u in db.all_("SELECT id, path FROM uploads WHERE updated_at < ?", (now - 24 * 3600,)):
        _rm(u["path"])
        db.run("DELETE FROM uploads WHERE id=?", (u["id"],))
    work = os.path.join(cfg["data_dir"], "work")
    if os.path.isdir(work):
        active = {r["id"] for r in db.all_("SELECT id FROM jobs WHERE status='running'")}
        for d in os.listdir(work):
            if d not in active:
                shutil.rmtree(os.path.join(work, d), ignore_errors=True)
    for f in os.listdir(settings.data_dir("logs")):  # log giữ lâu hơn kết quả 7 ngày để tra lỗi
        p = os.path.join(settings.data_dir("logs"), f)
        if os.path.getmtime(p) < now - (cfg["retention_hours"] * 3600 + 7 * 86400):
            _rm(p)


def _rm(p):
    if p:
        try:
            os.remove(p)
        except OSError:
            pass


def _loop(ready):
    ready.wait()
    last_clean = 0
    while True:
        try:
            if time.time() - last_clean > 3600:
                last_clean = time.time()
                cleanup()
            slot = _free_slot()
            job = claim() if slot else None
            if job:
                try:
                    run_job(job)
                finally:
                    slot.release()
                continue
            if slot:
                slot.release()
        except Exception:
            traceback.print_exc()
        _wake.wait(5)
        _wake.clear()


def start():
    """Phục hồi job gián đoạn một lần, rồi chạy gpu_concurrency luồng worker."""
    global _started
    if _started:
        return
    _started = True
    ready = threading.Event()

    def boot():
        try:
            recover()
        except Exception:
            traceback.print_exc()
        ready.set()

    threading.Thread(target=boot, daemon=True, name="video-recover").start()
    for i in range(max(1, int(settings.get()["gpu_concurrency"]))):
        threading.Thread(target=_loop, args=(ready,), daemon=True, name=f"video-worker-{i}").start()
