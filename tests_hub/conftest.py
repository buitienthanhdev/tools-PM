"""Fixture dùng chung cho test module kế toán (golden dataset sinh một lần mỗi phiên)."""

import json

import pytest


@pytest.fixture(scope="session")
def golden(tmp_path_factory):
    from modules.accounting.golden.generate import build

    d = tmp_path_factory.mktemp("golden")
    build(d)
    return d


@pytest.fixture(scope="session")
def expected(golden):
    return json.loads((golden / "EXPECTED.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _restore_accounting_config(request):
    """Test kế toán bật module trong cấu hình toàn cục; trả lại như cũ để test Hub không khởi động worker nền."""
    yield
    if request.module.__name__.startswith("test_accounting"):
        import os

        from core import config as hubcfg

        hubcfg.get().pop("accounting", None)
        os.environ.pop("PM_ACCOUNTING_DIR", None)
