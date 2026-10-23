"""
Policy engine: quyết định một bước có được phép chạy không — dựa trên lớp tác vụ, vai trò người dùng
và Ý ĐỊNH TRONG CÂU LỆNH CỦA NGƯỜI DÙNG (nguồn tin cậy). Nội dung tài liệu không bao giờ nâng quyền.
"""

from ..extract.base import fold
from .tools import COMMIT, EXTERNAL, GENERATE_ARTIFACT, PROPOSE, READ_ONLY, TRANSFORM, WRITE_DRAFT

DEFAULT_ALLOWED = {READ_ONLY, TRANSFORM, GENERATE_ARTIFACT, PROPOSE, WRITE_DRAFT, COMMIT}


def allowed_classes(ctx):
    out = set()
    if ctx.can("run_task"):
        out |= {READ_ONLY, TRANSFORM, GENERATE_ARTIFACT, WRITE_DRAFT}
    if ctx.can("edit_draft"):
        out.add(PROPOSE)
    if ctx.can("request_commit"):
        out.add(COMMIT)
    return out  # EXTERNAL_ACTION: không có công cụ, không bao giờ cho phép tự động


def allow(tool, command, allowed):
    if tool.task_class == EXTERNAL:
        return False, "hành động bên ngoài không được tự động thực hiện"
    if tool.task_class not in allowed:
        return False, f"vai trò không có quyền cho lớp {tool.task_class}"
    if tool.task_class == COMMIT and "ghi so" not in fold(command):
        return False, "chỉ gửi yêu cầu ghi sổ khi người dùng yêu cầu rõ ràng"
    return True, ""
