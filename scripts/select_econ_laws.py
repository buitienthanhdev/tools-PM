"""Chọn luật kinh tế - doanh nghiệp từ catalog (bản mới nhất + luật sửa đổi từ 2024) và tải file đính kèm."""
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent / "data" / "legal_crawl"
TOPICS = [
    "Doanh nghiệp", "Đầu tư", "Đầu tư công", "Đầu tư theo phương thức đối tác công tư", "Thương mại", "Cạnh tranh",
    "Kế toán", "Thống kê", "Quản lý thuế", "Thuế giá trị gia tăng", "Thuế thu nhập doanh nghiệp", "Thuế thu nhập cá nhân",
    "Thuế tiêu thụ đặc biệt", "Thuế xuất khẩu, thuế nhập khẩu", "Thuế tài nguyên", "Thuế bảo vệ môi trường", "Hải quan",
    "Phí và lệ phí", "Ngân sách nhà nước", "Quản lý nợ công", "Giá", "Bộ luật Lao động", "Việc làm",
    "An toàn, vệ sinh lao động", "Bảo hiểm xã hội", "Bảo hiểm y tế", "Công đoàn", "Sở hữu trí tuệ", "Phá sản", "Đấu thầu",
    "Đất đai", "Nhà ở", "Kinh doanh bất động sản", "Xây dựng", "Các tổ chức tín dụng", "Ngân hàng Nhà nước", "Chứng khoán",
    "Kinh doanh bảo hiểm", "Bảo vệ môi trường", "Bảo vệ quyền lợi người tiêu dùng", "Hợp tác xã", "Giao dịch điện tử",
    "An ninh mạng", "Bảo vệ dữ liệu cá nhân", "Dữ liệu", "Chuyển giao công nghệ", "Quảng cáo", "Điện lực", "Hóa chất",
    "Phòng, chống rửa tiền", "Trọng tài thương mại", "Hỗ trợ doanh nghiệp nhỏ và vừa", "Bộ luật Dân sự", "Bộ luật Hình sự",
    "Bộ luật Tố tụng dân sự", "Phòng, chống tham nhũng", "Quản lý, sử dụng tài sản công", "Chất lượng sản phẩm, hàng hóa",
    "Công nghiệp công nghệ số", "Khoa học, công nghệ và đổi mới sáng tạo", "Viễn thông",
]


def year(r):
    return int(r["date"][-4:] or 0)


def select(cat):
    chosen = {}
    for t in TOPICS:
        bare = t.replace("Bộ luật ", "")
        main = [r for r in cat if re.match(r"^(Bộ luật|Luật)\s+" + re.escape(bare) + r"\s*(năm\s*\d+)?\s*$", r["title"].strip(), re.I)
                or (t.startswith("Bộ luật") and r["title"].strip().lower().startswith(t.lower()) and "sửa đổi" not in r["title"].lower())]
        main.sort(key=year, reverse=True)
        if main:
            chosen[main[0]["docid"]] = main[0]
        for r in cat:
            if "sửa đổi" in r["title"].lower() and re.search(re.escape(bare), r["title"]) and year(r) >= 2024:
                chosen[r["docid"]] = r
    return list(chosen.values())


def main():
    cat = json.loads((ROOT / "catalog_3.json").read_text(encoding="utf-8"))
    sel = [r for r in select(cat) if r["files"]]
    (ROOT / "selected.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    print("đã chọn", len(sel), "văn bản")
    d = ROOT / "files"
    d.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (PMToolsHub legal-research)"
    for r in sel:
        r["local"] = []
        for u in r["files"]:
            ext = Path(u.split("?")[0]).suffix.lower() or ".bin"
            p = d / f"{r['docid']}_{len(r['local'])}{ext}"
            if not p.exists():
                time.sleep(1.2)
                resp = s.get(u, timeout=120)
                if resp.status_code != 200:
                    print("lỗi", resp.status_code, u)
                    continue
                p.write_bytes(resp.content)
            r["local"].append(p.name)
    (ROOT / "selected.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(Counter(Path(n).suffix for r in sel for n in r["local"]))


if __name__ == "__main__":
    sys.exit(main())
