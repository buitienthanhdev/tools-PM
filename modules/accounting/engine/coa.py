"""
Danh mục tài khoản khởi tạo cho tổ chức mới.

TT 99/2025/TT-BTC (hiệu lực 01/01/2026, thay TT 200/2014) quy định hệ thống tài khoản tại Phụ lục II.
Phụ lục II không có trong kho pháp luật local, nên danh mục dưới đây là tập tài khoản thông dụng
đánh dấu UNVERIFIED_APPENDIX_II: phải được kế toán trưởng đối chiếu trước khi dùng cho báo cáo pháp định.
"""

DEFAULT_REGIME = "TT99_2025"
VERIFICATION = "UNVERIFIED_APPENDIX_II"

# (mã, tên, loại, số dư thông thường, mã cha)
ACCOUNTS = [
    ("111", "Tiền mặt", "asset", "D", None),
    ("1111", "Tiền Việt Nam", "asset", "D", "111"),
    ("1112", "Ngoại tệ", "asset", "D", "111"),
    ("112", "Tiền gửi ngân hàng", "asset", "D", None),
    ("1121", "Tiền Việt Nam", "asset", "D", "112"),
    ("1122", "Ngoại tệ", "asset", "D", "112"),
    ("131", "Phải thu của khách hàng", "asset", "DC", None),
    ("133", "Thuế GTGT được khấu trừ", "asset", "D", None),
    ("1331", "Thuế GTGT được khấu trừ của hàng hoá, dịch vụ", "asset", "D", "133"),
    ("1332", "Thuế GTGT được khấu trừ của TSCĐ", "asset", "D", "133"),
    ("141", "Tạm ứng", "asset", "D", None),
    ("152", "Nguyên liệu, vật liệu", "asset", "D", None),
    ("153", "Công cụ, dụng cụ", "asset", "D", None),
    ("154", "Chi phí sản xuất, kinh doanh dở dang", "asset", "D", None),
    ("155", "Thành phẩm", "asset", "D", None),
    ("156", "Hàng hoá", "asset", "D", None),
    ("211", "Tài sản cố định hữu hình", "asset", "D", None),
    ("214", "Hao mòn tài sản cố định", "contra_asset", "C", None),
    ("242", "Chi phí trả trước", "asset", "D", None),
    ("331", "Phải trả cho người bán", "liability", "DC", None),
    ("333", "Thuế và các khoản phải nộp Nhà nước", "liability", "C", None),
    ("3331", "Thuế giá trị gia tăng phải nộp", "liability", "C", "333"),
    ("33311", "Thuế GTGT đầu ra", "liability", "C", "3331"),
    ("3334", "Thuế thu nhập doanh nghiệp", "liability", "C", "333"),
    ("3335", "Thuế thu nhập cá nhân", "liability", "C", "333"),
    ("334", "Phải trả người lao động", "liability", "C", None),
    ("338", "Phải trả, phải nộp khác", "liability", "C", None),
    ("341", "Vay và nợ thuê tài chính", "liability", "C", None),
    ("411", "Vốn đầu tư của chủ sở hữu", "equity", "C", None),
    ("421", "Lợi nhuận sau thuế chưa phân phối", "equity", "DC", None),
    ("511", "Doanh thu bán hàng và cung cấp dịch vụ", "revenue", "C", None),
    ("515", "Doanh thu hoạt động tài chính", "revenue", "C", None),
    ("521", "Các khoản giảm trừ doanh thu", "contra_revenue", "D", None),
    ("632", "Giá vốn hàng bán", "expense", "D", None),
    ("635", "Chi phí tài chính", "expense", "D", None),
    ("641", "Chi phí bán hàng", "expense", "D", None),
    ("642", "Chi phí quản lý doanh nghiệp", "expense", "D", None),
    ("711", "Thu nhập khác", "revenue", "C", None),
    ("811", "Chi phí khác", "expense", "D", None),
    ("821", "Chi phí thuế thu nhập doanh nghiệp", "expense", "D", None),
    ("911", "Xác định kết quả kinh doanh", "closing", "DC", None),
]

_PARENTS = {a[4] for a in ACCOUNTS if a[4]}


def seed(c, org_id, regime=DEFAULT_REGIME):
    for code, name, typ, side, parent in ACCOUNTS:
        c.execute(
            """INSERT OR IGNORE INTO accounts
               (org_id, code, name, acct_type, normal_side, parent_code, postable, regime, verification)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (org_id, code, name, typ, side, parent, 0 if code in _PARENTS else 1, regime, VERIFICATION),
        )
