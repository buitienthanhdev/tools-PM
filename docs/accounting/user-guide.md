# Hướng dẫn sử dụng Kế toán AI

1. Mở **sonxit.io.vn/accounting**, đăng nhập. Lần đầu: **Cài đặt** → nhập mã số thuế doanh nghiệp (để phân biệt hoá đơn mua vào / bán ra).
2. **Kéo thả** chứng từ vào khung làm việc: hoá đơn XML/PDF/ảnh, sao kê, sổ quỹ, Excel, CSV, ZIP. File lạ/độc hại bị từ chối kèm lý do;
   file trùng được dùng lại bản cũ.
3. **Gõ yêu cầu** bằng tiếng Việt và nhấn Enter. Ví dụ:
   - “Kiểm tra tất cả hoá đơn, phát hiện trùng lặp, tổng hợp theo nhà cung cấp và xuất Excel”
   - “Đối soát sao kê với sổ tiền gửi, tìm khoản chưa khớp”
   - “Lọc các hoá đơn trên 20 triệu” · “Kiểm tra file Excel có công thức sai không”
   - “So sánh thu chi theo tháng, tạo dashboard Excel” · “Lập bảng công nợ và tuổi nợ”
   - “Tự động định khoản các hoá đơn” (chỉ tạo đề xuất, không ghi sổ)
4. **Theo dõi** từng bước AI làm; bấm một bước để xem chi tiết. “Hoàn thành một phần” nghĩa là còn câu hỏi hoặc dữ liệu thiếu — đọc dòng ❓.
5. **Mở báo cáo** ở panel phải: xem từng sheet; cột *Nguồn* (S1, S2…) mở chứng từ gốc; bấm dòng hoá đơn để xem từng giá trị và vị trí
   trong chứng từ (vùng tô cam trên PDF, XPath trên XML). Tải **XLSX/PDF**.
6. **Sửa báo cáo** bằng câu tiếp theo trong cùng phiên: “thêm biểu đồ 6 tháng”, “sắp xếp theo doanh thu giảm dần”,
   “tách chi phí marketing thành sheet riêng”. Mỗi lần sửa tạo phiên bản mới, bản cũ giữ nguyên.
7. **Kiểm duyệt**: xử lý các điểm hệ thống không tự kết luận (hoá đơn mâu thuẫn, đối soát mơ hồ, nghi trùng, hoá đơn cần chọn tài khoản).
8. **Ghi sổ**: Sổ sách → “Gửi yêu cầu ghi sổ”; người có vai trò Phê duyệt (khác bạn) duyệt ở mục Phê duyệt. Sai thì tạo bút toán đảo.

Hệ thống không tự thanh toán, không nộp tờ khai thuế, không gửi dữ liệu ra ngoài. Kết quả từ ảnh/scan luôn cần kiểm duyệt.
