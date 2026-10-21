"""Tải toàn văn nghị định / thông tư đã chọn từ luatvietnam.vn (robots.txt cho phép trang văn bản) và nạp vào kho luật.
1 yêu cầu / 1,5 giây, có thể chạy lại (bỏ qua file đã tải). Ghi data/legal_crawl/lvn/*.json."""
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from lxml import html as LH

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("PYTHONUTF8", "1")
import select_lvn  # noqa: E402

OUT = ROOT / "data" / "legal_crawl" / "lvn"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (PMToolsHub legal-research)"}
DELAY = 3.0


def DELAY_UP():
    global DELAY
    DELAY = min(DELAY * 1.5, 12.0)


END = re.compile(r"^\s*(Văn bản liên quan|VB liên quan|Tải về|Xem thêm|Nơi nhận\s*:|Bản dịch|Lược đồ)", re.I)


def parse(page):
    t = LH.fromstring(page)
    title = re.sub(r"\s+", " ", t.xpath("//h1")[0].text_content()).strip()
    for bad in t.xpath('//script|//style|//noscript|//svg|//*[contains(@class,"tooltip")]'):
        bad.getparent().remove(bad)
    arts = t.xpath("//article")
    body = max(arts, key=lambda a: len(a.text_content())).text_content()
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in body.split("\n")]
    lines = [ln for ln in lines if ln]
    start = next((i for i, ln in enumerate(lines) if re.match(r"^(CHÍNH PHỦ|BỘ TRƯỞNG|QUỐC HỘI|Căn cứ)", ln)), None)
    if start is None:
        start = next((i for i, ln in enumerate(lines) if ln.startswith("Điều 1")), 0)
    out = []
    for ln in lines[start:]:
        if END.match(ln):
            break
        out.append(ln)
    return title, "\n".join(out)


def main():
    sel = select_lvn.broad() if "--broad" in sys.argv else select_lvn.main()
    s = requests.Session()
    s.headers.update(UA)
    ok = bad = 0
    for n, (y, u) in enumerate(sel, 1):
        did = re.search(r"-(\d+)-d\d+\.html", u).group(1)
        f = OUT / f"{did}.json"
        if f.exists():
            continue
        try:
            time.sleep(DELAY)
            r = s.get(u, timeout=90)
            if r.status_code == 429:  # bị giới hạn tốc độ: nghỉ rồi thử lại một lần, và chậm dần
                DELAY_UP()
                time.sleep(60)
                r = s.get(u, timeout=90)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            title, text = parse(r.text)
            if len(text) < 800 or "Điều" not in text:
                raise RuntimeError(f"văn bản quá ngắn/không có Điều ({len(text)} ký tự)")
            f.write_text(json.dumps({"url": u, "year": y, "title": title, "text": text}, ensure_ascii=False), encoding="utf-8")
            ok += 1
            print(f"[{n}/{len(sel)}] OK {title[:80]} ({len(text)})", flush=True)
        except Exception as ex:
            bad += 1
            print(f"[{n}/{len(sel)}] LỖI {u.rsplit('/', 1)[-1][:70]} | {ex}", flush=True)
    print("XONG TẢI", ok, "tải được,", bad, "lỗi", flush=True)


if __name__ == "__main__":
    main()
