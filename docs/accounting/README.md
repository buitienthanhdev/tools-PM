# Accounting AI (AAAP) — module `/accounting` của PM Tools

Trạng thái: **đã triển khai và kiểm thử trên staging, CHƯA lên production** (cần phê duyệt — xem [deployment.md](deployment.md)).

| Tài liệu | Nội dung |
| --- | --- |
| [repo-assessment.md](repo-assessment.md) | Khảo sát PM Tools hiện tại + 12 repo upstream (license, mức duy trì, khả năng dùng) |
| [architecture.md](architecture.md) | Kiến trúc, luồng dữ liệu, ba lớp AI / xác định / quản trị |
| [adr/](adr/) | Quyết định kiến trúc (tích hợp, DB, orchestrator, không chạy mã AI sinh, xử lý tài liệu) |
| [implementation-plan.md](implementation-plan.md) | Phase 0–7: đã làm / chưa làm / điều kiện nghiệm thu |
| [risk-register.md](risk-register.md) | Rủi ro và biện pháp |
| [security.md](security.md) | Mô hình đe doạ, phân quyền, cô lập tenant, prompt injection, audit |
| [deployment.md](deployment.md) | Staging, đưa lên production, rollback |
| [admin-guide.md](admin-guide.md) · [user-guide.md](user-guide.md) | Hướng dẫn quản trị / sử dụng |
| [test-report.md](test-report.md) | Lệnh kiểm thử, kết quả, chỉ số trên golden dataset |
| [production-readiness.md](production-readiness.md) | Checklist sẵn sàng production (PASS / CHƯA) |

Mã nguồn: `modules/accounting/` (backend), `static/modules/accounting/` + `static/styles/accounting.css` (giao diện),
`tests_hub/test_accounting_*.py` (kiểm thử), `modules/accounting/golden/` (bộ dữ liệu mẫu + đánh giá).
