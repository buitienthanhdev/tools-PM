# ADR-0004 Không thực thi mã/lệnh do AI sinh

**Bối cảnh.** Đặc tả cho phép Python sandbox với cô lập mạnh. Máy chủ Windows, không Docker/gVisor/Firecracker; tiến trình Hub chạy cùng
dữ liệu kế toán, secret phiên và GPU dùng chung. Đặc tả cũng nói không coi Docker mặc định là ranh giới bảo mật.

**Quyết định.** Không có công cụ chạy shell hay mã tuỳ ý. Mọi khả năng là hàm Python đã viết sẵn, có schema tham số, kiểm thử.
Biến đổi báo cáo theo hội thoại dùng tập thao tác có kiểm soát (`reports/spec.apply_ops`); biểu thức cột tính qua AST chỉ cho phép + − × ÷.

**Hệ quả.** An toàn hơn và kiểm toán được; đổi lại kém linh hoạt với yêu cầu lạ. Nếu sau này cần sandbox: tiến trình riêng, user riêng,
không mạng, Job Object giới hạn CPU/RAM, thư mục làm việc tạm — hoặc VM Linux; ghi ADR mới trước khi bật.
