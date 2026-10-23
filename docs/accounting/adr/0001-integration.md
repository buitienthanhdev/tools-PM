# ADR-0001 Tích hợp vào Hub thay vì website/stack riêng

**Bối cảnh.** Đặc tả gợi ý Next.js + FastAPI + Postgres + Redis + Docker. Máy chủ thực tế: Flask/waitress trên Windows, không Docker,
không Postgres/Redis; SPA vanilla JS; tunnel trỏ một cổng 5000. Yêu cầu: chạy tại `/accounting`, kế thừa giao diện và xác thực.

**Quyết định.** Module Flask `modules/accounting` + module SPA `static/modules/accounting`, cùng tiến trình Hub.
Bật/tắt bằng `accounting.enabled` (mặc định **tắt**). Khi tắt: không có route, không worker, không hiện trong menu.
Quyền vào module = quyền công cụ `accounting` của Hub (không tự cấp khi đăng ký); quyền nghiệp vụ = vai trò trong tổ chức.

**Phương án đã cân nhắc.** (a) FastAPI riêng + reverse proxy: thêm tiến trình, thêm cấu hình tunnel, trùng hệ thống phiên — chưa cần.
(b) Next.js: thêm build toolchain vào dự án không có build step. Có thể tách worker ra tiến trình riêng (`python -m modules.accounting.jobs`) khi cần.

**Hệ quả.** Không cần thay đổi tunnel/DNS. Lỗi trong module có thể ảnh hưởng tiến trình Hub ⇒ worker bắt mọi exception; rollback = tắt cờ.
