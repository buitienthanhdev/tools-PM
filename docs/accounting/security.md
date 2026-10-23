# Bảo mật & quản trị

## Xác thực và phân quyền
- Đăng nhập dùng hệ thống Hub (scrypt, cookie HttpOnly/SameSite=Lax/Secure, khoá sau 5 lần sai). Kiểm tra Origin cho request ghi (CSRF).
- Vào module cần quyền công cụ `accounting` do admin Hub cấp (không tự cấp khi `auto_approve`).
- Trong module: vai trò theo tổ chức — ADMIN, ACCOUNTANT, REVIEWER, APPROVER, AUDITOR, VIEWER (`security.PERMS`). Quyền quyết định ở máy chủ.
- Phân tách nhiệm vụ: người phê duyệt ghi sổ / quy tắc hạch toán phải khác người tạo và người yêu cầu (`allow_self_approval=false`).
- Chưa có: MFA, SSO doanh nghiệp.

## Cô lập tenant
Mỗi tổ chức một **file database riêng** (`data/accounting/tenants/<org_id>.db`); không gian cá nhân = một người dùng.
Danh bạ trung tâm chỉ chứa tổ chức và thành viên. Trigger trong mỗi database chặn dòng thuộc tổ chức khác. Route `/o/<org>/...`
kiểm tra thành viên trước rồi mới mở database của tổ chức; không phải thành viên ⇒ 404. Lịch sử chat (phiên, tin nhắn,
tác vụ, báo cáo) chỉ người tạo xem được. Kho file theo thư mục tổ chức. Xem ADR-0006.

## Chứng từ
Nhận diện theo chữ ký (không tin đuôi file); chặn file thực thi; Defender quét (không tự xoá để giữ bằng chứng); ZIP: chặn path traversal,
symlink, file mã hoá, zip bomb (tỉ lệ nén, tổng dung lượng, đọc có giới hạn), độ sâu lồng 2. XML: không resolve entity, không mạng.
XLSM: không chạy macro. Bản gốc lưu theo SHA-256, chỉ-đọc, trigger chặn xoá/sửa danh tính; kiểm tra hash trước khi xử lý và khi tải báo cáo.

## Prompt injection
Bốn nguồn được tách: chỉ dẫn hệ thống (planner), ý định người dùng (câu lệnh), đầu ra công cụ (tin cậy), nội dung tài liệu (không tin cậy).
Nội dung tài liệu không vào prompt; tên file được làm sạch và bọc trong khối dữ liệu không tin cậy. Kế hoạch bị lọc: chỉ công cụ đã đăng ký,
tham số đúng schema, lớp tác vụ được vai trò cho phép; `request_posting` chỉ khi câu lệnh người dùng chứa “ghi sổ”; không có công cụ
hành động bên ngoài (thanh toán, nộp thuế, gửi dữ liệu). Kiểm thử: `test_prompt_injection_has_no_effect`, `test_planner_output_is_policed`.

## Dữ liệu và AI
Mặc định chỉ dùng AI chạy trên máy chủ (Ollama). `cloud_ai_allowed=false`. AI không nhận nội dung chứng từ.

## Nhật ký kiểm toán
`audit_events` chỉ-thêm, nối chuỗi SHA-256; trigger chặn UPDATE/DELETE; `audit.verify()` phát hiện sửa đổi ngoài ứng dụng (test có).
Ghi: upload, từ chối, trích xuất (parser, phiên bản, model), kế hoạch (nguồn, model), từng lần gọi công cụ (tham số đã làm sạch),
artifact (hash), tải xuống, đề xuất/sửa/yêu cầu/duyệt/từ chối/ghi sổ/đảo bút toán, khoá kỳ, đổi thành viên, quyết định kiểm duyệt.
Khoá có tên chứa password/token/secret/api_key/cookie được thay bằng `[redacted]`. Chưa có chính sách xoá theo thời hạn (retention).

## Giới hạn & chống lạm dụng
Kích thước file, số file/lần, số trang PDF, số dòng sheet, ZIP (cấu hình `accounting.*`). Rate limit theo người dùng: upload 240/phút,
gửi lệnh 30/phút, tạo tổ chức 10/phút (bộ nhớ trong tiến trình).
