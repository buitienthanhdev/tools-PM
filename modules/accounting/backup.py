"""
Sao lưu và kiểm chứng khôi phục dữ liệu kế toán.

    python -m modules.accounting.backup create <thư mục đích>
    python -m modules.accounting.backup verify <thư mục bản sao lưu>

create: SQLite online backup API (nhất quán khi đang chạy) cho danh bạ trung tâm và database riêng của
        từng tổ chức + sao chép bản gốc/artifact + manifest SHA-256.
verify: PRAGMA integrity_check, chuỗi nhật ký kiểm toán, đối chiếu hash từng file trong manifest và với DB.
"""

import hashlib
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

from . import db, settings, tenancy


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def create(dest):
    src_dir = Path(settings.data_dir())
    out = Path(dest) / time.strftime("aaap-%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    dbs = {"aaap.db": None}
    for org in tenancy.all_org_ids():
        if db.tenant_exists(org):
            dbs[f"tenants/{org}.db"] = org
    (out / "tenants").mkdir()
    for rel, org in dbs.items():
        with (db.use_org(org) if org else db.central()), sqlite3.connect(out / rel) as target:
            db.conn().backup(target)
    files = {}
    for sub in ("objects", "artifacts"):
        if (src_dir / sub).exists():
            for p in (src_dir / sub).rglob("*"):
                if p.is_file() and p.suffix != ".tmp":
                    rel = p.relative_to(src_dir).as_posix()
                    (out / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, out / rel)
                    files[rel] = _sha(out / rel)
    manifest = {"created_at": time.time(), "databases": {rel: _sha(out / rel) for rel in dbs}, "files": files}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out


def verify(path):
    path = Path(path)
    problems = []
    manifest = json.loads((path / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel, h in manifest["files"].items():
        if not (path / rel).exists() or _sha(path / rel) != h:
            problems.append(f"file hỏng/thiếu: {rel}")
    events = 0
    for rel, h in manifest["databases"].items():
        if not (path / rel).exists() or _sha(path / rel) != h:
            problems.append(f"{rel} khác hash trong manifest")
            continue
        n, more = _verify_db(path, rel)
        events += n
        problems += more
    return {"ok": not problems, "problems": problems[:50], "files": len(manifest["files"]),
            "databases": len(manifest["databases"]), "audit_events": events}


def _verify_db(path, rel):
    problems = []
    con = sqlite3.connect(f"file:{path / rel}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        problems.append(f"{rel}: integrity_check thất bại")
    for table, label in (("files", "bản gốc"), ("artifacts", "artifact")):
        for r in con.execute(f"SELECT storage_path, sha256 FROM {table}"):
            fp = Path(r["storage_path"]).as_posix()
            if not (path / fp).exists() or _sha(path / fp) != r["sha256"]:
                problems.append(f"{label} không khớp {rel}: {fp}")
    from .audit import GENESIS, _digest

    m = con.execute("SELECT value FROM meta WHERE key='audit_imported_through_seq'").fetchone()
    imported = int(m[0]) if m else 0
    prev, n = GENESIS, 0
    for r in con.execute("SELECT * FROM audit_events ORDER BY seq"):
        r = dict(r)
        n += 1
        bad = _digest(r["prev_hash"], r) != r["hash"] if r["seq"] <= imported else (r["prev_hash"] != prev or _digest(prev, r) != r["hash"])
        if bad:
            problems.append(f"{rel}: chuỗi nhật ký đứt tại seq {r['seq']}")
            break
        prev = r["hash"]
    con.close()
    return n, problems


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, arg = sys.argv[1], sys.argv[2]
    print(create(arg) if cmd == "create" else json.dumps(verify(arg), ensure_ascii=False, indent=1))
