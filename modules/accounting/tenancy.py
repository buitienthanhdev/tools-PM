"""
Database riêng cho từng tổ chức (không gian cá nhân = một người dùng).

- create_tenant(): tạo file database, chép dòng orgs (bản sao từ danh bạ trung tâm), dựng trigger bảo vệ.
- split_legacy(): bố cục cũ (mọi tổ chức chung một file) → mỗi tổ chức một file. Chạy một lần khi khởi động.
  Bản database chung cũ được SAO LƯU vào <data_dir>/legacy/ trước khi danh bạ trung tâm được dựng lại,
  không xoá dữ liệu nào.
"""

import os
import sqlite3
import time

from . import db, settings

SKIP = {"schema_migrations", "sqlite_sequence", "meta", "org_members"}
BUSINESS = ("files", "conversations", "tasks", "journal_entries", "audit_events", "artifacts", "review_items")


def create_tenant(org_row):
    """Tạo (nếu chưa có) database của tổ chức và bản sao dòng orgs trong đó."""
    with db.use_org(org_row["id"]):
        c = db.conn()
        if not c.execute("SELECT 1 FROM orgs WHERE id=?", (org_row["id"],)).fetchone():
            with db.tx() as t:
                db.insert(t, "orgs", dict(org_row))


def _tables(c):
    return [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid") if r[0] not in SKIP]


def _copy_org(src_path, org_id):
    """Chép mọi dòng của org_id từ database chung sang database riêng (chỉ khi database riêng còn trống)."""
    with db.use_org(org_id):
        c = db.conn()
        if c.execute("SELECT count(*) FROM orgs").fetchone()[0]:
            return False
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("ATTACH DATABASE ? AS src", (src_path,))
        try:
            c.execute("BEGIN IMMEDIATE")
            for t in _tables(c):
                cols = [r[1] for r in c.execute(f"PRAGMA main.table_info({t})")]
                src_cols = {r[1] for r in c.execute(f"PRAGMA src.table_info({t})")}
                cols = [x for x in cols if x in src_cols]
                if not cols:
                    continue
                key = "id" if t == "orgs" else "org_id" if "org_id" in cols else None
                if not key:
                    continue
                q = ",".join(cols)
                c.execute(f"INSERT INTO main.{t} ({q}) SELECT {q} FROM src.{t} WHERE {key}=?", (org_id,))
            last = c.execute("SELECT max(seq) FROM main.audit_events").fetchone()[0]
            if last:
                c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('audit_imported_through_seq', ?)", (str(last),))
            c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('imported_from_shared_db', ?)", (str(time.time()),))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.execute("DETACH DATABASE src")
            c.execute("PRAGMA foreign_keys=ON")
    return True


def split_legacy():
    """Trả về danh sách org_id đã tách (rỗng nếu bố cục đã là database riêng)."""
    central = db.central_path()
    if not os.path.exists(central):
        return []
    with db.central():
        c = db.conn()
        if c.execute("SELECT 1 FROM meta WHERE key='tenant_split'").fetchone():
            return []
        has_data = any(c.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() for t in BUSINESS)
        orgs = [dict(r) for r in c.execute("SELECT * FROM orgs")]
        members = [dict(r) for r in c.execute("SELECT * FROM org_members")]
        if not has_data:
            with db.tx() as t:
                t.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('tenant_split', ?)", (str(time.time()),))
            for o in orgs:
                create_tenant(o)
            return []
        # 1. Sao lưu nguyên vẹn database chung trước mọi thay đổi
        legacy_dir = os.path.join(settings.data_dir(), "legacy")
        os.makedirs(legacy_dir, exist_ok=True)
        legacy = os.path.join(legacy_dir, time.strftime("aaap-shared-%Y%m%d-%H%M%S.db"))
        with sqlite3.connect(legacy) as out:
            c.backup(out)
    # 2. Chép dữ liệu từng tổ chức sang database riêng, kiểm tra số dòng
    split = []
    src = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
    for o in orgs:
        _copy_org(legacy, o["id"])
        with db.use_org(o["id"]):
            for t in BUSINESS:
                want = src.execute(f"SELECT count(*) FROM {t} WHERE org_id=?", (o["id"],)).fetchone()[0]
                got = db.one(f"SELECT count(*) n FROM {t} WHERE org_id=?", (o["id"],))["n"]
                if want != got:
                    raise RuntimeError(f"Tách dữ liệu {o['id']} lỗi ở bảng {t}: {got}/{want} dòng")
        split.append(o["id"])
    src.close()
    # 3. Dựng lại danh bạ trung tâm chỉ gồm tổ chức + thành viên
    db.close_all()
    tmp = central + ".new"
    for x in (tmp, tmp + "-wal", tmp + "-shm"):
        if os.path.exists(x):
            os.remove(x)
    n = sqlite3.connect(tmp, isolation_level=None)
    n.row_factory = sqlite3.Row
    db.migrate(n)
    n.execute("BEGIN")
    for o in orgs:
        n.execute(f"INSERT INTO orgs ({','.join(o)}) VALUES ({','.join('?' for _ in o)})", tuple(o.values()))
    for m in members:
        n.execute(f"INSERT INTO org_members ({','.join(m)}) VALUES ({','.join('?' for _ in m)})", tuple(m.values()))
    n.execute("INSERT INTO meta (key, value) VALUES ('tenant_split', ?)", (str(time.time()),))
    n.execute("INSERT INTO meta (key, value) VALUES ('legacy_backup', ?)", (os.path.basename(legacy),))
    n.execute("COMMIT")
    n.close()
    os.replace(tmp, central)
    for x in (central + "-wal", central + "-shm"):
        if os.path.exists(x):
            os.remove(x)
    print(f"[accounting] Đã tách {len(split)} tổ chức sang database riêng; bản cũ: {legacy}")
    return split


def all_org_ids():
    with db.central():
        return [r["id"] for r in db.all_("SELECT id FROM orgs ORDER BY created_at")]
