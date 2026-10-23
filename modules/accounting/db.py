"""
SQLite (WAL) cho module kế toán: kết nối theo luồng, migration có đánh số, giao dịch an toàn.

Máy chủ không có PostgreSQL (docs/accounting/adr/0002-database.md); schema giữ kiểu dữ liệu
chuyển được sang Postgres (TEXT/INTEGER/REAL, khoá ngoại, ràng buộc UNIQUE, CHECK).
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_local = threading.local()
_init_lock = threading.Lock()
_initialized = set()


def db_path():
    return os.path.join(settings.data_dir(), "aaap.db")


def new_id():
    return str(uuid.uuid4())


def now():
    return time.time()


def dumps(v):
    return json.dumps(v, ensure_ascii=False, default=str, sort_keys=True)


def loads(s, default=None):
    if s is None or s == "":
        return default
    return json.loads(s)


def _connect(path):
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at REAL)"
    )
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if f.stem in done:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for stmt in _split_sql(sql):
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations VALUES (?, ?)", (f.stem, time.time())
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def _split_sql(sql):
    """Tách câu lệnh; giữ nguyên khối CREATE TRIGGER ... BEGIN ... END;"""
    out, buf, in_trigger = [], [], False
    for line in sql.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        up = s.upper()
        if up.startswith("CREATE TRIGGER"):
            in_trigger = True
        if in_trigger:
            if up.endswith("END;"):
                out.append("\n".join(buf))
                buf, in_trigger = [], False
        elif s.endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out


def conn():
    """Kết nối riêng cho luồng hiện tại; tự migrate lần đầu với mỗi file DB."""
    path = db_path()
    c = getattr(_local, "conns", {}).get(path)
    if c is None:
        c = _connect(path)
        with _init_lock:
            if path not in _initialized:
                migrate(c)
                _initialized.add(path)
        _local.__dict__.setdefault("conns", {})[path] = c
    return c


@contextmanager
def tx():
    """Giao dịch ghi (BEGIN IMMEDIATE): tất cả hoặc không có gì. Lồng nhau dùng SAVEPOINT."""
    c = conn()
    if c.in_transaction:
        sp = f"sp_{uuid.uuid4().hex[:8]}"
        c.execute(f"SAVEPOINT {sp}")
        try:
            yield c
            c.execute(f"RELEASE {sp}")
        except Exception:
            c.execute(f"ROLLBACK TO {sp}")
            c.execute(f"RELEASE {sp}")
            raise
        return
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def one(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def all_(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def insert(c, table, row):
    cols = ",".join(row)
    q = ",".join("?" for _ in row)
    c.execute(f"INSERT INTO {table} ({cols}) VALUES ({q})", tuple(row.values()))
    return row


def reset_for_tests():
    """Đóng kết nối của luồng hiện tại (dùng khi test đổi thư mục dữ liệu)."""
    for c in getattr(_local, "conns", {}).values():
        try:
            c.close()
        except Exception:
            pass
    _local.conns = {}
