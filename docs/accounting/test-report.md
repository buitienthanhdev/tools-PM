# Báo cáo kiểm thử — 2026-10-23

Môi trường: Windows 11 Pro, Python 3.12.10, venv của Hub, RTX 5090. Chạy trong worktree `feature/accounting`.

## Lệnh và kết quả

| Lệnh | Kết quả |
| --- | --- |
| `ruff check .` | All checks passed |
| `pytest tests_hub -k accounting -q` | **90 passed, 3 skipped** (OCR GPU bật bằng `AAAP_OCR_TEST=1`; PaddleOCR/docling bật bằng `AAAP_DOCAI_TEST=1`) |
| `AAAP_DOCAI_TEST=1 pytest tests_hub/test_accounting_extract.py -k "paddle or docling"` | 2 passed (PaddleOCR đọc ảnh mờ; docling đọc sao kê không kẻ ô) |
| `AAAP_OCR_TEST=1 pytest tests_hub/test_accounting_extract.py -k ocr` | 1 passed (OCR thật trên GPU) |
| `pytest -q --ignore=tests_hub/test_image_processing.py` (toàn bộ Hub) | 115 passed, 3 skipped, **3 failed** |

3 lỗi toàn bộ Hub (`test_job_owner_isolated`, `test_image_validation`, `test_tools_health_shape`) **có từ trước** (baseline trước thay đổi:
25 passed / 3 failed, cùng 3 test): worktree không có binary Real-ESRGAN bị gitignore. Không có hồi quy do module kế toán.

## Bao phủ 15 bất biến bắt buộc (PHẦN XIV 14.2)

| # | Bất biến | Test |
| --- | --- | --- |
| 1 | Nợ = Có | `test_unbalanced_entry_rejected`, `test_balance_property_random` (60 bút toán ngẫu nhiên) |
| 2 | Không ghi trùng | `test_idempotent_no_duplicate_posting`, `test_worker_crash_resumes_without_duplicates` |
| 3 | Kỳ đã khoá | `test_locked_period_rejected` |
| 4 | Không mất chứng từ gốc | `test_original_files_cannot_be_deleted`, `test_backup_and_restore_verification` |
| 5 | Không trộn tenant | `test_tenant_isolation_api`, `test_tenant_isolation_engine` |
| 6 | Không nhận chứng từ thiếu bằng chứng | `test_invoice_missing_fields_flagged`, `test_journal_scenario_e_and_approval` (HĐ CONFLICTED không được định khoản) |
| 7 | Không sai do float | `test_no_float_drift_property`, `test_vn_format_roundtrip_property` |
| 8 | Không làm tròn sai âm thầm | `test_rounding_half_up_explicit`, `test_parse_amount` (AMBIGUOUS), chênh lệch quy đổi được ghi rõ |
| 9 | Không ghi sổ khi chưa duyệt | `test_no_posting_without_approval_and_sod`, `test_changed_after_request_cannot_be_approved` |
| 10 | Không thực thi lệnh trong tài liệu | `test_prompt_injection_has_no_effect`, `test_planner_output_is_policed` |
| 11 | Không mất trạng thái khi worker chết | `test_worker_crash_resumes_without_duplicates` |
| 12 | Không lặp side effect khi retry | `test_transient_error_retried_with_backoff` |
| 13 | Không vượt quyền | `test_hub_permission_required`, `test_role_enforcement_api` |
| 14 | Không kết luận trùng chỉ vì số tiền | `test_same_amount_is_not_duplicate` |
| 15 | Không báo thành công khi thiếu dữ liệu | `test_scenario_c_and_d_revise_keeps_old_version`, `test_missing_org_tax_id_never_silently_empties`, `test_cancel_and_waiting_for_input` |

## Chỉ số trên golden dataset (`python -m modules.accounting.golden.evaluate`)

| Chỉ số | Giá trị |
| --- | --- |
| Document parsing success rate | 0,9545 (42/44; thất bại có chủ đích: PDF có mật khẩu, `corrupt_excel.xls`). Trước đây 0,972 (35/36): .xls nay là định dạng được hỗ trợ nên file .xls hỏng được tính là đọc thất bại thay vì bị từ chối |
| File độc hại/không hỗ trợ bị từ chối đúng mã | 3/3 (exe giả PDF, .doc nhị phân, Office mã hoá; + zip bomb, path traversal, XXE, ZIP lồng sâu xử lý đúng) |
| Độ đúng trạng thái hoá đơn / tổng tiền | 1,0 / 1,0 (19 hoá đơn, gồm MST sai chữ số kiểm tra → NEEDS_REVIEW, số tiền bằng chữ lệch → CONFLICTED, dòng hàng PDF sai phép nhân → NEEDS_REVIEW) |
| Trường PDF so với XML cùng hoá đơn | 9/9 |
| Trùng lặp: recall / dương tính giả | 1,0 / 0,0 |
| Đối soát: precision / recall | 1,0 / 1,0; 36% nhóm chuyển người kiểm duyệt (tên đối tác so khớp mờ bằng RapidFuzz, ngưỡng chặt cho tên ngắn) |
| Task completion / artifact hợp lệ | 1,0 / 1,0 (15 tác vụ) |
| Độ trễ thực thi P50 / P95 | 0,073 s / 0,09 s (không gồm upload và LLM; trích xuất đã cache) |
| LLM lập kế hoạch (staging, qwen3.8:27b) | 2–3 s khi model đã nạp; 19 s lần đầu |
| OCR thật | Ảnh scan rõ (EasyOCR): 8/8 trường đúng (vẫn NEEDS_REVIEW). Ảnh mờ Gaussian σ=3,5: EasyOCR không nhận diện; PaddleOCR dự phòng nhận diện được hoá đơn (vẫn NEEDS_REVIEW, kiểm tra MST/chữ báo cần xem lại thay vì xung đột) |
| docling | Sao kê PDF không kẻ ô: đọc được bảng giao dịch (pdfplumber không tìm thấy bảng) |
| Telemetry | Span task/plan/tool/extract/docai ghi JSONL; test xác nhận không có nội dung chứng từ trong thuộc tính |

