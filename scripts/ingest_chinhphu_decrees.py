"""Tải PDF nghị định từ danh mục vanban.chinhphu.vn theo số hiệu và nạp vào kho luật.  python scripts/ingest_chinhphu_decrees.py 145/2020/NĐ-CP ..."""
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
from modules.legal_rag import engine as e  # noqa: E402

CR = ROOT / "data" / "legal_crawl"


def main(codes):
    cat = json.loads((CR / "catalog_4.json").read_text(encoding="utf-8"))
    for code in codes:
        r = next((x for x in cat if x["code"].strip() == code and x["files"]), None)
        if not r:
            print("không thấy", code)
            continue
        text = ""
        for u in [f for f in r["files"] if f.lower().endswith((".pdf", ".docx"))][:1]:
            time.sleep(1.2)
            resp = requests.get(u, headers={"User-Agent": "Mozilla/5.0 (PMToolsHub legal-research)"}, timeout=120)
            text += e.extract_text(u.rsplit("/", 1)[-1], resp.content)
        name = f"Nghị định {code} {r['title']}"[:170]
        try:
            d = e.add_law(name, text)
            print("OK", name[:80], len({c['article'] for c in d['chunks'] if c['article']}), "điều", flush=True)
        except Exception as ex:
            print("LỖI", name[:80], ex, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
