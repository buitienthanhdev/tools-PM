# Báo cáo kiểm thử — 2026-10-23

Môi trường: Windows 11 Pro, Python 3.12.10, venv của Hub, RTX 5090. Chạy trong worktree `feature/accounting`.

## Lệnh và kết quả

| Lệnh | Kết quả |
| --- | --- |
| `ruff check .` | All checks passed |
| `pytest tests_hub/test_accounting_engine.py tests_hub/test_accounting_extract.py tests_hub/test_accounting_api.py -q` | **67 passed, 1 skipped** (OCR GPU, bật bằng `AAAP_OCR_TEST=1`) |
| `AAAP_OCR_TEST=1 pytest tests_hub/test_accounting_extract.py -k ocr` | 1 passed (OCR thật trên GPU) |
| `pytest -q --ignore=tests_hub/test_image_processing.py` (toàn bộ Hub) | 92 passed, 1 skipped, **3 failed** |

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
| Document parsing success rate | 0,972 (35/36; thất bại có chủ đích: PDF có mật khẩu) |
| File độc hại/không hỗ trợ bị từ chối đúng mã | 3/3 (+ zip bomb, path traversal, XXE, ZIP lồng sâu xử lý đúng) |
| Độ đúng trạng thái hoá đơn / tổng tiền | 1,0 / 1,0 (16 hoá đơn) |
| Trường PDF so với XML cùng hoá đơn | 9/9 |
| Trùng lặp: recall / dương tính giả | 1,0 / 0,0 |
| Đối soát: precision / recall | 1,0 / 1,0 (7 cặp đúng); 36% nhóm chuyển người kiểm duyệt |
| Task completion / artifact hợp lệ | 1,0 / 1,0 (15 tác vụ) |
| Độ trễ thực thi P50 / P95 | 0,061 s / 0,079 s (không gồm upload và LLM; trích xuất đã cache) |
| LLM lập kế hoạch (staging, qwen3.8:27b) | 2–3 s khi model đã nạp; 19 s lần đầu |
| OCR thật | Ảnh scan rõ: 8/8 trường đúng (vẫn NEEDS_REVIEW). Ảnh mờ Gaussian σ=3,5: không nhận diện, không bịa |

**Giới hạn của các con số:** golden dataset do nhóm phát triển tự tạo từ dữ liệu hư cấu, nên 100% chỉ chứng minh hệ thống đúng
trên các tình huống đã thiết kế, **không** phải độ chính xác trên chứng từ thật. Cần đo lại với bộ chứng từ thật đã ẩn danh.

## Kiểm thử giao diện thật (staging 127.0.0.1:5055, Edge headless qua DevTools Protocol, LLM thật)
- Kịch bản A hoá đơn (7 file gồm ZIP, PDF, XML injection, exe giả PDF): hoàn thành, báo cáo xác minh đạt, mở bằng chứng PDF/XML.
- Kịch bản B đối soát: kết quả khớp golden (EXACT 1, VERIFIED 4, POTENTIAL 2, AMBIGUOUS 1, CONFLICTED 1, chênh lệch −677.000).
- Kịch bản C trên màn hình 390×844 (mobile): hoàn thành, panel báo cáo toàn màn hình.
- 0 lỗi console JavaScript ở cả 3 lượt. Hai lỗi phát hiện qua staging đã sửa và có test hồi quy:
  lọc theo chiều mua/bán khi tổ chức chưa có MST trả rỗng âm thầm; ZIP trùng không gắn file con vào phiên mới.
