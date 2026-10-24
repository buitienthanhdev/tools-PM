"""
Tài khoản & phân quyền cho Hub.

- Đăng ký → trạng thái "pending" → admin duyệt và cấp quyền từng công cụ.
- Chỉ một admin duy nhất (email trong config.admin_email). Tài khoản admin được tạo bằng mã cài đặt
  (data/admin_setup_code.txt, sinh tự động lần đầu) để không ai chiếm email admin trước.
- Mật khẩu băm scrypt (werkzeug). Phiên đăng nhập là cookie ký (HttpOnly, SameSite=Lax).
"""

import json
import os
import re
import secrets
import threading
import time
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import analytics, config

MODULES = ["whisper", "voxcpm", "image", "genreport", "legal", "spacet", "reviewingcv", "accounting", "video"]
# Công cụ xử lý dữ liệu nhạy cảm: không tự cấp khi auto_approve, admin phải cấp riêng
SENSITIVE_MODULES = {"accounting", "video"}  # không tự cấp khi đăng ký (video chiếm GPU nhiều giờ)
USERS_PATH = os.path.join(config.DATA_DIR, "users.json")
SECRET_PATH = os.path.join(config.DATA_DIR, "secret.key")
SETUP_CODE_PATH = os.path.join(config.DATA_DIR, "admin_setup_code.txt")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

bp = Blueprint("auth", __name__, url_prefix="/api")
_lock = threading.RLock()
_fails = {}  # (ip, email) -> [số lần sai, khoá đến]


# ── Lưu trữ ──────────────────────────────────────────────────
def _read():
    try:
        with open(USERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}}


def _write(db):
    tmp = USERS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, USERS_PATH)


