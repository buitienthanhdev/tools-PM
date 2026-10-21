import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "legal_crawl"
KW = ("doanh-nghiep|dau-tu|dang-ky-kinh-doanh|dang-ky-doanh-nghiep|thue|hoa-don|ke-toan|lao-dong|bao-hiem-xa-hoi|bao-hiem-y-te|bao-hiem-that-nghiep|tien-luong|"
      "xu-phat-vi-pham-hanh-chinh|thuong-mai|canh-tranh|chung-khoan|trai-phieu|ngan-hang|tin-dung|hai-quan|xuat-khau|nhap-khau|dat-dai|nha-o|bat-dong-san|xay-dung|"
      "dau-thau|pha-san|so-huu-tri-tue|hop-tac-xa|thuong-mai-dien-tu|giao-dich-dien-tu|du-lieu-ca-nhan|an-toan-ve-sinh|moi-truong|tieu-dung|nguoi-tieu-dung|"
      "quan-ly-gia|chuyen-doi-so|ho-kinh-doanh|khoi-nghiep|doanh-nghiep-nho-va-vua|hop-dong|chuyen-gia|nguoi-nuoc-ngoai|giay-phep|dieu-kien-kinh-doanh|phi-le-phi")
EXCL = ("quoc-phong|phong-chay|duong-bo|duong-sat|hang-khong|chuc-nang-nhiem-vu|co-cau-to-chuc|mien-thi-thuc|xi-mang|covid|y-te-du-phong|"
        "gao|det-may|khung-gia-phat-dien|han-ngach|hiep-dinh|quy-tac-xuat-xu|thuoc|duoc|thuc-pham|giong|thuy-san|lam-nghiep|co-so-du-lieu|van-ban-quy-pham|"
        "luu-tru-ho-so|bo-xay-dung|bien-gioi|hanh-chinh-ve-an-ninh|thu-tuc-hanh-chinh-linh-vuc")
TT_CORE = "thue|hoa-don|ke-toan|lao-dong|bao-hiem-xa-hoi|bao-hiem-that-nghiep|dang-ky-doanh-nghiep|dang-ky-kinh-doanh|chung-khoan|tien-luong|ho-kinh-doanh"


def main():
    u = json.loads((ROOT / "lvn_index.json").read_text(encoding="utf-8"))
    sel = []
    for x in u:
        slug = x.rsplit("/", 1)[-1]
        m = re.match(r"(nghi-dinh|thong-tu)-(?:lien-tich-)?[\w\-]*?-?(\d{4})-(nd-cp|tt-btc|tt-bkhdt|tt-bldtbxh|tt-nhnn|tt-bct|tt-btp|tt-bcong-thuong|tt-bnnptnt|tt-btnmt|tt-bxd|tt-bytx?|tt-btttt)-", slug)
        if not m:
            continue
        y = int(m.group(2))
        if y < 2020 or not re.search(KW, slug) or re.search(EXCL, slug):
            continue
        if m.group(1) == "thong-tu" and not re.search(TT_CORE, slug):
            continue
        sel.append((y, x))
    sel.sort(reverse=True)
    return sel
if __name__ == "__main__":
    s = main()
    print(len(s))
    from collections import Counter
    print(Counter(y for y, _ in s))
    for y, x in s[:60]:
        print(y, x.rsplit("/", 1)[-1][:110])


EXCL_BROAD = ("quoc-phong|phong-chay|duong-bo|duong-sat|hang-khong|chuc-nang-nhiem-vu|co-cau-to-chuc|mien-thi-thuc|covid|bien-gioi|quan-su|cong-an|an-ninh|"
              "cong-chuc|vien-chuc|dan-toc|ton-giao|nguoi-co-cong|liet-si|thi-dua|khen-thuong|giao-duc|hoc-sinh|sinh-vien|benh-vien|kham-chua|duoc|thuoc|vac-xin|"
              "hang-hai|tau-bien|thuyen-vien|ho-tich|quoc-tich|bau-cu|ngoai-giao|dieu-uoc|thanh-tra|khieu-nai|to-cao|hinh-su|ma-tuy|mai-dam|cai-nghien|thi-hanh-an|"
              "luat-su|cong-chung|giam-dinh|bao-chi|xuat-ban|dien-anh|the-thao|di-san|ton-tao")
TT_KW = ("thue|hoa-don|ke-toan|lao-dong|bao-hiem|dang-ky|chung-khoan|tien-luong|doanh-nghiep|dau-tu|thuong-mai|hai-quan|ngan-hang|tin-dung|gia|phi-le-phi|"
         "dau-thau|bat-dong-san|nha-o|dat-dai|ngoai-hoi|bao-lanh|trai-phieu|tai-chinh")


def broad():
    """Mọi nghị định Chính phủ từ 2019 (trừ lĩnh vực không liên quan kinh tế) + thông tư các bộ kinh tế có từ khóa kinh doanh."""
    u = json.loads((ROOT / "lvn_index.json").read_text(encoding="utf-8"))
    out = []
    for x in u:
        slug = x.rsplit("/", 1)[-1]
        if re.search(EXCL_BROAD, slug):
            continue
        m = re.search(r"-(2019|202\d)-nd-cp-", slug) if slug.startswith("nghi-dinh-") else None
        if not m and slug.startswith("thong-tu"):
            m = re.search(r"-(2019|202\d)-tt-(btc|bkhdt|bldtbxh|nhnn|bct|btp)-", slug)
            if m and not re.search(TT_KW, slug):
                m = None
        if m:
            out.append((int(m.group(1)), x))
    out.sort(reverse=True)
    return out
