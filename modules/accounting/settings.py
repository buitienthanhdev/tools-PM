"""Cấu hình module kế toán: mặc định → khoá "accounting" trong data/config.json → biến môi trường."""

import os

from core import config as hubcfg

DEFAULTS = {
    "enabled": False,  # tắt mặc định: production chỉ bật sau khi được phê duyệt
    "data_dir": "",  # trống = <PM_DATA_DIR>/accounting
    "max_file_mb": 50,
    "max_files_per_upload": 500,
    "max_pdf_pages": 300,
    "max_zip_members": 2000,
    "max_zip_total_mb": 500,
    "max_zip_ratio": 200,  # tỉ lệ nén tối đa (chống zip bomb)
    "max_zip_depth": 2,
    "max_sheet_rows": 200000,
    "antivirus": "auto",  # auto | defender | off
    "ocr": "auto",  # auto | easyocr | off
    "paddle_ocr": "auto",  # auto | off — dự phòng OCR (venv riêng, xem extract/docai.py)
    "docling": "auto",  # auto | off — dự phòng đọc bảng PDF không kẻ ô (venv riêng)
    "docai_python": "",  # trống = <thư mục cha của Hub>/venvs/docai/Scripts/python.exe
    "max_pdf_table_pages": 50,
    "llm_planner": True,  # False: chỉ dùng bộ lập kế hoạch theo quy tắc
    "planner_model": "",  # trống = models.genreport
    "cloud_ai_allowed": False,  # không gửi chứng từ ra AI ngoài máy chủ
    "workers": 1,
    "task_timeout_s": 3600,
    "step_max_attempts": 3,
    "lease_s": 120,
    "review_threshold": 0.8,  # confidence dưới ngưỡng → chuyển kiểm duyệt
    "date_tolerance_days": 3,
    "allow_self_approval": False,
}


def get():
    cfg = dict(DEFAULTS)
    cfg.update(hubcfg.get().get("accounting") or {})
    if os.environ.get("PM_ACCOUNTING"):
        cfg["enabled"] = os.environ["PM_ACCOUNTING"] == "1"
    if os.environ.get("PM_ACCOUNTING_DIR"):
        cfg["data_dir"] = os.environ["PM_ACCOUNTING_DIR"]
    if not cfg["data_dir"]:
        cfg["data_dir"] = os.path.join(hubcfg.DATA_DIR, "accounting")
    return cfg


def data_dir():
    d = get()["data_dir"]
    os.makedirs(d, exist_ok=True)
    return d
