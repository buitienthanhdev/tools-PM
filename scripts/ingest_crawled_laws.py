"""Nạp các luật đã tải (data/legal_crawl/selected.json) vào kho luật của module Pháp luật."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
from modules.legal_rag import engine as e  # noqa: E402

CR = ROOT / "data" / "legal_crawl"


def law_name(r):
    t = r["title"].strip()
    t = t[:1].upper() + (t[1:].lower() if t.isupper() else t[1:])
    code = r["code"].strip()
    return f"{t} ({code})" if code and code not in t else t


def main():
    sel = json.loads((CR / "selected.json").read_text(encoding="utf-8"))
    ok, bad = 0, []
    for n, r in enumerate(sel, 1):
        name = law_name(r)[:170]
        pdfs = [x for x in r["local"] if x.endswith(".pdf")]
        try:
            if pdfs:
                text = ""
                for f in pdfs:  # nhiều file thì ghép lại (phụ lục...)
                    text += "\n" + e.extract_text(f, (CR / "files" / f).read_bytes())
            else:
                f = r["local"][0]
                text = (CR / "txt" / (Path(f).stem + ".txt")).read_text(encoding="utf-8-sig", errors="ignore")
            doc = e.add_law(name, text)
            arts = len({c["article"] for c in doc["chunks"] if c["article"]})
            warn = "; ".join((doc.get("quality") or {}).get("warnings", []))
            print(f"[{n}/{len(sel)}] OK  {name[:70]} | {arts} điều, {len(doc['chunks'])} đoạn {('| ⚠ ' + warn) if warn else ''}", flush=True)
            ok += 1
        except Exception as ex:
            print(f"[{n}/{len(sel)}] LỖI {name[:70]} | {ex}", flush=True)
            bad.append((name, str(ex)))
    print("XONG", ok, "nạp được,", len(bad), "lỗi", flush=True)


if __name__ == "__main__":
    main()
