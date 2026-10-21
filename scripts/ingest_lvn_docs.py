"""Nạp văn bản đã tải từ luatvietnam.vn (data/legal_crawl/lvn/*.json) vào kho luật."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
from modules.legal_rag import engine as e  # noqa: E402

ok = skip = 0
for f in sorted((ROOT / "data" / "legal_crawl" / "lvn").glob("*.json"), key=lambda p: -json.loads(p.read_text(encoding="utf-8"))["year"]):
    d = json.loads(f.read_text(encoding="utf-8"))
    try:
        doc = e.add_law(d["title"][:170], d["text"], save=False)
        ok += 1
    except Exception as ex:
        skip += 1
        print("bỏ qua", d["title"][:70], "|", ex, flush=True)
e.flush()
print("XONG", ok, "nạp,", skip, "bỏ qua; tổng", len(e._kb["docs"]), "văn bản,", sum(len(x["chunks"]) for x in e._kb["docs"]), "đoạn", flush=True)
