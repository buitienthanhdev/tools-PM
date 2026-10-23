# Risk register

| # | Rủi ro | Mức | Biện pháp đã có | Còn lại |
| --- | --- | --- | --- | --- |
| R-01 | Sửa file trong thư mục production lên ngay (static phục vụ từ đĩa) | Cao | Phát triển trong worktree riêng; module tắt mặc định | Quy trình deploy phải theo deployment.md |
| R-02 | AI bịa số liệu / định khoản sai | Cao | AI chỉ chọn công cụ; mọi số do Decimal tính; định khoản chỉ theo quy tắc đã duyệt hoặc câu trả lời người dùng; ghi sổ cần người thứ hai | Quy tắc mẫu doanh thu 511 là giả định có điều kiện |
| R-03 | Prompt injection trong chứng từ | Cao | Nội dung chứng từ không vào prompt; policy theo câu lệnh người dùng; test với golden injection | File name vẫn vào prompt (đã làm sạch, đánh dấu không tin cậy) |
| R-04 | Lộ dữ liệu giữa tổ chức | Cao | org_id mọi bảng/truy vấn; 404 khi không phải thành viên; test cô lập API | Chưa có pentest độc lập |
| R-05 | OCR sai số | Trung bình | OCR luôn NEEDS_REVIEW; ảnh mờ không nhận diện thì không bịa | Chưa đo trên chứng từ thật |
| R-06 | Danh mục TK / quy tắc thuế chưa được chuyên gia xác nhận | Cao | Đánh dấu UNVERIFIED / NEEDS_EXPERT_REVIEW; 8% luôn kiểm duyệt | Cần kế toán trưởng duyệt |
| R-07 | SQLite một máy, mất dữ liệu | Trung bình | WAL + synchronous=FULL; backup + verify | Chưa lập lịch backup tự động |
| R-08 | Tranh chấp GPU với các công cụ khác | Trung bình | OCR/LLM qua hàng đợi GPU của Hub (cùng tiến trình) | Staging/tiến trình khác không được điều phối chung |
| R-09 | PyMuPDF là AGPL-3.0 (đã dùng trước ở Hub) | Trung bình | Ghi nhận | Cần ý kiến pháp lý hoặc thay pypdf (mất toạ độ bằng chứng) |
| R-10 | Không có engine tính lại công thức Excel | Thấp | Công thức kiểm tra cấu trúc + giá trị tính độc lập bằng Decimal, nói rõ trong báo cáo | Cài LibreOffice nếu cần tính lại thật |
| R-11 | Worker trong tiến trình web, tác vụ dài chiếm thread | Thấp | 1 worker mặc định, lease + khôi phục | Có thể tách tiến trình riêng |
| R-12 | Tài khoản Hub tự duyệt (auto_approve) | Trung bình | `accounting` là công cụ nhạy cảm, không tự cấp | — |
| R-13 | Defender không có/không quét | Thấp | Ghi NOT_SCANNED vào provenance; chặn exe theo chữ ký | — |
| R-14 | docling/PaddleOCR xung đột phiên bản với các công cụ khác của Hub | Trung bình | Venv riêng `venvs/docai`, gọi qua tiến trình con có timeout và khoá; lỗi → bộ đọc chính tiếp tục | Venv riêng phải được cập nhật thủ công |
| R-15 | docling/PaddleOCR chạy CPU chậm (hàng chục giây/trang), chiếm CPU | Thấp | Chỉ chạy khi bộ đọc chính thất bại; một tiến trình mỗi lúc; giới hạn `max_pdf_table_pages` | Có thể tắt bằng `paddle_ocr`/`docling` = off |
