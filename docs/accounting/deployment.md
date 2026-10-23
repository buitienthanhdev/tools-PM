# Triển khai

## Trạng thái hiện tại
- Code nằm ở worktree `D:\tools PM\aaap-dev`, branch `feature/accounting` (tạo từ `edc5287`). **Chưa commit, chưa merge, chưa lên production.**
- Thư mục production `D:\tools PM\tools PM` **không bị thay đổi** (ngoài metadata git worktree).

## Staging (đã chạy)
```
set PM_DATA_DIR=<thư mục dữ liệu staging riêng>
set PM_ACCOUNTING=1
set PM_INSECURE_COOKIE=1            (chỉ vì staging dùng http://127.0.0.1)
set PM_ADMIN_EMAIL=... & set PM_ADMIN_PASSWORD=...
set PM_ALLOWED_ORIGINS=http://127.0.0.1:5055
python -c "import sys; sys.path.insert(0,'.'); from waitress import serve; import app; serve(app.app, listen='127.0.0.1:5055')"
```
Không mở ra Internet (không có ingress tunnel cho 5055).

## Đưa lên production — chỉ sau khi được phê duyệt
1. Sao lưu: lưu `git diff` của 2 file đang sửa dở trong thư mục production (`core/llm.py`, `modules/legal_rag/engine.py` —
   không phải của module này, cần chủ sở hữu quyết định trước khi merge) và sao lưu `data/` (users.json, config.json, secret.key).
2. Commit trên `feature/accounting`, review, merge vào branch production đang chạy.
3. Cài phụ thuộc (đã có sẵn trong venv: openpyxl, lxml): `pip install -r requirements.txt` — kiểm tra không nâng cấp gói khác.
4. Thêm vào `data/config.json`: `"accounting": {"enabled": true}` (giữ mặc định khác). Không cần sửa tunnel.
5. Khởi động lại theo README Hub: `kill_tools.ps1` rồi `start_tools.bat` (PowerShell quyền Administrator).
6. Kiểm tra: `/api/health` 200; `/api/auth/me` có `features.accounting=true`; admin cấp quyền “Kế toán AI” cho người dùng thử;
   chạy một tác vụ mẫu bằng `modules/accounting/golden`.
7. Lập lịch sao lưu: `python -m modules.accounting.backup create D:\backups\aaap` hằng ngày + `verify` hằng tuần.

## Rollback
- **Nhanh (không mất dữ liệu):** đặt `"accounting": {"enabled": false}` và khởi động lại Hub. Module biến mất (không route, không worker,
  không menu); dữ liệu `data/accounting/` giữ nguyên.
- **Hoàn toàn:** checkout lại commit trước merge, khởi động lại. Thay đổi ngoài module chỉ gồm: `app.py` (gắn module có điều kiện),
  `core/auth.py` (thêm công cụ `accounting`, không tự cấp; trả `features`), `static/js/main.js`, `static/stores/authStore.js`,
  `static/components/icons.js`, nhãn trong `adminModule.js`/`authModule.js`, `requirements.txt`.
- Không có migration phá huỷ dữ liệu Hub; DB kế toán là file riêng.
