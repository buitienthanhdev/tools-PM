"""
Video Workspace: tải lên theo phần, phân tích, phân quyền, giới hạn, hàng đợi, huỷ, treo, crash, phục hồi sau khởi động lại,
dọn file hết hạn — chạy với RVE giả (tests_hub/video_stub, không cần GPU). Cần ffmpeg/ffprobe của Video Workspace.
Kiểm thử GPU thật (RVE thật trên video): đặt VIDEO_GPU_TEST=1.
pytest tests_hub/test_video_workspace.py -q
"""

import os
import subprocess
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STUB = os.path.join(ROOT, "tests_hub", "video_stub")


def _ffdir():
    from modules.video_workspace import settings

    return settings.DEFAULTS["ffmpeg_dir"]


pytestmark = pytest.mark.skipif(not os.path.isfile(os.path.join(_ffdir(), "ffprobe.exe" if os.name == "nt" else "ffprobe")),
                                reason="Chưa cài ffmpeg/ffprobe của Video Workspace (scripts/setup_video_workspace.py)")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    from flask import Flask

    from core import auth
    from core import config as hubcfg
    from modules.video_workspace import api, db, models

    cfg = hubcfg.get()
    cfg["auto_approve"] = True
    cfg.pop("admin_password", None)
    cfg["video"] = {"enabled": True, "data_dir": str(tmp_path / "video"), "python": sys.executable, "rve_dir": STUB,
                    "models_dir": str(tmp_path / "models"), "stall_timeout_s": 4, "min_free_disk_gb": 0, "chunk_mb": 1,
                    "max_upload_mb": 50, "quota_per_user_gb": 1, "max_queued_per_user": 2}
    os.makedirs(tmp_path / "models", exist_ok=True)
    auth.USERS_PATH = str(tmp_path / "users.json")
    auth.SECRET_PATH = str(tmp_path / "secret.key")
    auth.SETUP_CODE_PATH = str(tmp_path / "code.txt")
    db.reset_for_tests()
    monkeypatch.setattr(models, "capabilities", lambda refresh=False, wait=False: {"ok": True, "backends": ["pytorch (cuda)"], "gpus": ["Stub"], "torch": "0", "half": True})
    monkeypatch.setattr(models, "is_ready", lambda mid: True)

    def fake_ensure(mid, log=print):
        p = str(tmp_path / "models" / mid)
        open(p, "wb").close()
        return p

    monkeypatch.setattr(models, "ensure", fake_ensure)
    app = Flask("video_test")
    app.config["TESTING"] = True
    auth.init_app(app)
    app.register_blueprint(api.bp)
    ff = os.path.join(_ffdir(), "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    clip = tmp_path / "clip.mp4"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=2",
                    "-f", "lavfi", "-i", "sine=f=440:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)],
                   check=True)
    return {"app": app, "clip": clip, "tmp": tmp_path}


def _user(app, email):
    from core import auth

    c = app.test_client()
    assert c.post("/api/auth/register", json={"email": email, "password": "matkhau123", "name": email}).status_code == 200
    db = auth._read()
    db["users"][email]["modules"] = ["video"]
    auth._write(db)
    return c


def _upload(c, path, name=None, chunk=1024 * 1024):
    data = open(path, "rb").read()
    r = c.post("/api/video/uploads", json={"name": name or os.path.basename(path), "size": len(data)})
    assert r.status_code == 200, r.json
    uid, size = r.json["upload_id"], r.json["chunk_size"]
    off = 0
    while off < len(data):
        part = data[off:off + min(chunk, size)]
        r = c.put(f"/api/video/uploads/{uid}?offset={off}", data=part)
        assert r.status_code == 200, r.json
        off = r.json["received"]
    return c.post(f"/api/video/uploads/{uid}/complete")


def _run_next():
    from modules.video_workspace import worker

    job = worker.claim()
    assert job
    worker.run_job(job)
    return job["id"]


