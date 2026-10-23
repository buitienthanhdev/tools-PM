"""
Đọc số tiền viết bằng chữ tiếng Việt → số nguyên, để đối chiếu với tổng tiền bằng số trên hoá đơn.

Chấp nhận các biến thể hay gặp: lăm/nhăm/năm, mốt/một, tư/bốn, bẩy/bảy, nghìn/ngàn, tỷ/tỉ, linh/lẻ,
dạng đầy đủ ("hai tỷ không trăm linh hai triệu…") lẫn rút gọn ("hai tỷ hai triệu…"),
và phần đuôi "đồng", "chẵn". Không đọc được → None (không đoán).
"""

from num2words import num2words

from ..extract.base import fold

DIGITS = {"khong": 0, "mot": 1, "hai": 2, "ba": 3, "bon": 4, "tu": 4, "nam": 5, "lam": 5, "nham": 5,
          "sau": 6, "bay": 7, "tam": 8, "chin": 9}
FILLER = {"linh", "le"}
SKIP = {"dong", "chan", "vnd", "viet", "so", "tien", "bang", "chu", "la", "tong", "cong", "thanh", "toan"}
SCALES = (("ty", 10**9), ("ti", 10**9), ("trieu", 10**6), ("nghin", 10**3), ("ngan", 10**3))


def _below_1000(tokens):
    total, pending, last = 0, None, None
    for t in tokens:
        if t in DIGITS:
            if pending is not None:
                return None  # hai chữ số liền nhau: không phải cách đọc hợp lệ
            pending = DIGITS[t]
        elif t == "muoi":
            if pending is not None and last in DIGITS:
                total += pending * 10  # "hai mươi"
            else:
                total += 10  # "mười"
            pending = None
        elif t == "tram":
            total += (pending if pending is not None else 1) * 100
            pending = None
        elif t in FILLER:
            pass
        else:
            return None
        last = t
    return total + (pending or 0)


def _parse(tokens):
    if not tokens:
        return 0
    for word, value in SCALES:
        if word in tokens:
            i = len(tokens) - 1 - tokens[::-1].index(word)  # tách tại lần xuất hiện cuối của bậc lớn nhất
            left, right = _parse(tokens[:i]), _parse(tokens[i + 1:])
            if left is None or right is None:
                return None
            return (left if tokens[:i] else 1) * value + right
    return _below_1000(tokens)


def words_to_int(text):
    """'Hai mươi bảy triệu năm trăm nghìn đồng chẵn' → 27500000; không đọc được → None."""
    if not text:
        return None
    tokens = [t for t in fold(text).split() if t not in SKIP]
    if not tokens or not any(t in DIGITS or t == "muoi" for t in tokens):
        return None
    return _parse(tokens)


def int_to_words(n):
    """Cách đọc chuẩn để hiển thị trong thông báo (num2words, tiếng Việt)."""
    return " ".join(num2words(int(n), lang="vi").split())  # num2words dùng khoảng trắng không ngắt
