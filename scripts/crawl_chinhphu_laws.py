"""Lập danh mục Luật từ vanban.chinhphu.vn (Cổng TTĐT Chính phủ, robots.txt cho phép).
Chạy:  python scripts/crawl_chinhphu_laws.py [typegroupid]   (3 = Luật). Ghi data/legal_crawl/catalog_<type>.json.
Lịch sự: 1 yêu cầu / 1,5 giây, một luồng."""
import json
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

BASE = "https://vanban.chinhphu.vn/he-thong-van-ban"
UA = {"User-Agent": "Mozilla/5.0 (PMToolsHub legal-research; contact: admin)"}
OUT = Path(__file__).resolve().parent.parent / "data" / "legal_crawl"
OUT.mkdir(parents=True, exist_ok=True)


def hidden(html):
    """Mọi input trong form (ASP.NET WebForms cần gửi lại đủ cả ViewState lẫn các ô ẩn của điều khiển)."""
    out = {}
    for tag in re.findall(r"<input [^>]*>", html):
        name = re.search(r'name="([^"]+)"', tag)
        if not name or re.search(r'type="(submit|button|image|checkbox|radio)"', tag):
            continue
        val = re.search(r'value="([^"]*)"', tag)
        out[name.group(1)] = unescape(val.group(1)) if val else ""
    return out


def rows(html):
    out = []
    for tr in re.split(r"<tr>\s*<td>", html)[1:]:
        m = re.search(r"docid=(\d+)", tr)
        t = re.search(r'class="substract">\s*([^<]+?)\s*</span>', tr)
        if not (m and t):
            continue
        code = re.search(r'class="code">([^<]*)<', tr)
        date = re.search(r'class="issued-date">([^<]*)<', tr)
        files = re.findall(r'<div class="bl-doc-file"><a href="([^"]+)"', tr)
        out.append({"docid": m.group(1), "title": unescape(t.group(1)).strip(), "code": (code.group(1) if code else "").strip(),
                    "date": (date.group(1) if date else "").strip(), "files": files})
    return out


def main(tg="3"):
    s = requests.Session()
    s.headers.update(UA)
    url = f"{BASE}?classid=1&mode=1&typegroupid={tg}"
    html = s.get(url, timeout=60).text
    total = int(re.search(r"\|\s*(\d+)\s*<", html).group(1))
    pages = -(-total // 50)
    print("tổng", total, "văn bản,", pages, "trang", flush=True)
    items = rows(html)
    for p in range(2, pages + 1):
        time.sleep(1.5)
        data = hidden(html)
        data["__EVENTTARGET"], data["__EVENTARGUMENT"] = "ctrl_191017_163$grvDocument", f"Page${p}"
        r = s.post(url, data=data, timeout=60)
        r.raise_for_status()
        html = r.text
        got = rows(html)
        items += got
        print(f"trang {p}/{pages}: +{len(got)}", flush=True)
    seen, uniq = set(), []
    for it in items:
        if it["docid"] not in seen:
            seen.add(it["docid"])
            uniq.append(it)
    (OUT / f"catalog_{tg}.json").write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    print("đã lưu", len(uniq), "văn bản")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "3")
