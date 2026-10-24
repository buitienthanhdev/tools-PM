"""
API Video Workspace (/api/video/*). core.auth._guard đã yêu cầu đăng nhập + quyền công cụ "video"; mọi thao tác với file
và job còn kiểm tra chủ sở hữu (người khác nhận 404). Không nhận đường dẫn, lệnh hay tham số ffmpeg từ frontend: chỉ id
model trong danh mục đã duyệt và vài tuỳ chọn có giới hạn (pipeline.plan kiểm tra).
"""

import os
import queue
import re
import subprocess
import threading

from flask import Blueprint, jsonify, request, send_file

from core import auth

from . import catalog, db, models, pipeline, probe, settings, worker

bp = Blueprint("video", __name__, url_prefix="/api/video")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SOURCE_URL = "https://github.com/TNTwise/REAL-Video-Enhancer"


def _err(code, msg, status=400):
    return jsonify({"error": msg, "code": code}), status


def _user():
    return auth.current_user()["email"]


def _is_admin():
    return auth.current_user()["role"] == "admin"


@bp.errorhandler(pipeline.JobError)
def _job_error(e):
    return _err(e.code, str(e))


def _usage(owner):
    v = db.one("SELECT coalesce(sum(size),0) n FROM videos WHERE owner=? AND deleted_at IS NULL", (owner,))["n"]
    r = db.one("SELECT coalesce(sum(output_size),0) n FROM jobs WHERE owner=? AND deleted_at IS NULL AND output_path IS NOT NULL",
               (owner,))["n"]
    u = db.one("SELECT coalesce(sum(size),0) n FROM uploads WHERE owner=?", (owner,))["n"]
    return v + r + u


def _video_view(v):
    info = db.loads(v["info_json"], {})
    return {"id": v["id"], "name": v["name"], "size": v["size"], "created_at": v["created_at"], "expires_at": v["expires_at"],
            "info": {k: x for k, x in info.items() if k not in ("proxy_path",)}}


def _job_view(j):
    out = db.loads(j["output_json"])
    return {"id": j["id"], "video_id": j["video_id"], "config": db.loads(j["config_json"], {}), "plan": db.loads(j["plan_json"], {}),
            "models": db.loads(j["models_json"], {}), "preview": bool(j["preview"]), "status": j["status"], "stage": j["stage"],
            "message": j["message"], "progress": j["progress"], "frames_done": j["frames_done"], "frames_total": j["frames_total"],
            "eta_s": j["eta_s"], "fps": j["fps"], "attempts": j["attempts"], "created_at": j["created_at"],
            "started_at": j["started_at"], "finished_at": j["finished_at"], "expires_at": j["expires_at"],
            "error_code": j["error_code"], "error_message": j["error_message"], "cancel_requested": bool(j["cancel_requested"]),
            "output": out, "output_size": j["output_size"], "has_result": bool(j["output_path"] and os.path.isfile(j["output_path"]))}


def _own_video(vid):
    v = db.one("SELECT * FROM videos WHERE id=? AND deleted_at IS NULL", (vid,))
    if not v or v["owner"] != _user():
        return None
    return v


def _own_job(jid):
    j = db.one("SELECT * FROM jobs WHERE id=? AND deleted_at IS NULL", (jid,))
    if not j or (j["owner"] != _user() and not _is_admin()):
        return None
    return j


# ── Trạng thái & danh mục ────────────────────────────────────────
@bp.route("/status")
def status():
    cfg = settings.get()
    caps = models.capabilities()
    allowed = catalog.allowed(cfg)
    problems = models.env_problems()
    usable = not problems and bool(caps and caps.get("ok"))
    return jsonify({
        "ready": usable, "checking": caps is None, "problems": problems + ([caps["error"]] if caps and caps.get("error") else []),
        "hardware": {"backend": cfg["backend"], "gpus": (caps or {}).get("gpus"), "torch": (caps or {}).get("torch"),
                     "half_precision": (caps or {}).get("half")},
        "models": [{"id": k, "kind": m["kind"], "group": m.get("group"), "label": m["label"], "best_for": m["best_for"],
                    "scale": m.get("scale"), "license": m["license"], "noncommercial": m["noncommercial"],
                    "installed": models.is_ready(k), "downloadable": cfg["allow_model_download"]} for k, m in allowed.items()],
        "factors": list(catalog.INTERPOLATE_FACTORS), "scene_detect": catalog.SCENE_DETECT,
        "presets": [p for p in catalog.PRESETS if all(x in allowed for x in [p.get("upscale"), p.get("interpolate"), *(p.get("restore") or [])] if x)]
        + [dict(p, upscale=p["fallback_upscale"]) for p in catalog.PRESETS
           if p.get("fallback_upscale") and p.get("upscale") not in allowed and p["fallback_upscale"] in allowed],
        "limits": {k: cfg[k] for k in ("max_upload_mb", "chunk_mb", "max_duration_s", "max_input_pixels", "max_output_pixels",
                                       "max_output_fps", "max_queued_per_user", "quota_per_user_gb", "retention_hours",
                                       "preview_seconds", "gpu_concurrency")},
        "usage_bytes": _usage(_user()),
        "queue": {"queued": db.one("SELECT count(*) n FROM jobs WHERE status='queued'")["n"],
                  "running": db.one("SELECT count(*) n FROM jobs WHERE status='running'")["n"]},
        "license": {"name": "REAL-Video-Enhancer", "license": "AGPL-3.0", "source": SOURCE_URL,
                    "commit": _vendor_commit()},
    })