def secret_key():
    try:
        with open(SECRET_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        key = secrets.token_hex(32)
        with open(SECRET_PATH, "w", encoding="utf-8") as f:
            f.write(key)
        return key


def setup_code():
    """Mã cài đặt cho admin; chỉ tồn tại khi admin chưa được tạo."""
    with _lock:
        if config.get()["admin_email"] in _read()["users"]:
            return None
        try:
            with open(SETUP_CODE_PATH, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            code = secrets.token_urlsafe(9)
            with open(SETUP_CODE_PATH, "w", encoding="utf-8") as f:
                f.write(code)
            return code


def init_app(app):
    app.secret_key = secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("PM_INSECURE_COOKIE") != "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    )
    app.register_blueprint(bp)
    app.before_request(_guard)
    _seed_admin()
    if setup_code():
        print(f"[auth] Chưa có admin. Mã cài đặt nằm ở {SETUP_CODE_PATH}")


def _seed_admin():
    """Tạo sẵn admin từ config (admin_email + admin_password), nếu chưa có."""
    cfg = config.get()
    pw = os.environ.get("PM_ADMIN_PASSWORD") or cfg.get("admin_password")
    if not pw:
        return
    ident = cfg["admin_email"]
    with _lock:
        db = _read()
        if ident in db["users"]:
            return
        db["users"][ident] = {
            "name": ident,
            "pw_hash": generate_password_hash(str(pw)),
            "role": "admin",
            "status": "active",
            "modules": MODULES,
            "created": int(time.time()),
        }
        _write(db)


# ── Người dùng hiện tại ──────────────────────────────────────
def _public(email, u):
    return {
        "email": email,
        "name": u.get("name", ""),
        "role": u.get("role", "user"),
        "status": u.get("status", "pending"),
        "modules": MODULES if u.get("role") == "admin" else u.get("modules", []),
        "created": u.get("created"),
        "last_login": u.get("last_login"),
    }


def current_user():
    email = session.get("email")
    if not email:
        return None
    with _lock:
        u = _read()["users"].get(email)
    if not u or u.get("status") == "disabled":
        session.clear()
        return None
    return _public(email, u)


def can(user, module):
    if not user or user["status"] != "active":
        return False
    return user["role"] == "admin" or module in user["modules"]


def is_admin():
    u = current_user()
    return bool(u and u["role"] == "admin" and u["status"] == "active")


# ── Bảo vệ API ───────────────────────────────────────────────
_PREFIX_MODULE = [
    ("/api/transcribe", "whisper"),
    ("/api/voxcpm", "voxcpm"),
    ("/api/image", "image"),
    ("/api/genreport", "genreport"),
    ("/api/legal", "legal"),
    ("/api/cv", "reviewingcv"),
    ("/api/accounting", "accounting"),
    ("/api/video", "video"),
]
_PUBLIC = ("/api/auth/", "/api/health", "/api/track/")  # track: beacon lượt xem/lỗi trình duyệt (giới hạn tốc độ)


def _deny(code, msg, status):
    return jsonify({"error": msg, "code": code}), status


def _guard():
    p = request.path
    if request.method == "OPTIONS":
        return None
    if not (p.startswith("/api/") or p.startswith("/uploads/")):
        return None
    if p.startswith(_PUBLIC):
        return None
    user = current_user()
    if not user:
        return _deny("login_required", "Bạn cần đăng nhập", 401)
    if user["status"] != "active":
        return _deny("pending", "Tài khoản đang chờ admin duyệt", 403)
    if p.startswith("/api/admin/"):
        return None if user["role"] == "admin" else _deny("forbidden", "Chỉ admin", 403)
    for prefix, module in _PREFIX_MODULE:
        if p.startswith(prefix):
            if p.startswith("/api/legal/admin"):
                return None  # công cụ pháp luật tự kiểm tra quyền admin
            if not can(user, module):
                return _deny(
                    "no_permission", "Bạn chưa được cấp quyền dùng công cụ này", 403
                )
            return None
    return None  # job, export, uploads, gpu: chỉ cần đăng nhập và đang hoạt động


def check_job_owner(job):
    """Trả về (json, status) nếu người dùng không được xem job này, ngược lại None."""
    user = current_user()
    if (
        job.get("owner")
        and user
        and job["owner"] != user["email"]
        and user["role"] != "admin"
    ):
        return _deny("forbidden", "Tác vụ của người khác", 403)
    return None


# ── API ──────────────────────────────────────────────────────
def _body():
    return request.get_json(silent=True) or {}


def _norm_email(v):
    return str(v or "").strip().lower()


def _throttle_key(email):
    return (
        request.headers.get("CF-Connecting-IP") or request.remote_addr or "?",
        email,
    )


@bp.route("/auth/me")
def me():
    return jsonify(
        {
            "user": current_user(),
            "modules": MODULES,
            "needs_admin_setup": setup_code() is not None,
            "features": current_app.config.get("FEATURES", {}),
        }
    )


@bp.route("/auth/register", methods=["POST"])
def register():
    d = _body()
    email = _norm_email(d.get("email"))
    name = str(d.get("name") or "").strip()[:60]
    pw = str(d.get("password") or "")
    if not EMAIL_RE.match(email):
        return _deny("bad_email", "Email không hợp lệ", 400)
    if len(pw) < 8:
        return _deny("weak_password", "Mật khẩu tối thiểu 8 ký tự", 400)
    if not name:
        name = email.split("@")[0]
    is_admin_email = email == config.get()["admin_email"]
    with _lock:
        db = _read()
        if email in db["users"]:
            return _deny("exists", "Email này đã đăng ký", 409)
        user = {
            "name": name,
            "pw_hash": generate_password_hash(pw),
            "role": "user",
            "status": "pending",
            "modules": [],
            "created": int(time.time()),
        }
        if config.get().get("auto_approve", True):
            user.update(status="active", modules=[m for m in MODULES if m not in SENSITIVE_MODULES])
        if is_admin_email:
            code = setup_code()
            if not code or not secrets.compare_digest(
                str(d.get("setup_code") or ""), code
            ):
                return _deny(
                    "setup_code",
                    "Email admin cần mã cài đặt (file data/admin_setup_code.txt trên máy chủ)",
                    403,
                )
            user.update(role="admin", status="active", modules=MODULES)
        db["users"][email] = user
        _write(db)
        analytics.event("register", user=email, actor=email, status=user["status"], name=name)
        if is_admin_email:
            try:
                os.remove(SETUP_CODE_PATH)
            except OSError:
                pass
    session.clear()
    session.permanent = True
    session["email"] = email
    return jsonify({"user": current_user()})


@bp.route("/auth/login", methods=["POST"])
def login():
    d = _body()
    email, pw = _norm_email(d.get("email")), str(d.get("password") or "")
    key = _throttle_key(email)
    rec = _fails.get(key)
    if rec and rec[1] > time.time():
        return _deny(
            "locked",
            f"Sai quá nhiều lần, thử lại sau {int(rec[1] - time.time())} giây",
            429,
        )
    with _lock:
        u = _read()["users"].get(email)
    if not u or not check_password_hash(u["pw_hash"], pw):
        n = (rec[0] if rec else 0) + 1
        _fails[key] = [n, time.time() + 300 if n >= 5 else 0]
        analytics.event("login_fail", user=email if u else None, actor="anonymous", email=email[:120], attempt=n,
                        locked=n >= 5, known_user=bool(u))
        return _deny("bad_login", "Sai email hoặc mật khẩu", 401)
    if u.get("status") == "disabled":
        analytics.event("login_blocked", user=email, actor=email, reason="disabled")
        return _deny("disabled", "Tài khoản đã bị khoá", 403)
    _fails.pop(key, None)
    with _lock:
        db = _read()
        db["users"][email]["last_login"] = int(time.time())
        _write(db)
    session.clear()
    session.permanent = True
    session["email"] = email
    analytics.event("login_ok", user=email, actor=email)
    return jsonify({"user": current_user()})


@bp.route("/auth/logout", methods=["POST"])
def logout():
    if session.get("email"):
        analytics.event("logout", user=session.get("email"), actor=session.get("email"))
    session.clear()
    return jsonify({"ok": True})


@bp.route("/auth/password", methods=["POST"])
def change_password():
    user = current_user()
    if not user:
        return _deny("login_required", "Bạn cần đăng nhập", 401)
    d = _body()
    new = str(d.get("new_password") or "")
    if len(new) < 8:
        return _deny("weak_password", "Mật khẩu mới tối thiểu 8 ký tự", 400)
    with _lock:
        db = _read()
        u = db["users"][user["email"]]
        if not check_password_hash(u["pw_hash"], str(d.get("old_password") or "")):
            return _deny("bad_login", "Mật khẩu cũ không đúng", 403)
        u["pw_hash"] = generate_password_hash(new)
        _write(db)
    analytics.event("password_change", user=user["email"], actor=user["email"])
    return jsonify({"ok": True})


# ── Quản trị (chỉ admin; _guard đã chặn người khác) ──────────
@bp.route("/admin/users")
def admin_users():
    with _lock:
        users = _read()["users"]
    rows = [_public(e, u) for e, u in users.items()]
    rows.sort(
        key=lambda r: (
            r["role"] != "admin",
            r["status"] != "pending",
            r["created"] or 0,
        )
    )
    return jsonify({"users": rows, "modules": MODULES})


@bp.route("/admin/users/<email>", methods=["POST"])
def admin_update(email):
    email = _norm_email(email)
    d = _body()
    with _lock:
        db = _read()
        u = db["users"].get(email)
        if not u:
            return _deny("not_found", "Không có tài khoản này", 404)
        if u.get("role") == "admin":
            return _deny("forbidden", "Không đổi được tài khoản admin", 403)
        if "status" in d:
            if d["status"] not in ("pending", "active", "disabled"):
                return _deny("bad_status", "Trạng thái không hợp lệ", 400)
            u["status"] = d["status"]
        if "modules" in d:
            u["modules"] = [m for m in d["modules"] if m in MODULES]
        before = {"status": u.get("status"), "modules": list(u.get("modules", []))}
        if d.get("new_password"):
            if len(str(d["new_password"])) < 8:
                return _deny("weak_password", "Mật khẩu tối thiểu 8 ký tự", 400)
            u["pw_hash"] = generate_password_hash(str(d["new_password"]))
        _write(db)
    analytics.event("admin_update", user=email, before=before,
                    after={k: d[k] for k in ("status", "modules") if k in d}, password_reset=bool(d.get("new_password")))
    return jsonify({"user": _public(email, u)})


@bp.route("/admin/users/<email>", methods=["DELETE"])
def admin_delete(email):
    email = _norm_email(email)
    with _lock:
        db = _read()
        u = db["users"].get(email)
        if not u:
            return _deny("not_found", "Không có tài khoản này", 404)
        if u.get("role") == "admin":
            return _deny("forbidden", "Không xoá được admin", 403)
        del db["users"][email]
        _write(db)
    analytics.event("admin_delete", user=email, name=u.get("name"))
    return jsonify({"ok": True})
