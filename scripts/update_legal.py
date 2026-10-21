"""Cập nhật kho luật định kỳ (chạy hằng tuần bằng Task Scheduler):
  1. luatvietnam.vn: đọc ~25 sitemap mới nhất, lấy nghị định / thông tư kinh tế chưa có, tải và nạp.
  2. vanban.chinhphu.vn: luật mới ban hành (loại 3) chưa có trong danh mục, tải PDF (OCR nếu là bản scan) và nạp.
  3. Đánh dấu văn bản bị thay thế / bãi bỏ, dựng lại chỉ mục vector.
  4. Khởi động lại server để nạp kho mới (watchdog tự bật lại).
Lịch sự với nguồn: 1 yêu cầu / 1,5 giây. Nhật ký: logs/update_legal.log"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("PYTHONUTF8", "1")
CR = ROOT / "data" / "legal_crawl"
UA = {"User-Agent": "Mozilla/5.0 (PMToolsHub legal-research)"}
SITEMAPS = 25


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def update_lvn(e):
    import crawl_luatvietnam_docs as cd
    import select_lvn

    s = requests.Session()
    s.headers.update(UA)
    idx_file = CR / "lvn_index.json"
    known = set(json.loads(idx_file.read_text(encoding="utf-8")))
    maps = [m for m in re.findall(r"<loc>([^<]+)</loc>", s.get("https://luatvietnam.vn/sitemap.xml", timeout=60).text) if "sitemap_document" in m][:SITEMAPS]
    fresh = []
    for m in maps:
        time.sleep(1.5)
        for u in re.findall(r"<loc>([^<]+)</loc>", s.get(m, timeout=90).text):
            if u not in known and re.match(r"(nghi-dinh|thong-tu)", u.rsplit("/", 1)[-1]):
                fresh.append(u)
    log("luatvietnam: văn bản mới trong sitemap:", len(fresh))
    idx_file.write_text(json.dumps(sorted(known | set(fresh)), ensure_ascii=False), encoding="utf-8")
    done_ids = {f.stem for f in (CR / "lvn").glob("*.json")}

    def did(u):
        m = re.search(r"-(\d+)-d\d+\.html", u)
        return m.group(1) if m else None

    wanted = [x for _, x in select_lvn.broad()]
    # văn bản mới trước, rồi phần tồn đọng chưa tải; mỗi lần tối đa 150, dừng ngay khi bị giới hạn tốc độ (429)
    todo = [u for u in wanted if u in set(fresh)] + [u for u in wanted if did(u) not in done_ids and u not in set(fresh)]
    added = 0
    for u in todo[:150]:
        try:
            time.sleep(3)
            r = s.get(u, timeout=90)
            if r.status_code == 429:
                log("  trang giới hạn tốc độ (429), dừng đợt này, tuần sau tải tiếp")
                break
            title, text = cd.parse(r.text)
            if len(text) < 800 or "Điều" not in text:
                continue
            (CR / "lvn" / f"{did(u)}.json").write_text(json.dumps({"url": u, "year": 0, "title": title, "text": text}, ensure_ascii=False), encoding="utf-8")
            e.add_law(title[:170], text, save=False)
            added += 1
        except Exception as ex:
            log("  bỏ qua", u.rsplit("/", 1)[-1][:60], "|", ex)
    e.flush()
    log("luatvietnam: đã nạp", added, "| còn tồn đọng", max(0, len(todo) - 150))


def update_laws(e):
    import crawl_chinhphu_laws as cl

    cat_file = CR / "catalog_3.json"
    old = {r["docid"] for r in json.loads(cat_file.read_text(encoding="utf-8"))}
    s = requests.Session()
    s.headers.update(UA)
    page = s.get(f"{cl.BASE}?classid=1&mode=1&typegroupid=3", timeout=60).text
    new = [r for r in cl.rows(page) if r["docid"] not in old]
    log("chinhphu: luật mới:", len(new))
    cat = json.loads(cat_file.read_text(encoding="utf-8"))
    for r in new:
        cat.append(r)
        pdf = next((f for f in r["files"] if f.lower().endswith((".pdf", ".docx"))), None)
        if not pdf:
            continue
        try:
            time.sleep(1.5)
            text = e.extract_text(pdf.rsplit("/", 1)[-1], s.get(pdf, timeout=120).content)
            name = f"{r['title']} ({r['code']})"[:170] if r["code"] else r["title"][:170]
            e.add_law(name, text)
            log("  nạp luật:", name[:80])
        except Exception as ex:
            log("  lỗi luật", r["title"][:60], "|", ex)
    cat_file.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    from modules.legal_rag import engine as e

    before = len(e._kb["docs"])
    for fn in (update_lvn, update_laws):
        try:
            fn(e)
        except Exception as ex:
            log("LỖI", fn.__name__, ex)
    log("đã đánh dấu", e.mark_superseded(), "văn bản bị thay thế")
    r = e.reindex()
    log(f"kho: {before} -> {len(e._kb['docs'])} văn bản; chỉ mục {r}")
    if len(e._kb["docs"]) != before:  # có thay đổi → server nạp lại kho
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | % { Stop-Process -Id $_.OwningProcess -Force }"], check=False)
        log("đã khởi động lại server")


if __name__ == "__main__":
    main()
