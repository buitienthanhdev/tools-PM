"""SQLite lưu bền cho Video Workspace: phiên tải lên theo phần, video, job (hàng đợi). WAL, một kết nối mỗi luồng."""

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

from . import settings

_local = threading.local()
_init_lock = threading.Lock()
_ready = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
  id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL, received INTEGER NOT NULL DEFAULT 0,
  path TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL, path TEXT NOT NULL,
  info_json TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, deleted_at REAL);
CREATE INDEX IF NOT EXISTS ix_videos_owner ON videos(owner, created_at);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, owner TEXT NOT NULL, video_id TEXT NOT NULL, config_json TEXT NOT NULL, models_json TEXT NOT NULL,
  preview INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, stage TEXT NOT NULL, message TEXT,
  frames_done INTEGER, frames_total INTEGER, progress REAL, eta_s REAL, fps REAL,
  attempts INTEGER NOT NULL DEFAULT 0, worker TEXT, pid INTEGER, lease_until REAL, cancel_requested INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, started_at REAL, finished_at REAL, expires_at REAL,
  error_code TEXT, error_message TEXT, output_path TEXT, output_size INTEGER, output_json TEXT, log_path TEXT,
  plan_json TEXT, deleted_at REAL);
CREATE INDEX IF NOT EXISTS ix_jobs_owner ON jobs(owner, created_at);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status, created_at);
"""

ACTIVE = ("queued", "running")
TERMINAL = ("completed", "failed", "cancelled")


def path():
    return os.path.join(settings.data_dir(), "video.db")


def conn():
    p = path()
    c = getattr(_local, "c", None)
    if c is None or getattr(_local, "p", None) != p:
        c = sqlite3.connect(p, timeout=30, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA foreign_keys=ON")
        with _init_lock:
            if p not in _ready:
                c.executescript(SCHEMA)
                _ready.add(p)
        _local.c, _local.p = c, p
    return c


@contextmanager
def tx():
    c = conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        raise


def one(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def all_(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def run(sql, args=()):
    return conn().execute(sql, args).rowcount


def new_id():
    return uuid.uuid4().hex


def now():
    return time.time()


def dumps(o):
    return json.dumps(o, ensure_ascii=False, default=str)


def loads(s, default=None):
    if not s:
        return default
    try:
        return json.loads(s)
    except ValueError:
        return default


def reset_for_tests():
    c = getattr(_local, "c", None)
    if c is not None:
        c.close()
    _local.c = None
    _ready.clear()
