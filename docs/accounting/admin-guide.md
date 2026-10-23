# Hướng dẫn quản trị

**Bật module:** `data/config.json` → `"accounting": {"enabled": true}`; khởi động lại Hub.

**Cấp quyền:** trang `/admin` của Hub → tick “Kế toán AI” cho tài khoản. Người dùng mới có một tổ chức cá nhân (họ là ADMIN,
ACCOUNTANT, REVIEWER, APPROVER). Để làm việc nhóm: trong module → Cài đặt → thêm email + vai trò. Người phê duyệt ghi sổ phải là người khác.

**Cấu hình (`accounting` trong config.json):** `max_file_mb` (50), `max_files_per_upload` (500), `max_pdf_pages` (300), `max_zip_members`,
`max_zip_total_mb`, `max_zip_ratio`, `max_zip_depth`, `max_sheet_rows`, `antivirus` (auto|defender|off), `ocr` (auto|easyocr|off),
`llm_planner` (true), `planner_model` (trống = models.genreport), `workers` (1), `task_timeout_s`, `step_max_attempts`, `lease_s`,
`date_tolerance_days` (3), `allow_self_approval` (false), `cloud_ai_allowed` (false), `data_dir`.

**Worker riêng (tuỳ chọn):** `python -m modules.accounting.jobs` — tác vụ được nhận qua DB, nhiều worker an toàn nhờ lease.

**Sao lưu / kiểm tra:** `python -m modules.accounting.backup create <đích>`; `... verify <bản sao>`.
**Kiểm tra nhật ký:** module → Nhật ký kiểm toán → “Kiểm tra toàn vẹn”.
**Đo chất lượng:** `python -m modules.accounting.golden.evaluate`.

**Sự cố:** tác vụ treo → worker khác tự nhận lại khi hết lease (120 s); AI lập kế hoạch lỗi liên tục → tự chuyển sang lập kế hoạch theo
quy tắc trong 5 phút; Ollama tắt → hệ thống vẫn chạy bằng quy tắc.
