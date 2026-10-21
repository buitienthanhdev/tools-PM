"""Đổi văn bản bảng mã TCVN3 (ABC, font .Vn*) sang Unicode. Dùng cho các file .doc/.rtf đời cũ."""
_PAIRS = (
    "A1Ă A2Â A3Ê A4Ô A5Ơ A6Ư A7Đ A8ă A9â AAê ABô ACơ ADư AEđ "
    "B5à B6ả B7ã B8á B9ạ BBằ BCẳ BDẵ BEắ C6ặ C7ầ C8ẩ C9ẫ CAấ CBậ "
    "CCè CEẻ CFẽ D0é D1ẹ D2ề D3ể D4ễ D5ế D6ệ D7ì D8ỉ DCĩ DDí DEị "
    "DFò E1ỏ E2õ E3ó E4ọ E5ồ E6ổ E7ỗ E8ố E9ộ EAờ EBở ECỡ EDớ EEợ "
    "EFù F1ủ F2ũ F3ú F4ụ F5ừ F6ử F7ữ F8ứ F9ự FAỳ FBỷ FCỹ FDý FEỵ"
).split()
TABLE = {chr(int(p[:2], 16)): p[2:] for p in _PAIRS}
TABLE["\xad"] = "ư"  # dấu gạch nối mềm: Word đổi 0xAD


def tcvn3_to_unicode(text: str) -> str:
    return "".join(TABLE.get(c, c) for c in text)
