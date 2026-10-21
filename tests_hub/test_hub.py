"""Kiểm thử Hub: tài khoản, phân quyền, tác vụ, Real-ESRGAN thật. Chạy: pytest tests_hub -q"""

import io
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADMIN = "tienthanh18082003@gmail.com"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    from core import auth, config, jobs

    cfg = config.get()  # cô lập khỏi data/config.json thật của máy chủ
    cfg["admin_email"] = ADMIN
    cfg.pop("admin_password", None)
    cfg["auto_approve"] = True
    d = tmp_path_factory.mktemp("data")
    auth.USERS_PATH = str(d / "users.json")
    auth.SECRET_PATH = str(d / "secret.key")
    auth.SETUP_CODE_PATH = str(d / "code.txt")
    upload_dir = d / "uploads"
    upload_dir.mkdir()
    jobs.UPLOAD_DIR = upload_dir
    from routes import image as image_route
    from routes import system as system_route

    image_route.UPLOAD_DIR = upload_dir
    system_route.UPLOAD_DIR = upload_dir
    import app as hub

    hub.app.config["TESTING"] = True
    return hub


def client(app):
    return app.app.test_client()


def post(c, url, **kw):
    return c.post(url, json=kw)


def test_public_endpoints_open(app):
    c = client(app)
    health = c.get("/api/health")
    assert health.status_code == 200
    assert isinstance(health.json["image_ai_runtime_available"], bool)
    assert c.get("/api/auth/me").json["user"] is None


def test_api_requires_login(app):
    c = client(app)
    for url in ("/api/gpu/status", "/api/cv/status", "/api/legal/status", "/api/job/x"):
        r = c.get(url)
        assert r.status_code == 401, url
        assert r.json["code"] == "login_required"


def test_admin_needs_setup_code(app):
    from core import auth

    c = client(app)
    r = post(c, "/api/auth/register", email=ADMIN, password="matkhau123", name="Admin")
    assert r.status_code == 403 and r.json["code"] == "setup_code"
    code = auth.setup_code()
    assert code
    r = post(
        c,
        "/api/auth/register",
        email=ADMIN,
        password="matkhau123",
        name="Admin",
        setup_code=code,
    )
    assert r.status_code == 200
    assert r.json["user"]["role"] == "admin"
    assert auth.setup_code() is None  # mã dùng một lần


def test_user_flow_approve_and_permissions(app):
    admin, user = client(app), client(app)
    assert (
        post(admin, "/api/auth/login", email=ADMIN, password="matkhau123").status_code
        == 200
    )

    from core import config

    config.get()["auto_approve"] = False  # test luồng duyệt thủ công
    r = post(
        user,
        "/api/auth/register",
        email="Khach@Example.com",
        password="khach12345",
        name="Khách",
    )
    assert r.status_code == 200 and r.json["user"]["status"] == "pending"
    assert user.get("/api/gpu/status").json["code"] == "pending"  # chưa duyệt

    assert user.get("/api/admin/users").status_code == 403  # không phải admin
    assert (
        post(
            admin,
            "/api/admin/users/khach@example.com",
            status="active",
            modules=["whisper"],
        ).status_code
        == 200
    )

    assert (
        user.get("/api/gpu/status").status_code == 200
    )  # đã duyệt: dùng được API chung
    assert user.get("/api/cv/status").json["code"] == "no_permission"  # chưa cấp CV
    assert user.get("/api/legal/status").status_code == 403

    post(
        admin, "/api/admin/users/khach@example.com", modules=["whisper", "reviewingcv"]
    )
    assert user.get("/api/cv/status").status_code == 200

    post(admin, "/api/admin/users/khach@example.com", status="disabled")
    assert user.get("/api/gpu/status").status_code == 401  # bị khoá: văng ra ngay


def test_login_rate_limit_and_wrong_password(app):
    c = client(app)
    for _ in range(5):
        assert (
            post(c, "/api/auth/login", email="nobody@x.com", password="sai").status_code
            == 401
        )
    assert (
        post(c, "/api/auth/login", email="nobody@x.com", password="sai").status_code
        == 429
    )


def test_cannot_modify_admin(app):
    admin = client(app)
    post(admin, "/api/auth/login", email=ADMIN, password="matkhau123")
    assert (
        post(admin, f"/api/admin/users/{ADMIN}", status="disabled").status_code == 403
    )
    assert admin.delete(f"/api/admin/users/{ADMIN}").status_code == 403