def test_upload_probe_permissions_and_limits(env):
    app = env["app"]
    a = _user(app, "a@x.com")
    b = _user(app, "b@x.com")
    r = _upload(a, env["clip"], chunk=300 * 1024)  # nhiều phần
    assert r.status_code == 200, r.json
    v = r.json["video"]
    i = v["info"]
    assert i["video"]["width"] == 320 and i["video"]["fps"] == 24 and abs(i["duration"] - 2) < 0.1 and i["audio"]["codec"] == "aac"
    assert i["playable"] is True
    # Sai vị trí phần → 409 kèm số byte máy chủ đã nhận (để trình duyệt tiếp tục đúng chỗ)
    up = a.post("/api/video/uploads", json={"name": "x.mp4", "size": 10}).json["upload_id"]
    r = a.put(f"/api/video/uploads/{up}?offset=5", data=b"12345")
    assert r.status_code == 409 and r.json["received"] == 0
    # File giả đuôi .mp4 bị từ chối theo nội dung thật, không lộ đường dẫn máy chủ
    fake = env["tmp"] / "fake.mp4"
    fake.write_bytes(b"day khong phai video" * 100)
    r = _upload(a, fake)
    assert r.status_code == 422 and r.json["code"] == "not_media" and str(env["tmp"]) not in r.json["error"]
    # Vượt dung lượng cho phép
    assert a.post("/api/video/uploads", json={"name": "big.mp4", "size": 60 * 1024 ** 2}).status_code == 413
    # Người khác không thấy video, không phát được, không tạo job trên video của người khác
    assert b.get(f"/api/video/videos/{v['id']}").status_code == 404
    assert b.get(f"/api/video/videos/{v['id']}/file").status_code == 404
    assert b.post("/api/video/jobs", json={"video_id": v["id"], "config": {"upscale": "realesr-general-4x"}}).status_code == 404
    assert b.get("/api/video/videos").json["videos"] == []
    # Phát video gốc hỗ trợ Range (tua được)
    r = a.get(f"/api/video/videos/{v['id']}/file", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.data) == 100


def test_plan_validation_rejects_unsafe_or_unsupported(env):
    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]

    def plan(conf):
        return a.post("/api/video/plan", json={"video_id": vid, "config": conf})

    ok = plan({"upscale": "realesr-general-4x", "interpolate": "rife-4.26", "factor": 2})
    assert ok.status_code == 200
    p = ok.json["plan"]
    assert (p["output"]["width"], p["output"]["height"], p["output"]["fps"]) == (1280, 720, 48.0)
    assert p["duration"] == 2.0 and p["output"]["audio"] == "copy" and p["models"]["rife-4.26"]["sha256"]
    assert plan({"upscale": "../../evil.pth"}).json["code"] == "bad_model"
    assert plan({"upscale": "rife-4.26"}).json["code"] == "bad_model"  # sai loại model
    assert plan({"interpolate": "rife-4.26", "factor": 2.5}).json["code"] == "bad_factor"  # hệ số lẻ = slow-motion
    assert plan({"upscale": "realesr-general-4x", "ffmpeg_args": "-vf crop"}).json["code"] == "bad_request"
    assert plan({"restore": ["scunet-denoise", "drunet-denoise"]}).json["code"] == "bad_model"  # hai model cùng loại
    assert plan({}).json["code"] == "nothing"
    combo = plan({"restore": ["deh264-span"], "interpolate": "rife-4.26", "factor": 2}).json["plan"]
    assert combo["scene_detect"] == "mean" and any("chuyển cảnh" in w for w in combo["warnings"])
    prev = plan({"upscale": "openproteus-2x", "preview": {"start": 1.5}}).json["plan"]
    assert prev["start"] == 1.0 and prev["duration"] == 1.0 and "cắt đoạn xử lý thử" in prev["normalize"]  # kẹp trong video


