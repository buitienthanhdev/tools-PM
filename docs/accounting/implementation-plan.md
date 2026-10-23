# Kế hoạch & trạng thái triển khai theo phase

Ký hiệu: ✅ làm xong + có test PASS · 🟡 làm một phần · ⛔ chưa làm.

| Phase | Hạng mục | Trạng thái | Bằng chứng / ghi chú |
| --- | --- | --- | --- |
| 0 | Khảo sát repo, ADR, rủi ro, kế hoạch | ✅ | docs/accounting/* |
| 1 Core | Tích hợp Hub, xác thực, tổ chức & vai trò, DB + migration, kho file bất biến, upload, task | ✅ | test_accounting_api, test_accounting_engine |
| 1 | Docker Compose | ⛔ | Máy chủ không có Docker (ADR-0001). Triển khai = gắn vào Hub |
| 2 Document | PDF chữ, OCR, XML hoá đơn, Excel/CSV/TSV/DOCX/JSON/TXT, ZIP, provenance, kiểm tra | ✅ | test_accounting_extract; OCR thật: ảnh rõ 8/8 trường đúng, ảnh mờ không nhận diện (trả NEEDS_REVIEW) |
| 2 | Dòng hàng hoá trên PDF, sao kê PDF (kể cả không kẻ ô), .xls, OCR dự phòng ảnh mờ, kiểm tra MST + tiền bằng chữ | ✅ | pdfplumber, docling, xlrd, PaddleOCR, python-stdnum, num2words; test_accounting_extract (docling/Paddle bật bằng `AAAP_DOCAI_TEST=1`) |
| 2 | .doc nhị phân (Word 97-2003) | ⛔ | Từ chối với mã `unsupported_doc` |
| 3 Orchestrator | Chat, planner LLM + quy tắc, registry 21 công cụ, policy, timeline, retry/resume | ✅ | LLM thật (qwen3.8:27b) chạy trên staging, 3 kịch bản |
| 4 Accounting | Bút toán kép, hệ thống TK, đối soát, kiểm tra, rule engine có phiên bản | ✅ | Danh mục TK TT99 **chưa đối chiếu Phụ lục II** |
| 4 | Tồn kho, TSCĐ/khấu hao, thuế TNDN/TNCN | ⛔ | Chưa có công cụ |
| 5 Report | Excel (công thức, định dạng, biểu đồ, nguồn, cảnh báo), PDF, phiên bản, xem trước | ✅ | Xác minh tự động sau khi ghi file |
| 5 | Mẫu báo cáo pháp định (BCTC, tờ khai) | ⛔ | Chỉ báo cáo phân tích nội bộ |
| 6 HITL | Hàng đợi kiểm duyệt, phê duyệt 2 người (tổ chức 1 người: tự duyệt có xác nhận), bằng chứng, sửa sai bằng bút toán đảo, audit chuỗi băm | ✅ | test SoD, kỳ khoá, bút toán đảo |
| 7 Hardening | Backup/verify, giới hạn, rate limit, khôi phục worker, đo chỉ số, OpenTelemetry (JSONL cục bộ, P95 trên trang sức khoẻ) | 🟡 | Chưa: MFA, SSO, gửi trace tới collector, kiểm thử tải đồng thời nhiều người, pentest |
| — | Scheduled workflows | ⛔ | Không hiển thị trong UI (không làm giao diện giả) |

## Điều kiện để sang production
1. Người có thẩm quyền phê duyệt (xem production-readiness.md).
2. Kế toán trưởng đối chiếu hệ thống tài khoản với Phụ lục II TT 99/2025.
3. Thử với một bộ chứng từ thật đã ẩn danh của doanh nghiệp và đo lại chỉ số.

## Việc tiếp theo đề xuất
Đối soát dòng hàng PDF với phiếu nhập; nhập danh mục TK từ file; chỉnh tay giá trị trích xuất (hiện chỉ ghi feedback);
quy đổi tỷ giá có nguồn cấu hình; báo cáo pháp định có phiên bản; worker tiến trình riêng; xuất dữ liệu sang ERP.