def _vendor_commit():
    try:
        with open(os.path.join(settings.MODULE_DIR, "VENDOR.md"), encoding="utf-8") as f:
            m = re.search(r"Commit:\s*`?([0-9a-f]{40})", f.read())
            return m.group(1) if m else None
    except OSError:
        return None


# ── Tải lên theo phần (Cloudflare giới hạn 100 MB/request) ──────
@bp.route("/uploads", methods=["POST"])
def upload_start():
    cfg = settings.get()
    d = request.get_json(silent=True) or {}
    name = re.sub(r"[\x00-\x1f\\/:*?\"<>|]", "_", str(d.get("name") or "video"))[:180]
    try:
        size = int(d.get("size"))
    except (TypeError, ValueError):
        return _err("bad_request", "Thiếu dung lượng file")
    if size <= 0:
        return _err("empty", "File rỗng")
    if size > cfg["max_upload_mb"] * 1024 ** 2:
        return _err("too_big", f"File {size / 1024 ** 2:.0f} MB vượt giới hạn {cfg['max_upload_mb']} MB", 413)
    if _usage(_user()) + size > cfg["quota_per_user_gb"] * 1024 ** 3:
        return _err("quota", f"Vượt dung lượng lưu trữ {cfg['quota_per_user_gb']} GB của bạn — xoá bớt video/kết quả cũ", 413)
    uid = db.new_id()
    path = os.path.join(settings.data_dir("uploads"), f"{uid}.part")
    open(path, "wb").close()
    db.run("INSERT INTO uploads (id, owner, name, size, received, path, created_at, updated_at) VALUES (?,?,?,?,0,?,?,?)",
           (uid, _user(), name, size, path, db.now(), db.now()))
    return jsonify({"upload_id": uid, "chunk_size": cfg["chunk_mb"] * 1024 ** 2})


@bp.route("/uploads/<uid>", methods=["PUT"])
def upload_chunk(uid):
    cfg = settings.get()
    u = db.one("SELECT * FROM uploads WHERE id=?", (uid,))
    if not u or u["owner"] != _user():
        return _err("not_found", "Không có phiên tải lên", 404)
    try:
        offset = int(request.args.get("offset", "-1"))
    except ValueError:
        offset = -1
    if offset != u["received"]:
        return jsonify({"error": "Sai vị trí phần", "code": "bad_offset", "received": u["received"]}), 409
    limit = cfg["chunk_mb"] * 1024 ** 2
    if (request.content_length or 0) > limit:
        return _err("chunk_too_big", "Phần tải lên quá lớn", 413)
    data = request.get_data(cache=False)
    if len(data) > limit or u["received"] + len(data) > u["size"]:
        return _err("chunk_too_big", "Phần tải lên vượt dung lượng đã khai báo", 413)
    with open(u["path"], "ab") as f:
        f.write(data)
    received = u["received"] + len(data)
    db.run("UPDATE uploads SET received=?, updated_at=? WHERE id=?", (received, db.now(), uid))
    return jsonify({"received": received})


