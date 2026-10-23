"""Theo dõi truy cập + dashboard quản trị: ghi đúng, không ghi bí mật, chỉ admin xem được. pytest tests_hub/test_hub_analytics.py -q"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADMIN = "boss@x.com"


@pytest.fixture()
def hub(tmp_path):
    from flask import Flask, jsonify

    from core import analytics, auth, config
    from routes import admin_analytics

    cfg = config.get()
    cfg["admin_email"] = ADMIN
    cfg["auto_approve"] = True
    cfg.pop("admin_password", None)
    auth.USERS_PATH = str(tmp_path / "users.json")
    auth.SECRET_PATH = str(tmp_path / "secret.key")
    auth.SETUP_CODE_PATH = str(tmp_path / "code.txt")
    analytics.reset_for_tests(str(tmp_path / "analytics.db"))
    app = Flask("analytics_test")
    app.config["TESTING"] = True
    auth.init_app(app)
    analytics.init_app(app)
    app.register_blueprint(admin_analytics.bp)

    @app.route("/api/image/boom", methods=["POST"])
    def boom():
        raise RuntimeError("hỏng có chủ đích")

    @app.errorhandler(Exception)
    def err(e):
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return e
        analytics.server_error(e)
        return jsonify({"error": "Lỗi máy chủ"}), 500

    return app


def _register(c, email, pw="matkhau123", **extra):
    r = c.post("/api/auth/register", json={"email": email, "password": pw, "name": email.split("@")[0], **extra})
    assert r.status_code == 200, r.json
    return r


def _admin(app):
    from core import auth

    c = app.test_client()
    code = auth.setup_code()
    _register(c, ADMIN, setup_code=code)
    return c


def test_tracking_end_to_end(hub):
    from core import analytics

    admin = _admin(hub)
    u = hub.test_client()
    ua = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit Version/17.0 Mobile Safari/604.1"}
    _register(u, "an@x.com")
    # Lượt xem trang qua beacon (text/plain như sendBeacon), thời gian ở lại, lỗi JS
    hdr = {**ua, "CF-Connecting-IP": "203.0.113.7", "CF-IPCountry": "VN"}
    body = json.dumps({"vid": "v-an", "sid": "s1", "path": "/accounting", "title": "Kế toán", "ref": "https://google.com/search?q=x", "screen": "390x844"})
    assert u.post("/api/track/pv", data=body, headers=hdr, content_type="text/plain").status_code == 204
    u.post("/api/track/leave", data=json.dumps({"vid": "v-an", "path": "/accounting", "dur": 42.5}), headers=hdr)
    u.post("/api/track/err", data=json.dumps({"vid": "v-an", "kind": "TypeError", "msg": "x is undefined", "src": "a.js:1:2", "path": "/accounting"}), headers=hdr)
    # Đăng nhập sai (không ghi mật khẩu), lỗi máy chủ, yêu cầu bị từ chối
    anon = hub.test_client()
    anon.post("/api/auth/login", json={"email": "an@x.com", "password": "MAT-KHAU-BI-MAT"}, headers={"CF-Connecting-IP": "198.51.100.9"})
    assert u.post("/api/image/boom", json={"secret_field": "NOI-DUNG-NHAY-CAM"}, headers=hdr).status_code == 500
    assert anon.get("/api/admin/analytics/overview").status_code == 401
    assert u.get("/api/admin/analytics/overview").status_code == 403  # người dùng thường không xem được
    anon.get("/wp-login.php", headers={"CF-Connecting-IP": "198.51.100.66"})  # máy quét: SPA trả 200 nhưng vẫn phải ghi
    analytics.flush()

    o = admin.get("/api/admin/analytics/overview?range=24h").json
    k = o["kpis"]
    assert k["pageviews"] == 1 and k["visitors"] == 1 and k["avg_duration_s"] == 42.5
    assert k["login_fails"] == 1 and k["registrations"] == 2 and k["errors_5xx"] == 1 and k["app_errors"] == 2
    assert sum(s["pageviews"] for s in o["series"]) == 1 and len(o["series"]) >= 24
    t = admin.get("/api/admin/analytics/top?range=24h").json
    assert t["pages"][0]["path"] == "/accounting" and t["referrers"][0]["k"] == "google.com"
    assert t["countries"][0]["k"] == "VN" and t["devices"][0]["k"] == "mobile" and t["browsers"][0]["k"] == "Safari"
    assert any(m["module"] == "image" and m["e5"] == 1 for m in t["modules"])
    sec = admin.get("/api/admin/analytics/security?range=24h").json
    assert sec["scans_404"] and "/wp-login.php" in sec["scans_404"][0]["paths"]
    assert sec["login_fail_by_ip"][0]["ip"] == "198.51.100.9" and sec["login_fail_by_email"][0]["email"] == "an@x.com"
    errs = admin.get("/api/admin/analytics/errors?range=24h").json
    kinds = {(g["source"], g["kind"]) for g in errs["groups"]}
    assert ("server", "RuntimeError") in kinds and ("client", "TypeError") in kinds
    assert "RuntimeError" in errs["http_5xx"][0]["errors"]
    # Hành trình người dùng
    d = admin.get("/api/admin/analytics/user?email=an@x.com&range=24h").json
    types = {e["type"] for e in d["timeline"]}
    assert {"page", "fail", "event", "error"} <= types and d["stats"]["pageviews"] == 1
    # Nhật ký thô có lọc + CSV
    lg = admin.get("/api/admin/analytics/log?kind=requests&range=24h&status=5xx").json
    assert len(lg["rows"]) == 1 and lg["rows"][0]["path"] == "/api/image/boom" and lg["rows"][0]["error"] == "RuntimeError"
    csv_ = admin.get("/api/admin/analytics/export.csv?kind=events&range=24h")
    assert csv_.status_code == 200 and "login_fail" in csv_.get_data(as_text=True)
    # Trực tiếp: người dùng vừa hoạt động đang online
    live = admin.get("/api/admin/analytics/live").json
    assert any(x.get("user") == "an@x.com" for x in live["online"])
    # Không bao giờ ghi mật khẩu / nội dung request
    raw = open(analytics.DB_PATH, "rb").read().decode("utf-8", "ignore")
    for secret in ("MAT-KHAU-BI-MAT", "NOI-DUNG-NHAY-CAM", "matkhau123"):
        assert secret not in raw


def test_beacon_rate_limited_and_validated(hub):
    c = hub.test_client()
    assert c.post("/api/track/nope", data="{}").status_code == 404
    assert c.post("/api/track/pv", data="khong-phai-json").status_code == 400
    codes = [c.post("/api/track/ping", data=json.dumps({"vid": "x"}), headers={"CF-Connecting-IP": "192.0.2.1"}).status_code for _ in range(130)]
    assert codes.count(204) == 120 and codes[-1] == 429


def test_path_normalization_and_ua():
    from core import analytics

    assert analytics.norm_path("/api/accounting/o/3a1fcd38-db0f-4d4f-a812-75ec038a44c7/tasks/123") == "/api/accounting/o/:id/tasks/:id"
    assert analytics.parse_ua("curl/8.4.0")[2] == "bot"
    assert analytics.parse_ua("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 Edg/130.0")[:3] == ("Edge", "Windows", "desktop")
    assert analytics.module_of("/api/cv/review") == "reviewingcv" and analytics.module_of("/accounting") == "accounting"