def test_job_owner_isolated(app):
    a, b = client(app), client(app)
    post(a, "/api/auth/register", email="a@x.com", password="passwordA1", name="A")
    post(b, "/api/auth/register", email="b@x.com", password="passwordB1", name="B")
    admin = client(app)
    post(admin, "/api/auth/login", email=ADMIN, password="matkhau123")
    for e in ("a@x.com", "b@x.com"):
        post(admin, f"/api/admin/users/{e}", status="active", modules=["image"])

    png = io.BytesIO()
    from PIL import Image

    Image.new("RGB", (64, 48), (200, 80, 40)).save(png, "PNG")
    png.seek(0)
    up = a.post(
        "/api/image/upload",
        data={"image": (png, "t.png")},
        content_type="multipart/form-data",
    )
    assert up.status_code == 200 and up.json["width"] == 64
    assert a.get(up.json["file_path"]).status_code == 200
    assert b.get(up.json["file_path"]).status_code == 403
    r = post(
        a, "/api/image/process", job_id=up.json["job_id"], scale="4x", model="photo"
    )
    assert r.status_code == 200
    jid = r.json["job_id"]
    assert b.get(f"/api/job/{jid}").status_code == 403  # người khác không xem được
    assert admin.get(f"/api/job/{jid}").status_code == 200  # admin xem được

    # Real-ESRGAN thật: ảnh đầu ra phải đúng kích thước 4x
    for _ in range(120):
        j = a.get(f"/api/job/{jid}").json
        if j["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    assert j["status"] == "completed", j
    assert (j["result"]["width"], j["result"]["height"]) == (256, 192)
    assert a.get(j["result"]["enhanced_path"]).status_code == 200
    assert b.get(j["result"]["enhanced_path"]).status_code == 403
    out = a.get(j["result"]["enhanced_path"])
    assert out.status_code == 200
    assert Image.open(io.BytesIO(out.data)).size == (256, 192)
    assert "owner" not in j


def test_image_validation(app):
    a = client(app)
    post(a, "/api/auth/login", email="a@x.com", password="passwordA1")
    assert post(a, "/api/image/process", job_id="x", scale="8x").status_code == 400
    assert (
        post(
            a, "/api/image/process", job_id="x", scale="2x", model="khong-co"
        ).status_code
        == 400
    )
    assert (
        post(
            a, "/api/image/process", job_id="khong-ton-tai", scale="2x", model="photo"
        ).status_code
        == 404
    )


def test_tools_health_shape(app):
    c = client(app)
    h = c.get("/api/health/tools").json
    assert set(h["tools"]) == {
        "whisper",
        "voxcpm",
        "image",
        "genreport",
        "legal",
        "reviewingcv",
        "spacet",
    }
    assert h["tools"]["image"]["ok"] is True
    assert "busy" in h["gpu"]


def test_cv_edit_check_flags_invented_skills():
    from modules.reviewingcv import engine

    cv = "Project Manager at FPT, managed 3 Agile teams, budget 400k USD, Scrum, Jira"
    edits = [
        {"old": "Scrum, Jira", "new": "Scrum, Jira, SAFe-ready"},
        {"old": "budget 400k USD", "new": "managed project budgets"},
        {"old": "không có trong CV", "new": "Scrum"},
        {"old": "managed 3 Agile teams", "new": "led 3 Agile teams"},
    ]
    out = engine.check_edits(cv, edits)
    assert any("safe" in w.lower() for w in out[0]["warnings"])
    assert any("400k" in w for w in out[1]["warnings"])
    assert any("nguyên văn" in w for w in out[2]["warnings"])
    assert out[3]["warnings"] == []


def test_llm_status_reports_missing_model():
    from core import llm

    st = llm.status("model-khong-ton-tai-xyz")
    assert st["ok"] is False and st["error"]


def test_split_text_chunks_keeps_order_and_limit():
    import re

    from routes.speech import split_text_chunks

    text = "Xin chào các bạn. " * 30 + "Đây là một câu rất dài, có nhiều dấu phẩy, " * 8
    chunks = split_text_chunks(text)
    assert len(chunks) > 1 and all(len(c) <= 241 for c in chunks)
    squeeze = lambda t: re.sub(r"\s+", "", t)  # noqa: E731
    assert squeeze("".join(chunks)) == squeeze(text)  # không mất, không đảo chữ
    assert split_text_chunks("Ngắn thôi.") == ["Ngắn thôi."]


def test_genreport_rejects_empty_notes():
    import genreport_service as g

    with pytest.raises(ValueError):
        g.generate_word_report({"raw_text": "   "})