@bp.route("/uploads/<uid>/complete", methods=["POST"])
def upload_complete(uid):
    cfg = settings.get()
    u = db.one("SELECT * FROM uploads WHERE id=?", (uid,))
    if not u or u["owner"] != _user():
        return _err("not_found", "Không có phiên tải lên", 404)
    if u["received"] != u["size"] or os.path.getsize(u["path"]) != u["size"]:
        return _err("incomplete", "Chưa tải đủ file", 409)
    vid = db.new_id()
    final = os.path.join(settings.data_dir("videos"), vid)  # tên nội bộ, không dùng tên người dùng
    os.replace(u["path"], final)
    db.run("DELETE FROM uploads WHERE id=?", (uid,))
    try:
        info = probe.probe(final)
    except probe.ProbeError as e:
        os.remove(final)
        return _err(e.code, str(e), 422)
    except subprocess.TimeoutExpired:
        os.remove(final)
        return _err("probe_timeout", "Phân tích file quá lâu — file có thể hỏng", 422)
    except Exception as e:  # lỗi ngoài dự kiến: không để lại file mồ côi (không bản ghi nào trỏ tới)
        try:
            os.remove(final)
        except OSError:
            pass
        return _err("probe_failed", f"Không phân tích được file ({type(e).__name__})", 500)
    if info["duration"] > cfg["max_duration_s"]:
        os.remove(final)
        return _err("too_long", f"Video dài {info['duration']:.0f} giây, vượt giới hạn {cfg['max_duration_s']} giây", 422)
    if info["video"]["width"] * info["video"]["height"] > cfg["max_input_pixels"]:
        os.remove(final)
        return _err("too_large", "Độ phân giải đầu vào vượt giới hạn", 422)
    v = info["video"]
    fmt = (info["container"] or "").split(",")[0]  # "mov,mp4,…" / "matroska,webm" (MKV và WebM chung tên)
    acodec = (info["audio"] or {}).get("codec")
    info["playable"] = v["pix_fmt"] in ("yuv420p", "yuvj420p") and v["bit_depth"] == 8 and (
        (fmt == "mov" and v["codec"] in ("h264", "av1") and acodec in (None, "aac", "mp3"))
        or (fmt == "matroska" and v["codec"] in ("vp8", "vp9", "av1") and acodec in (None, "opus", "vorbis")))
    info["proxy"] = None if info["playable"] else "pending"
    db.run("INSERT INTO videos (id, owner, name, size, path, info_json, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
           (vid, _user(), u["name"], u["size"], final, db.dumps(info), db.now(), db.now() + cfg["retention_hours"] * 3600))
    if not info["playable"]:
        _proxy_q.put(vid)
    return jsonify({"video": _video_view(db.one("SELECT * FROM videos WHERE id=?", (vid,)))})


# Bản xem trước: một hàng đợi, một luồng (giới hạn số ffmpeg chạy cùng lúc); khởi động lại → đưa lại các bản "pending"
_proxy_q = queue.Queue()
_proxy_started = False


def _proxy_loop():
    while True:
        vid = _proxy_q.get()
        try:
            _make_proxy(vid)
        except Exception as e:  # không để luồng chết; đánh dấu thất bại để giao diện thôi chờ
            print(f"[video] proxy {vid[:8]} lỗi: {type(e).__name__}: {e}")
            v = db.one("SELECT info_json FROM videos WHERE id=?", (vid,))
            if v:
                info = db.loads(v["info_json"], {})
                info["proxy"] = "failed"
                db.run("UPDATE videos SET info_json=? WHERE id=?", (db.dumps(info), vid))


def start_proxies():
    global _proxy_started
    if _proxy_started:
        return
    _proxy_started = True
    for v in db.all_("SELECT id, info_json FROM videos WHERE deleted_at IS NULL"):
        if (db.loads(v["info_json"], {}) or {}).get("proxy") == "pending":
            _proxy_q.put(v["id"])
    threading.Thread(target=_proxy_loop, daemon=True, name="video-proxy").start()


def _make_proxy(vid):
    """Bản xem trước H.264 cho file gốc trình duyệt không phát được (dùng NVENC, không chiếm nhân CUDA)."""
    v = db.one("SELECT * FROM videos WHERE id=?", (vid,))
    if not v or v["deleted_at"] or not os.path.isfile(v["path"]):
        return
    info = db.loads(v["info_json"], {})
    out = os.path.join(settings.data_dir("videos"), f"{vid}.proxy.mp4")
    base = [settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", v["path"], "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1,format=yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart"]
    ok = False
    for enc in (["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"], ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]):
        r = subprocess.run(base + enc + [out], capture_output=True, timeout=7200, creationflags=NO_WINDOW)
        if r.returncode == 0 and os.path.isfile(out):
            ok = True
            break
    info["proxy"] = "ready" if ok else "failed"
    info["proxy_path"] = out if ok else None
    db.run("UPDATE videos SET info_json=? WHERE id=?", (db.dumps(info), vid))


