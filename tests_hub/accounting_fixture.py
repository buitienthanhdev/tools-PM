"""Fixture chung cho test module kế toán: dữ liệu tạm, golden dataset, Flask app có gắn module."""

import io
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ORG_TAX = "0012345678"


def configure(tmp_path, **overrides):
    """Trỏ module kế toán + tài khoản Hub sang thư mục tạm; trả về dict cấu hình đang dùng."""
    from core import auth
    from core import config as hubcfg
    from modules.accounting import db

    os.environ["PM_ACCOUNTING_DIR"] = str(tmp_path / "acct")
    cfg = hubcfg.get()
    cfg["auto_approve"] = True
    cfg.pop("admin_password", None)
    cfg["accounting"] = {"enabled": True, "antivirus": "off", "ocr": "off", "llm_planner": False,
                         "max_zip_ratio": 200, **overrides}
    auth.USERS_PATH = str(tmp_path / "users.json")
    auth.SECRET_PATH = str(tmp_path / "secret.key")
    auth.SETUP_CODE_PATH = str(tmp_path / "code.txt")
    db.reset_for_tests()
    return cfg["accounting"]


def make_app():
    from flask import Flask

    from core import auth
    from modules.accounting import api

    app = Flask("aaap_test")
    app.config["TESTING"] = True
    app.config["FEATURES"] = {"accounting": True}
    auth.init_app(app)
    app.register_blueprint(api.bp)
    return app


def register(client, email, pw="matkhau123", name=None):
    r = client.post("/api/auth/register", json={"email": email, "password": pw, "name": name or email.split("@")[0]})
    assert r.status_code == 200, r.json
    return r


def grant(email, modules=("accounting",)):
    from core import auth

    db = auth._read()
    db["users"][email]["modules"] = list(set(db["users"][email]["modules"]) | set(modules))
    auth._write(db)


def upload(client, org, paths, conversation_id=None):
    data = {"files": [(io.BytesIO(Path(p).read_bytes()), Path(p).name) for p in paths]}
    if conversation_id:
        data["conversation_id"] = conversation_id
    r = client.post(f"/api/accounting/o/{org}/files", data=data, content_type="multipart/form-data")
    assert r.status_code == 200, r.json
    return r.json


def new_ctx(org_name="Test", user="a@x.com", tax_id=ORG_TAX, roles=None):
    from modules.accounting import security

    kw = {"tax_id": tax_id}
    if roles:
        kw["roles"] = roles
    org = security.create_org(org_name, user, **kw)
    return security.context(org, user)


def ingest(ctx, paths):
    from modules.accounting import extract
    from modules.accounting.ingest import pipeline

    results, ids = [], []
    for p in paths:
        r = pipeline.ingest_stream(ctx, io.BytesIO(Path(p).read_bytes()), Path(p).name)
        results.append(r)
        for fid in pipeline.flatten([r]):
            extract.ensure(ctx.org_id, fid, ORG_TAX)
            ids.append(fid)
    return results, ids
