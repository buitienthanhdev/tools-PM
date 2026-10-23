# Production readiness — `sonxit.io.vn/accounting`

Kết luận: **chưa đủ điều kiện bật cho dữ liệu kế toán thật của doanh nghiệp**; đủ điều kiện bật có giới hạn cho nhóm thử nghiệm
với dữ liệu ẩn danh, sau khi được phê duyệt.

| Hạng mục | Trạng thái |
| --- | --- |
| Toàn bộ test module PASS, không hồi quy Hub | PASS |
| Module tắt mặc định, rollback bằng cờ cấu hình | PASS |
| Cô lập tenant, phân quyền máy chủ, phân tách nhiệm vụ | PASS (test) — chưa pentest độc lập |
| Prompt injection không có hiệu lực | PASS (test + staging) |
| Bản gốc bất biến, audit chuỗi băm, backup + verify | PASS — chưa lập lịch backup tự động |
| Khôi phục worker, retry có backoff, dead letter | PASS (test) |
| Chạy thật trên staging với LLM + OCR thật | PASS |
| Danh mục tài khoản TT 99/2025 đã đối chiếu Phụ lục II | **CHƯA** — cần kế toán trưởng |
| Quy tắc thuế 8% theo kỳ, mẫu báo cáo pháp định | **CHƯA** |
| Đo chất lượng trên chứng từ thật đã ẩn danh | **CHƯA** |
| MFA, SSO, retention nhật ký, giám sát (OpenTelemetry) | **CHƯA** |
| Kiểm thử tải đồng thời nhiều người dùng | **CHƯA** |
| Ý kiến pháp lý về AGPL của PyMuPDF | **CHƯA** (rủi ro có từ trước trong Hub) |
| Phê duyệt triển khai từ chủ hệ thống | **CHƯA** |
