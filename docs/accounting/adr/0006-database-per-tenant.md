# ADR-0006 Mỗi tổ chức (người dùng) một file database; lịch sử chat riêng từng người

**Bối cảnh.** Yêu cầu: mỗi người dùng có hệ database riêng và lịch sử chat riêng. Trước đây mọi tổ chức dùng chung
`aaap.db`, cô lập bằng `org_id` trong từng truy vấn (cô lập logic).

**Quyết định.**
- `data/accounting/aaap.db` chỉ còn là **danh bạ trung tâm** (orgs, org_members).
- Mỗi tổ chức có **file database riêng** `data/accounting/tenants/<org_id>.db` (cùng schema). Không gian cá nhân tạo tự
  động cho mỗi người dùng ⇒ mỗi người một database. Ngữ cảnh chọn database bằng contextvar (`db.use_org`, `db.central`);
  API gắn ngữ cảnh sau khi kiểm tra thành viên; worker gắn theo tổ chức của task.
- Trong database của tổ chức, trigger `tenant_guard_*` chặn mọi dòng có `org_id` khác ⇒ lỗi nhầm ngữ cảnh gây lỗi ngay,
  không ghi lẫn. Truy vấn nhầm database chỉ trả rỗng (dữ liệu không tồn tại trong file đó).
- **Lịch sử chat riêng:** phiên làm việc, tin nhắn, tác vụ, báo cáo chỉ người tạo xem được (kể cả trong tổ chức dùng chung).
  Chứng từ, sổ sách, kiểm duyệt, phê duyệt vẫn dùng chung trong tổ chức vì là dữ liệu nghiệp vụ của nhóm.
- **Chuyển đổi:** khi khởi động, nếu `aaap.db` còn dữ liệu nghiệp vụ (bố cục cũ) thì sao lưu nguyên vẹn vào
  `legacy/aaap-shared-*.db`, chép dữ liệu từng tổ chức sang file riêng (đối chiếu số dòng), rồi dựng lại danh bạ trung tâm.
  Nhật ký kiểm toán chuyển sang được kiểm tra băm từng dòng (`meta.audit_imported_through_seq`), sau đó nối chuỗi đầy đủ.

**Hệ quả.** Sao lưu/khôi phục/xoá theo từng tổ chức dễ dàng; worker quét hàng đợi của từng database (phù hợp số tổ chức nhỏ–vừa).
File bản gốc chứng từ vẫn ở `objects/<org_id>/` (đã tách theo tổ chức từ trước). Bản `legacy/` chứa dữ liệu cũ — xoá thủ công
khi không còn cần.
