"""Văn bản luật HƯ CẤU (không phải luật thật) để đo chất lượng truy xuất, không phụ thuộc dữ liệu thật."""

LAW_NAME = "Luật Thư viện Cộng đồng số 99/2026 (hư cấu, dùng để kiểm thử)"

LAW_TEXT = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Chương I
QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Luật này quy định về tổ chức, hoạt động của thư viện cộng đồng và quyền, nghĩa vụ của bạn đọc.
Điều 2. Giải thích từ ngữ
Trong Luật này, các từ ngữ dưới đây được hiểu như sau:
1. Bạn đọc là cá nhân đã được cấp thẻ thư viện.
2. Tài liệu là sách, báo, tạp chí và các ấn phẩm khác do thư viện quản lý.
3. Quá hạn là việc giữ tài liệu quá thời gian cho mượn quy định tại Luật này.
Chương II
THẺ THƯ VIỆN
Điều 3. Điều kiện cấp thẻ thư viện
1. Công dân từ đủ 6 tuổi trở lên được cấp thẻ thư viện khi xuất trình giấy tờ tuỳ thân.
2. Trẻ em dưới 6 tuổi chỉ được đọc tại chỗ dưới sự giám sát của người giám hộ.
3. Thẻ thư viện có giá trị trong 24 tháng kể từ ngày cấp.
Điều 4. Cấp lại thẻ thư viện
Bạn đọc làm mất thẻ phải báo ngay cho thư viện. Phí cấp lại thẻ là 20.000 đồng, thẻ mới được cấp trong thời hạn 3 ngày làm việc.
Chương III
MƯỢN VÀ TRẢ TÀI LIỆU
Điều 5. Thời hạn mượn tài liệu
1. Sách giáo khoa và sách tham khảo được mượn tối đa 21 ngày.
2. Tạp chí và báo được mượn tối đa 7 ngày.
3. Mỗi lần mượn không quá 5 tài liệu cùng lúc.
4. Bạn đọc được gia hạn một lần, mỗi lần 7 ngày, nếu tài liệu chưa có người đặt trước.
Điều 6. Xử lý trả tài liệu muộn
1. Bạn đọc trả tài liệu quá hạn bị phạt 2.000 đồng cho mỗi tài liệu mỗi ngày.
2. Tổng tiền phạt không vượt quá giá trị của tài liệu.
3. Quá hạn trên 30 ngày thì thẻ thư viện bị tạm khoá cho đến khi trả tài liệu và nộp phạt.
Điều 7. Làm mất hoặc làm hư hỏng tài liệu
1. Bạn đọc làm mất tài liệu phải mua tài liệu cùng loại để thay thế hoặc bồi thường bằng 3 lần giá bìa.
2. Tài liệu bị rách, ghi vẽ lên nội dung phải bồi thường theo mức độ hư hỏng nhưng không quá giá bìa.
Chương IV
GIỜ MỞ CỬA VÀ QUY TẮC SỬ DỤNG
Điều 8. Giờ mở cửa
Thư viện mở cửa từ 8 giờ đến 20 giờ các ngày trong tuần, trừ Chủ nhật và các ngày lễ theo quy định.
Điều 9. Quy tắc trong phòng đọc
1. Không hút thuốc, không ăn uống và không gây ồn ào trong phòng đọc.
2. Điện thoại phải để chế độ im lặng.
3. Bạn đọc vi phạm quy tắc lần đầu bị nhắc nhở, vi phạm lần thứ ba bị đình chỉ quyền sử dụng thư viện 30 ngày.
Điều 10. Quyền của bạn đọc
Bạn đọc có quyền sử dụng miễn phí các dịch vụ cơ bản của thư viện, được hướng dẫn tra cứu và được bảo mật thông tin cá nhân.
Chương V
TRÁCH NHIỆM QUẢN LÝ
Điều 11. Trách nhiệm của thủ thư
1. Thủ thư phải công khai nội quy, bảng giá phạt và giờ mở cửa tại nơi dễ thấy.
2. Thủ thư không được thu bất kỳ khoản phí nào ngoài mức quy định tại Luật này.
3. Thủ thư phải lập biên bản khi xử lý vi phạm và giao một bản cho bạn đọc.
Điều 12. Khiếu nại
Bạn đọc có quyền khiếu nại quyết định xử phạt trong thời hạn 15 ngày kể từ ngày nhận biên bản. Giám đốc thư viện giải quyết khiếu nại trong 10 ngày làm việc.
"""

# (câu hỏi diễn đạt khác hẳn văn bản luật, Điều đúng cần xuất hiện trong top-k)
QUERIES = [
    ("Tôi giữ cuốn sách muộn mấy hôm thì phải đóng bao nhiêu tiền?", "6"),
    ("Làm rơi mất thẻ đọc thì xin cái mới hết bao nhiêu và bao lâu có?", "4"),
    ("Em bé 5 tuổi có vào đọc sách được không?", "3"),
    ("Mượn báo được giữ trong bao nhiêu ngày?", "5"),
    ("Đánh mất quyển sách của thư viện thì đền thế nào?", "7"),
    ("Cuối tuần thư viện có làm việc không?", "8"),
    ("Hút thuốc trong phòng đọc bị xử lý ra sao?", "9"),
    ("Không đồng ý với quyết định phạt thì phải làm gì và trong bao lâu?", "12"),
    ("Thủ thư có được thu thêm tiền ngoài quy định không?", "11"),
    ("the doc het han bao lau", "3"),  # không dấu, diễn đạt ngắn
    ("gia han sach duoc may lan", "5"),  # không dấu
]

# Câu hỏi hoàn toàn ngoài phạm vi: phải bị coi là "chưa có căn cứ"
OFF_TOPIC = [
    "Cách nấu phở bò ngon cho 4 người?",
    "Giá vàng hôm nay là bao nhiêu?",
    "Thủ tục ly hôn đơn phương cần giấy tờ gì?",
]