@bp.route("/uploads/<uid>", methods=["DELETE"])
def upload_abort(uid):
    u = db.one("SELECT * FROM uploads WHERE id=?", (uid,))
    if not u or u["owner"] != _user():
        return _err("not_found", "Không có phiên tải lên", 404)
    try:
        os.remove(u["path"])
    except OSError:
        pass
    db.run("DELETE FROM uploads WHERE id=?", (uid,))
    return jsonify({"ok": True})


# ── Video ────────────────────────────────────────────────────────
@bp.route("/videos")
def videos():
    rows = db.all_("SELECT * FROM videos WHERE owner=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 100", (_user(),))
    return jsonify({"videos": [_video_view(v) for v in rows]})


@bp.route("/videos/<vid>")
def video(vid):
    v = _own_video(vid)
    return jsonify({"video": _video_view(v)}) if v else _err("not_found", "Không có video", 404)


@bp.route("/videos/<vid>/file")
def video_file(vid):
    v = _own_video(vid)
    if not v:
        return _err("not_found", "Không có video", 404)
    info = db.loads(v["info_json"], {})
    if not info.get("playable"):
        if info.get("proxy_path") and os.path.isfile(info["proxy_path"]):
            return send_file(info["proxy_path"], mimetype="video/mp4", conditional=True)
        return _err("not_playable", "Trình duyệt không phát được định dạng gốc; bản xem trước đang được tạo" if info.get("proxy") == "pending"
                    else "Không tạo được bản xem trước cho định dạng này", 409)
    mime = "video/webm" if (info.get("container") or "").startswith("matroska") else "video/mp4"
    return send_file(v["path"], mimetype=mime, conditional=True)


@bp.route("/videos/<vid>", methods=["DELETE"])
def video_delete(vid):
    v = _own_video(vid)
    if not v:
        return _err("not_found", "Không có video", 404)
    db.run("UPDATE jobs SET cancel_requested=1 WHERE video_id=? AND status IN ('queued','running')", (vid,))
    db.run("UPDATE jobs SET status='cancelled', stage='cancelled', message='Video gốc đã bị xoá', finished_at=? "
           "WHERE video_id=? AND status='queued'", (db.now(), vid))
    info = db.loads(v["info_json"], {})
    for p in (v["path"], info.get("proxy_path")):
        if p:
            try:
                os.remove(p)
            except OSError:
                pass
    db.run("UPDATE videos SET deleted_at=? WHERE id=?", (db.now(), vid))
    return jsonify({"ok": True})


# ── Kế hoạch & job ───────────────────────────────────────────────
def _conf():
    d = request.get_json(silent=True) or {}
    c = d.get("config") or {}
    if not isinstance(c, dict):
        raise pipeline.JobError("bad_request", "Cấu hình không hợp lệ")
    allowed_keys = {"upscale", "interpolate", "factor", "restore", "scene_detect", "preview"}
    if set(c) - allowed_keys:
        raise pipeline.JobError("bad_request", "Cấu hình có tham số không được hỗ trợ: " + ", ".join(sorted(set(c) - allowed_keys)))
    return str(d.get("video_id") or ""), c


@bp.route("/plan", methods=["POST"])
def plan():
    vid, conf = _conf()
    v = _own_video(vid)
    if not v:
        return _err("not_found", "Không có video", 404)
    p = pipeline.plan(db.loads(v["info_json"]), conf)
    return jsonify({"plan": p})


@bp.route("/jobs", methods=["POST"])
def job_create():
    cfg = settings.get()
    vid, conf = _conf()
    v = _own_video(vid)
    if not v:
        return _err("not_found", "Không có video", 404)
    caps = models.capabilities()  # None = đang kiểm tra GPU (vừa khởi động): vẫn nhận job, worker chờ kết quả kiểm tra
    if models.env_problems() or (caps is not None and not caps.get("ok")):
        return _err("not_ready", "Máy xử lý video chưa sẵn sàng: " + "; ".join(models.env_problems() or [caps.get("error") or "không nhận diện được GPU"]), 503)
    p = pipeline.plan(db.loads(v["info_json"]), conf)
    mine = db.one("SELECT count(*) n FROM jobs WHERE owner=? AND status IN ('queued','running')", (_user(),))["n"]
    if mine >= cfg["max_queued_per_user"]:
        return _err("queue_full", f"Bạn đã có {mine} job đang chờ/chạy (tối đa {cfg['max_queued_per_user']})", 429)
    total = db.one("SELECT count(*) n FROM jobs WHERE status IN ('queued','running')")["n"]
    if total >= cfg["max_queued_total"]:
        return _err("queue_full", "Hàng đợi máy chủ đang đầy, vui lòng thử lại sau", 429)
    est = p["output"]["width"] * p["output"]["height"] * p["output"]["frames"] * 0.1
    if _usage(_user()) + est > cfg["quota_per_user_gb"] * 1024 ** 3:
        return _err("quota", "Kết quả dự kiến vượt dung lượng lưu trữ còn lại của bạn — xoá bớt kết quả cũ", 413)
    jid = db.new_id()
    db.run("""INSERT INTO jobs (id, owner, video_id, config_json, models_json, preview, status, stage, message, created_at, plan_json)
              VALUES (?,?,?,?,?,?, 'queued', 'queued', 'Đang chờ xử lý', ?, ?)""",
           (jid, _user(), vid, db.dumps(conf), db.dumps(p["models"]), 1 if conf.get("preview") else 0, db.now(), db.dumps(p)))
    worker.wake()
    return jsonify({"job": _job_view(db.one("SELECT * FROM jobs WHERE id=?", (jid,)))})