def test_job_runs_with_stages_and_verified_output(env):
    from modules.video_workspace import db

    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]
    j = a.post("/api/video/jobs", json={"video_id": vid, "config": {"upscale": "realesr-general-4x", "interpolate": "rife-4.26", "factor": 2}}).json["job"]
    assert j["status"] == "queued"
    seen = set()
    t = threading.Thread(target=_run_next)
    t.start()
    while t.is_alive():
        r = db.one("SELECT stage FROM jobs WHERE id=?", (j["id"],))
        seen.add(r["stage"])
        time.sleep(0.05)
    t.join()
    j = a.get(f"/api/video/jobs/{j['id']}").json["job"]
    assert j["status"] == "completed", j
    assert {"processing", "encoding"} <= seen
    o = j["output"]
    assert (o["video"]["width"], o["video"]["height"], o["video"]["fps"]) == (1280, 720, 48.0) and abs(o["duration"] - 2) < 0.2
    assert o["audio"]["codec"] == "aac" and abs(o["av_offset_ms"]) < 50 and j["expires_at"]
    r = a.get(f"/api/video/jobs/{j['id']}/result?download=1")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"] and r.data[4:8] == b"ftyp"
    b = _user(env["app"], "b@x.com")
    assert b.get(f"/api/video/jobs/{j['id']}/result").status_code == 404
    assert b.delete(f"/api/video/jobs/{j['id']}").status_code == 404
    assert a.delete(f"/api/video/jobs/{j['id']}").status_code == 200
    assert a.get(f"/api/video/jobs/{j['id']}/result").status_code == 404


def test_cancel_kills_process_tree(env, monkeypatch):
    import psutil

    from modules.video_workspace import db

    monkeypatch.setenv("STUB_MODE", "slow")
    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]
    jid = a.post("/api/video/jobs", json={"video_id": vid, "config": {"upscale": "openproteus-2x"}}).json["job"]["id"]
    t = threading.Thread(target=_run_next)
    t.start()
    for _ in range(200):
        r = db.one("SELECT pid, stage FROM jobs WHERE id=?", (jid,))
        if r["pid"] and r["stage"] == "processing":
            break
        time.sleep(0.1)
    pid = r["pid"]
    kids = [p.pid for p in psutil.Process(pid).children(recursive=True)]
    assert a.post(f"/api/video/jobs/{jid}/cancel").status_code == 200
    t.join(30)
    assert not t.is_alive()
    assert a.get(f"/api/video/jobs/{jid}").json["job"]["status"] == "cancelled"
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert not any(psutil.pid_exists(k) for k in kids)
    assert not os.path.isdir(os.path.join(str(env["tmp"]), "video", "work", jid))  # file tạm đã dọn


@pytest.mark.parametrize("mode,code", [("crash", "gpu_oom"), ("stall", "stalled")])
def test_backend_crash_or_stall_is_detected(env, monkeypatch, mode, code):
    monkeypatch.setenv("STUB_MODE", mode)
    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]
    jid = a.post("/api/video/jobs", json={"video_id": vid, "config": {"upscale": "openproteus-2x"}}).json["job"]["id"]
    t0 = time.time()
    _run_next()
    j = a.get(f"/api/video/jobs/{jid}").json["job"]
    assert j["status"] == "failed" and j["error_code"] == code, j
    assert time.time() - t0 < 30  # RVE thật không tự thoát khi luồng render lỗi — worker phải tự dừng


def test_restart_recovery_and_queue_limits(env):
    from modules.video_workspace import db, settings, worker

    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]
    cfg = {"video_id": vid, "config": {"upscale": "openproteus-2x"}}
    j1 = a.post("/api/video/jobs", json=cfg).json["job"]["id"]
    a.post("/api/video/jobs", json=cfg)
    r = a.post("/api/video/jobs", json=cfg)
    assert r.status_code == 429 and r.json["code"] == "queue_full"  # max_queued_per_user = 2
    # Giả lập máy chủ chết khi job đang chạy (tiến trình con không còn)
    db.run("UPDATE jobs SET status='running', worker='otherhost:1', attempts=1, pid=999999, lease_until=? WHERE id=?", (db.now() - 5, j1))
    worker.recover()
    r = db.one("SELECT status, message FROM jobs WHERE id=?", (j1,))
    assert r["status"] == "queued" and "chạy lại" in r["message"]
    db.run("UPDATE jobs SET status='running', worker='otherhost:1', attempts=?, lease_until=? WHERE id=?",
           (settings.get()["max_attempts"], db.now() - 5, j1))
    worker.recover()
    r = db.one("SELECT status, error_code FROM jobs WHERE id=?", (j1,))
    assert (r["status"], r["error_code"]) == ("failed", "interrupted")  # không thử lại vô hạn