**Giới hạn của các con số:** golden dataset do nhóm phát triển tự tạo từ dữ liệu hư cấu, nên 100% chỉ chứng minh hệ thống đúng
trên các tình huống đã thiết kế, **không** phải độ chính xác trên chứng từ thật. Cần đo lại với bộ chứng từ thật đã ẩn danh.

## Kiểm thử giao diện thật (staging 127.0.0.1:5055, Edge headless qua DevTools Protocol, LLM thật)
- Kịch bản A hoá đơn (7 file gồm ZIP, PDF, XML injection, exe giả PDF): hoàn thành, báo cáo xác minh đạt, mở bằng chứng PDF/XML.
- Kịch bản B đối soát: kết quả khớp golden (EXACT 1, VERIFIED 4, POTENTIAL 2, AMBIGUOUS 1, CONFLICTED 1, chênh lệch −677.000).
- Kịch bản C trên màn hình 390×844 (mobile): hoàn thành, panel báo cáo toàn màn hình.
- 0 lỗi console JavaScript ở cả 3 lượt. Hai lỗi phát hiện qua staging đã sửa và có test hồi quy:
  lọc theo chiều mua/bán khi tổ chức chưa có MST trả rỗng âm thầm; ZIP trùng không gắn file con vào phiên mới.

## Dùng thử như người dùng thật (staging, LLM thật, 2026-10-23) và các lỗi đã sửa

~25 câu lệnh tự nhiên trên file hư cấu ngoài golden (danh sách sinh viên, bảng kê bán hàng tiêu đề 2 tầng, sao kê CSV
kiểu ngân hàng khác, bảng lương, hoá đơn, file 50.000 dòng, scan mờ). Kết quả trước → sau khi sửa:

| Lỗi phát hiện | Sau khi sửa (đối chiếu độc lập) | Test hồi quy |
| --- | --- | --- |
| Phiên không có file xử lý toàn bộ hoá đơn của tổ chức (kể cả phiên khác) | Hỏi người dùng tải file; danh sách file rỗng = không có dữ liệu | `test_empty_conversation_never_uses_other_sessions_files` |
| "Định khoản hoá đơn mua vào" sinh bút toán cho hoá đơn bán ra | Lọc theo chiều yêu cầu | `test_journal_direction_follows_request` |
| MST sai chữ số kiểm tra vẫn lưu; hoá đơn "không liên quan" trả 0 âm thầm | Từ chối khi lưu; cảnh báo + hỏi lại khi không hoá đơn nào mang MST tổ chức | `test_invalid_org_tax_id_rejected_and_unrelated_invoices_flagged` |
| Không nói thẳng câu trả lời (người dùng production: "nói tiếng người xem nào?") | Đoạn đầu tin nhắn là câu trả lời có số liệu, chi tiết các bước ở dưới | `test_gender_count_answer_and_out_of_scope`, `test_bank_summary_and_direct_answer` |
| Không tính được tổng/nhóm/lọc/top trên bảng bất kỳ; không hiểu "Phái" = "giới tính" | Công cụ `analyze_table` (Decimal, đồng nghĩa + RapidFuzz + theo giá trị, tháng/quý/năm từ cột ngày): 40 nữ / 80 nam; doanh thu 158.747.000; Nước mắm 48.735.000 cao nhất; SV990120 điểm 9,48; 50.000 dòng → 62.006.543.000 | `test_two_row_header_and_table_analysis` |
| Sao kê đọc đúng nhưng không trả lời tiền vào/ra, số dư | Công cụ `summarize_bank`: 196.000.000 / 88.500.000, số dư 250.000.000 → 357.500.000 | `test_bank_summary_and_direct_answer` |
| Tiêu đề gộp 2 dòng: dòng tiêu đề phụ bị tính là dữ liệu | Ghép tiêu đề 2 tầng (bộ đọc Excel 1.4.0) | `test_two_row_header_and_table_analysis` |
| Hỏi thuế GTGT trả tổng tiền; hoá đơn bị bỏ vì bước kiểm tra không chạy | Trả thuế đầu vào/đầu ra riêng; luôn kiểm tra trước khi tổng hợp/định khoản | `test_planner_output_is_policed` |
| Luôn tạo file Excel kể cả khi không có kết quả | Bỏ qua (SKIPPED) khi các bước phân tích không có kết quả | — |
| Câu ngoài phạm vi / yêu cầu xoá sổ trả lời lạc đề; TNCN, mẫu 01-2/GTGT báo "hoàn thành" | Nói rõ ngoài phạm vi / chưa hỗ trợ; trạng thái "hoàn thành một phần" | `test_gender_count_answer_and_out_of_scope` |
| Tải lại file cũ ở phiên mới bị báo "trùng" | Trùng file chỉ tính trong cùng hội thoại | — |
| Tổ chức một người không bao giờ ghi sổ được | Được tự duyệt sau khi xác nhận, ghi audit; tự tắt khi có thành viên thứ hai | `test_single_member_org_can_self_approve_with_confirmation` |
| `data/accounting/` không nằm trong `.gitignore` | Đã thêm | — |

Còn lại: kết quả phụ thuộc LLM chọn đúng công cụ — các câu trên đều đúng trong lượt thử, nhưng chưa đo trên tập câu hỏi lớn.
