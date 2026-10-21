"""Lập danh mục nghị định / thông tư / văn bản hợp nhất từ sitemap luatvietnam.vn (robots.txt cho phép trang văn bản).
Chỉ đọc sitemap công khai, 1 yêu cầu / 1,2 giây. Ghi data/legal_crawl/lvn_index.json."""
import json
import re
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (PMToolsHub legal-research)"}
OUT = Path(__file__).resolve().parent.parent / "data" / "legal_crawl" / "lvn_index.json"


def main():
    s = requests.Session()
    s.headers.update(UA)
    idx = s.get("https://luatvietnam.vn/sitemap.xml", timeout=60).text
    maps = [m for m in re.findall(r"<loc>([^<]+)</loc>", idx) if "sitemap_document" in m]
    print(len(maps), "sitemap văn bản", flush=True)
    keep = []
    for m in maps:
        time.sleep(1.2)
        try:
            xml = s.get(m, timeout=90).text
        except Exception as e:
            print("lỗi", m, e)
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            slug = u.rsplit("/", 1)[-1]
            if re.match(r"(nghi-dinh|thong-tu|van-ban-hop-nhat|luat|bo-luat|nghi-quyet-\d+-\d{4}-(qh|ubtvqh))", slug):
                keep.append(u)
        print(m.rsplit("/", 1)[-1], len(keep), flush=True)
    OUT.write_text(json.dumps(sorted(set(keep)), ensure_ascii=False, indent=0), encoding="utf-8")
    print("đã lưu", len(set(keep)))


if __name__ == "__main__":
    main()