def test_cleanup_removes_expired_files(env):
    from modules.video_workspace import db, worker

    a = _user(env["app"], "a@x.com")
    v = _upload(a, env["clip"]).json["video"]
    jid = a.post("/api/video/jobs", json={"video_id": v["id"], "config": {"upscale": "openproteus-2x"}}).json["job"]["id"]
    _run_next()
    out = db.one("SELECT output_path FROM jobs WHERE id=?", (jid,))["output_path"]
    src = db.one("SELECT path FROM videos WHERE id=?", (v["id"],))["path"]
    assert os.path.isfile(out) and os.path.isfile(src)
    db.run("UPDATE jobs SET expires_at=? WHERE id=?", (db.now() - 1, jid))
    db.run("UPDATE videos SET expires_at=? WHERE id=?", (db.now() - 1, v["id"]))
    worker.cleanup()
    assert not os.path.exists(out) and not os.path.exists(src)
    assert a.get(f"/api/video/videos/{v['id']}").status_code == 404
    assert a.get(f"/api/video/jobs/{jid}").json["job"]["has_result"] is False


@pytest.mark.skipif(os.environ.get("VIDEO_GPU_TEST") != "1", reason="Đặt VIDEO_GPU_TEST=1 để chạy RVE thật trên GPU")
def test_real_rve_on_gpu(tmp_path):
    """RVE thật + model thật: upscale 2x + nội suy ×2 đoạn video thật 2 giây, kiểm tra đầu ra."""
    from core import config as hubcfg
    from modules.video_workspace import db, models, pipeline, probe, settings, worker

    hubcfg.get()["video"] = {"enabled": True, "data_dir": str(tmp_path / "video")}
    db.reset_for_tests()
    assert models.capabilities(wait=True)["ok"]
    ff = settings.ffmpeg()
    clip = tmp_path / "real.mp4"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", "240", "-i",
                    "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov", "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(clip)],
                   check=True)
    info = probe.probe(str(clip))
    conf = {"upscale": "openproteus-2x", "interpolate": "rife-4.26", "factor": 2}
    p = pipeline.plan(info, conf)
    db.run("INSERT INTO videos (id, owner, name, size, path, info_json, created_at, expires_at) VALUES ('v1','t','real.mp4',1,?,?,?,?)",
           (str(clip), db.dumps(info), db.now(), db.now() + 3600))
    db.run("""INSERT INTO jobs (id, owner, video_id, config_json, models_json, status, stage, created_at, plan_json, attempts)
              VALUES ('j1','t','v1',?,?,'running','queued',?,?,1)""", (db.dumps(conf), db.dumps(p["models"]), db.now(), db.dumps(p)))
    worker.run_job(db.one("SELECT * FROM jobs WHERE id='j1'"))
    j = db.one("SELECT * FROM jobs WHERE id='j1'")
    assert j["status"] == "completed", j["error_message"]
    o = db.loads(j["output_json"])
    assert (o["video"]["width"], o["video"]["height"]) == (2560, 1068) and o["video"]["fps"] == 48.0 and abs(o["av_offset_ms"]) < 50


def test_cancel_while_waiting_for_gpu(env):
    """Huỷ job đang xếp hàng chờ GPU (công cụ khác đang dùng) phải có hiệu lực ngay, không đợi tới lượt."""
    from core import gpu

    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]
    jid = a.post("/api/video/jobs", json={"video_id": vid, "config": {"upscale": "openproteus-2x"}}).json["job"]["id"]
    hold, release = threading.Event(), threading.Event()

    def other_tool():
        with gpu.task("whisper:test", "whisper"):
            hold.set()
            release.wait(60)

    th = threading.Thread(target=other_tool)
    th.start()
    hold.wait(10)
    t = threading.Thread(target=_run_next)
    t.start()
    for _ in range(50):
        if "chờ GPU" in (a.get(f"/api/video/jobs/{jid}").json["job"]["message"] or ""):
            break
        time.sleep(0.1)
    t0 = time.time()
    assert a.post(f"/api/video/jobs/{jid}/cancel").status_code == 200
    t.join(10)
    release.set()
    th.join(10)
    assert not t.is_alive() and time.time() - t0 < 5
    assert a.get(f"/api/video/jobs/{jid}").json["job"]["status"] == "cancelled"
    assert gpu.status()["waiting"] == 0