@bp.route("/jobs")
def jobs():
    rows = db.all_("SELECT * FROM jobs WHERE owner=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 100", (_user(),))
    return jsonify({"jobs": [_job_view(j) for j in rows]})


@bp.route("/jobs/<jid>")
def job(jid):
    j = _own_job(jid)
    return jsonify({"job": _job_view(j)}) if j else _err("not_found", "Không có job", 404)


@bp.route("/jobs/<jid>/cancel", methods=["POST"])
def job_cancel(jid):
    j = _own_job(jid)
    if not j:
        return _err("not_found", "Không có job", 404)
    if j["status"] not in db.ACTIVE:
        return _err("bad_state", "Job đã kết thúc")
    db.run("UPDATE jobs SET cancel_requested=1 WHERE id=?", (jid,))
    db.run("UPDATE jobs SET status='cancelled', stage='cancelled', message='Đã huỷ', finished_at=? WHERE id=? AND status='queued'",
           (db.now(), jid))
    return jsonify({"job": _job_view(db.one("SELECT * FROM jobs WHERE id=?", (jid,)))})


@bp.route("/jobs/<jid>", methods=["DELETE"])
def job_delete(jid):
    j = _own_job(jid)
    if not j:
        return _err("not_found", "Không có job", 404)
    if j["status"] in db.ACTIVE:
        db.run("UPDATE jobs SET cancel_requested=1 WHERE id=?", (jid,))
        db.run("UPDATE jobs SET status='cancelled', stage='cancelled', finished_at=? WHERE id=? AND status='queued'", (db.now(), jid))
    if j["output_path"]:
        try:
            os.remove(j["output_path"])
        except OSError:
            pass
    db.run("UPDATE jobs SET deleted_at=?, output_path=NULL WHERE id=?", (db.now(), jid))
    return jsonify({"ok": True})


@bp.route("/jobs/<jid>/result")
def job_result(jid):
    j = _own_job(jid)
    if not j or not j["output_path"] or not os.path.isfile(j["output_path"]):
        return _err("not_found", "Không có kết quả", 404)
    v = db.one("SELECT name FROM videos WHERE id=?", (j["video_id"],))
    stem = os.path.splitext((v or {}).get("name") or "video")[0][:120]
    p = db.loads(j["plan_json"], {})
    tag = "_".join(x for x in [f"{p.get('output', {}).get('width')}x{p.get('output', {}).get('height')}",
                               f"{p.get('output', {}).get('fps')}fps", "thu" if j["preview"] else ""] if x)
    return send_file(j["output_path"], mimetype="video/mp4", conditional=True,
                     as_attachment=request.args.get("download") == "1", download_name=f"{stem}_{tag}.mp4")


@bp.route("/jobs/<jid>/log")
def job_log(jid):
    """Chỉ admin: log chi tiết theo job (có đường dẫn máy chủ)."""
    if not _is_admin():
        return _err("forbidden", "Chỉ admin", 403)
    j = db.one("SELECT log_path FROM jobs WHERE id=?", (jid,))
    if not j or not j["log_path"] or not os.path.isfile(j["log_path"]):
        return _err("not_found", "Không có log", 404)
    with open(j["log_path"], encoding="utf-8", errors="replace") as f:
        return jsonify({"log": f.read()[-60000:]})


def init_app(app):
    app.register_blueprint(bp)
    models.capabilities()  # nhận diện backend chạy nền
    worker.start()
    start_proxies()
