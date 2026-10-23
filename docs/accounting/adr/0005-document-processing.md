# ADR-0005 Xử lý tài liệu bằng thư viện có sẵn, ưu tiên nguồn có cấu trúc

- **XML hoá đơn điện tử** (HDon/DLHDon): nguồn chính xác nhất; lxml với `resolve_entities=False, no_network=True, load_dtd=False`.
  Số đọc theo xs:decimal, không áp quy tắc dấu chấm/phẩy kiểu VN. Mỗi giá trị ghi XPath.
- **PDF có lớp chữ**: PyMuPDF, trích theo nhãn VN/EN; toạ độ tìm bằng `search_for` để tô vùng bằng chứng. Không trích dòng hàng.
- **PDF scan / ảnh**: EasyOCR local (vi+en) qua hàng đợi GPU của Hub. Kết quả luôn `NEEDS_REVIEW`.
- **Excel/CSV/TSV/DOCX/JSON**: openpyxl (không chạy macro), csv sniffer, python-docx. Nhận diện bảng theo từ đồng nghĩa tiêu đề;
  chiều tiền Nợ/Có chỉ suy ra khi biết là sao kê hay sổ, nếu không ⇒ NEEDS_REVIEW.
- **Không hỗ trợ (trả lỗi có cấu trúc)**: .xls/.doc nhị phân, Office có mật khẩu, PDF có mật khẩu, file thực thi.
- Docling/MinerU để dành làm adapter khi gặp PDF bảng biểu phức tạp (thêm model, tài nguyên GPU).