def test_fair_queue_interleaves_users(env):
    from modules.video_workspace import db, worker

    a, b = _user(env["app"], "a@x.com"), _user(env["app"], "b@x.com")
    va = _upload(a, env["clip"]).json["video"]["id"]
    vb = _upload(b, env["clip"]).json["video"]["id"]
    cfg = {"upscale": "openproteus-2x"}
    a1 = a.post("/api/video/jobs", json={"video_id": va, "config": cfg}).json["job"]["id"]
    a2 = a.post("/api/video/jobs", json={"video_id": va, "config": cfg}).json["job"]["id"]
    b1 = b.post("/api/video/jobs", json={"video_id": vb, "config": cfg}).json["job"]["id"]
    order = []
    for _ in range(3):
        j = worker.claim()
        order.append(j["id"])
        db.run("UPDATE jobs SET status='completed' WHERE id=?", (j["id"],))
    assert order == [a1, b1, a2]  # B không phải đợi hết các job của A


def test_job_accepted_while_gpu_check_running(env, monkeypatch):
    """Ngay sau khởi động (đang kiểm tra GPU) vẫn nhận job; worker chờ kết quả kiểm tra rồi mới chạy."""
    from modules.video_workspace import models

    state = {"n": 0}

    def caps(refresh=False, wait=False):
        if not wait:
            return None  # đang kiểm tra
        state["n"] += 1
        return {"ok": True, "gpus": ["Stub"]}

    monkeypatch.setattr(models, "capabilities", caps)
    a = _user(env["app"], "a@x.com")
    vid = _upload(a, env["clip"]).json["video"]["id"]
    r = a.post("/api/video/jobs", json={"video_id": vid, "config": {"upscale": "openproteus-2x"}})
    assert r.status_code == 200, r.json
    _run_next()
    assert a.get(f"/api/video/jobs/{r.json['job']['id']}").json["job"]["status"] == "completed" and state["n"] == 1


def test_preview_proxy_recovers_after_restart_and_no_orphans(env, monkeypatch):
    from modules.video_workspace import api, db, probe, worker

    a = _user(env["app"], "a@x.com")
    ff = os.path.join(_ffdir(), "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    mkv = env["tmp"] / "clip.mkv"  # H.264 trong MKV: trình duyệt không phát được → cần bản xem trước
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(env["clip"]), "-c", "copy", str(mkv)], check=True)
    monkeypatch.setattr(api, "_proxy_started", False)
    api.start_proxies()
    v = _upload(a, mkv).json["video"]
    assert v["info"]["playable"] is False

    def proxy_state():
        return db.loads(db.one("SELECT info_json FROM videos WHERE id=?", (v["id"],))["info_json"])

    for _ in range(200):
        if proxy_state().get("proxy") == "ready":
            break
        time.sleep(0.1)
    info = proxy_state()
    assert info["proxy"] == "ready" and a.get(f"/api/video/videos/{v['id']}/file").status_code == 200
    # Giả lập Hub khởi động lại khi bản xem trước đang tạo dở
    os.remove(info["proxy_path"])
    info.update(proxy="pending", proxy_path=None)
    db.run("UPDATE videos SET info_json=? WHERE id=?", (db.dumps(info), v["id"]))
    monkeypatch.setattr(api, "_proxy_started", False)
    api.start_proxies()
    for _ in range(200):
        if proxy_state().get("proxy") == "ready":
            break
        time.sleep(0.1)
    assert proxy_state()["proxy"] == "ready"
    # Hết hạn: xoá cả bản xem trước
    proxy = proxy_state()["proxy_path"]
    db.run("UPDATE videos SET expires_at=? WHERE id=?", (db.now() - 1, v["id"]))
    worker.cleanup()
    assert not os.path.exists(proxy)
    # Lỗi ngoài dự kiến khi phân tích: không để lại file mồ côi
    monkeypatch.setattr(probe, "probe", lambda p: (_ for _ in ()).throw(RuntimeError("bất ngờ")))
    before = set(os.listdir(os.path.join(str(env["tmp"]), "video", "videos")))
    r = _upload(a, env["clip"])
    assert r.status_code == 500 and r.json["code"] == "probe_failed"
    assert set(os.listdir(os.path.join(str(env["tmp"]), "video", "videos"))) == before
