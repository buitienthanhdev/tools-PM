"""
API dashboard quản trị (chỉ admin — core.auth._guard chặn /api/admin/*) và beacon theo dõi từ trình duyệt (/api/track/*).
Mọi số liệu đọc từ core.analytics (SQLite riêng); không đọc dữ liệu nghiệp vụ của các công cụ.
"""

import csv
import io
import json
import os
import shutil
import subprocess
import time

from flask import Blueprint, Response, jsonify, request

from core import analytics as A
from core import auth, config, gpu
from core import jobs as hubjobs

bp = Blueprint("admin_analytics", __name__)
RANGES = {"1h": 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400, "90d": 90 * 86400}
PROC_START = time.time()


def _range():
    r = request.args.get("range", "24h")
    span = RANGES.get(r, 86400)
    now = time.time()
    return r, now - span, now, span


def _q(sql, args=()):
    try:
        return A.query(sql, args)
    except Exception as e:  # DB chưa có (chưa có lượt truy cập nào)
        if "unable to open" in str(e) or "no such table" in str(e):
            return []
        raise


def _one(sql, args=()):
    r = _q(sql, args)
    return r[0] if r else {}


def _p95(sql, args):
    vals = [r["ms"] for r in _q(sql, args)]
    if not vals:
        return None
    vals.sort()
    return round(vals[min(len(vals) - 1, int(0.95 * len(vals)))], 1)


# ── Beacon công khai ─────────────────────────────────────────
@bp.route("/api/track/<kind>", methods=["POST"])
def track(kind):
    if kind not in ("pv", "leave", "err", "ping"):
        return "", 404
    if not A.rate_ok():
        return "", 429
    try:
        d = json.loads(request.get_data(cache=False, as_text=True)[:8000] or "{}")  # sendBeacon gửi text/plain
    except ValueError:
        return "", 400
    if not isinstance(d, dict):
        return "", 400
    if kind == "ping":
        user = A._user_email()
        vid = A._clean(d.get("vid"), 40)
        A._touch_live(f"u:{user}" if user else f"v:{vid}", user=user, path=A._clean(d.get("path"), 300), vid=vid)
    else:
        A.beacon(kind, d)
    return "", 204


# ── Tổng quan ────────────────────────────────────────────────
def _kpis(t0, t1):
    pv = _one("SELECT count(*) n, count(DISTINCT vid) v, avg(dur) d FROM pageviews WHERE ts>=? AND ts<? AND device!='bot'", (t0, t1))
    rq = _one("""SELECT count(*) n, sum(status>=500) e5, sum(status>=400 AND status<500) e4, count(DISTINCT ip) ips,
                 sum(method!='GET' AND module NOT IN ('auth','admin','other','page')) actions
                 FROM requests WHERE ts>=? AND ts<? AND device!='bot'""", (t0, t1))
    users = _one("""SELECT count(*) n FROM (SELECT user FROM requests WHERE ts>=? AND ts<? AND user IS NOT NULL
                    UNION SELECT user FROM pageviews WHERE ts>=? AND ts<? AND user IS NOT NULL)""", (t0, t1, t0, t1))
    ev = {r["kind"]: r["n"] for r in _q("SELECT kind, count(*) n FROM events WHERE ts>=? AND ts<? GROUP BY kind", (t0, t1))}
    errs = _one("SELECT count(*) n FROM errors WHERE ts>=? AND ts<?", (t0, t1))
    bots = _one("SELECT count(*) n FROM requests WHERE ts>=? AND ts<? AND device='bot'", (t0, t1))
    return {
        "visitors": pv.get("v") or 0, "pageviews": pv.get("n") or 0, "avg_duration_s": round(pv["d"], 1) if pv.get("d") else None,
        "users": users.get("n") or 0, "requests": rq.get("n") or 0, "actions": rq.get("actions") or 0,
        "errors_5xx": rq.get("e5") or 0, "errors_4xx": rq.get("e4") or 0, "unique_ips": rq.get("ips") or 0,
        "error_rate": round((rq.get("e5") or 0) / rq["n"], 4) if rq.get("n") else 0,
        "p95_ms": _p95("SELECT ms FROM requests WHERE ts>=? AND ts<? AND device!='bot'", (t0, t1)),
        "logins": ev.get("login_ok", 0), "login_fails": ev.get("login_fail", 0), "registrations": ev.get("register", 0),
        "app_errors": errs.get("n") or 0, "bot_requests": bots.get("n") or 0,
    }


@bp.route("/api/admin/analytics/overview")
def overview():
    r, t0, t1, span = _range()
    cur, prev = _kpis(t0, t1), _kpis(t0 - span, t0)
    hourly = span <= 2 * 86400
    if span <= 3600:
        fmt, step = "%H:%M", 300
    elif hourly:
        fmt, step = "%d/%m %H:00", 3600
    else:
        fmt, step = "%d/%m", 86400
    # Mốc thời gian theo giờ địa phương của máy chủ
    def bucket(ts):
        lt = time.localtime(ts)
        if step == 300:
            return time.strftime("%H:", lt) + f"{lt.tm_min // 5 * 5:02d}"
        return time.strftime(fmt, lt)

    keys = []
    t = t0
    while t <= t1:
        k = bucket(t)
        if not keys or keys[-1] != k:
            keys.append(k)
        t += step
    series = {k: {"t": k, "pageviews": 0, "visitors": set(), "requests": 0, "e4": 0, "e5": 0} for k in keys}
    for row in _q("SELECT ts, vid FROM pageviews WHERE ts>=? AND ts<? AND device!='bot'", (t0, t1)):
        s = series.get(bucket(row["ts"]))
        if s:
            s["pageviews"] += 1
            s["visitors"].add(row["vid"])
    for row in _q("SELECT ts, status FROM requests WHERE ts>=? AND ts<? AND device!='bot'", (t0, t1)):
        s = series.get(bucket(row["ts"]))
        if s:
            s["requests"] += 1
            s["e4"] += 400 <= row["status"] < 500
            s["e5"] += row["status"] >= 500
    out = [{**v, "visitors": len(v["visitors"])} for v in series.values()]
    return jsonify({"range": r, "kpis": cur, "previous": prev, "series": out, "online": len(A.live()),
                    "generated_at": time.time()})


@bp.route("/api/admin/analytics/live")
def live():
    rows = A.live()
    users = {e: u for e, u in auth._read()["users"].items()}
    for x in rows:
        if x.get("user") in users:
            x["name"] = users[x["user"]].get("name")
        x["ago_s"] = round(time.time() - x["ts"])
    recent = _q("SELECT ts, user, path, ip, country, browser, device FROM pageviews ORDER BY id DESC LIMIT 30")
    return jsonify({"online": rows, "recent_pageviews": recent})


@bp.route("/api/admin/analytics/top")
def top():
    r, t0, t1, _ = _range()
    a = (t0, t1)
    pages = _q("""SELECT path, count(*) views, count(DISTINCT vid) visitors, avg(dur) avg_dur FROM pageviews
                  WHERE ts>=? AND ts<? AND device!='bot' GROUP BY path ORDER BY views DESC LIMIT 30""", a)
    modules = _q("""SELECT module, count(*) requests, sum(method!='GET') actions, count(DISTINCT user) users,
                    sum(status>=500) e5, sum(status>=400 AND status<500) e4, avg(ms) avg_ms FROM requests
                    WHERE ts>=? AND ts<? AND device!='bot' GROUP BY module ORDER BY actions DESC, requests DESC""", a)
    users = _q("""SELECT user, count(*) requests, sum(method!='GET') actions, sum(status>=400) errors,
                  count(DISTINCT ip) ips, max(ts) last_seen, group_concat(DISTINCT module) modules FROM requests
                  WHERE ts>=? AND ts<? AND user IS NOT NULL GROUP BY user ORDER BY requests DESC LIMIT 100""", a)
    pv_users = {x["user"]: x for x in _q("""SELECT user, count(*) pageviews, sum(dur) time_s FROM pageviews
                                             WHERE ts>=? AND ts<? AND user IS NOT NULL GROUP BY user""", a)}
    for u in users:
        u.update({k: v for k, v in pv_users.pop(u["user"], {}).items() if k != "user"})
    users += [{"user": k, **{x: v for x, v in p.items() if x != "user"}, "requests": 0, "actions": 0} for k, p in pv_users.items()]

    def dim(col):
        bot = "" if col == "device" else "AND device!='bot'"  # thiết bị: vẫn hiện số bot để biết tỉ lệ
        return _q(f"""SELECT coalesce({col}, '(không rõ)') k, count(DISTINCT vid) visitors, count(*) views FROM pageviews
                      WHERE ts>=? AND ts<? {bot} GROUP BY k ORDER BY visitors DESC LIMIT 15""", a)

    endpoints = _q("""SELECT method, route, module, count(*) n, avg(ms) avg_ms, max(ms) max_ms, sum(status>=500) e5,
                      sum(status>=400 AND status<500) e4 FROM requests WHERE ts>=? AND ts<? GROUP BY method, route
                      ORDER BY n DESC LIMIT 60""", a)
    slow = _q("""SELECT method, route, avg(ms) avg_ms, max(ms) max_ms, count(*) n FROM requests WHERE ts>=? AND ts<?
                 GROUP BY method, route HAVING n >= 3 ORDER BY avg_ms DESC LIMIT 15""", a)
    return jsonify({"range": r, "pages": pages, "modules": modules, "users": users, "countries": dim("country"),
                    "browsers": dim("browser"), "os": dim("os"), "devices": dim("device"), "referrers": dim("ref"),
                    "screens": dim("screen"), "endpoints": endpoints, "slow": slow})


@bp.route("/api/admin/analytics/security")
def security():
    r, t0, t1, _ = _range()
    a = (t0, t1)
    fails_ip = _q("""SELECT ip, country, count(*) n, count(DISTINCT json_extract(detail,'$.email')) emails, max(ts) last
                     FROM events WHERE kind='login_fail' AND ts>=? AND ts<? GROUP BY ip ORDER BY n DESC LIMIT 30""", a)
    fails_email = _q("""SELECT json_extract(detail,'$.email') email, count(*) n, count(DISTINCT ip) ips, max(ts) last
                        FROM events WHERE kind='login_fail' AND ts>=? AND ts<? GROUP BY email ORDER BY n DESC LIMIT 30""", a)
    denied = _q("""SELECT ip, country, status, count(*) n, group_concat(DISTINCT route) routes, max(ts) last FROM requests
                   WHERE status IN (401,403,429) AND ts>=? AND ts<? GROUP BY ip, status ORDER BY n DESC LIMIT 30""", a)
    scans = _q("""SELECT ip, country, browser, count(*) n, group_concat(DISTINCT path) paths, max(ts) last FROM requests
                  WHERE (status=404 OR module='scan') AND ts>=? AND ts<? GROUP BY ip ORDER BY n DESC LIMIT 30""", a)
    bots = _q("""SELECT browser, ip, count(*) n, max(ts) last FROM requests WHERE device='bot' AND ts>=? AND ts<?
                 GROUP BY browser, ip ORDER BY n DESC LIMIT 30""", a)
    admin_ev = _q("""SELECT ts, kind, user, actor, ip, country, detail FROM events WHERE ts>=? AND ts<?
                     AND kind NOT IN ('login_ok') ORDER BY ts DESC LIMIT 200""", a)
    new_ips = _q("""SELECT user, ip, country, min(ts) first FROM requests WHERE user IS NOT NULL AND ts>=? AND ts<?
                    GROUP BY user, ip HAVING first >= ? ORDER BY first DESC LIMIT 50""", (t1 - 90 * 86400, t1, t0))
    return jsonify({"range": r, "login_fail_by_ip": fails_ip, "login_fail_by_email": fails_email, "denied": denied,
                    "scans_404": scans, "bots": bots, "events": admin_ev, "new_user_ips": new_ips})


@bp.route("/api/admin/analytics/errors")
def errors():
    r, t0, t1, _ = _range()
    groups = _q("""SELECT source, kind, message, where_, count(*) n, count(DISTINCT user) users, max(ts) last, min(ts) first,
                   group_concat(DISTINCT path) paths, max(id) sample_id FROM errors WHERE ts>=? AND ts<?
                   GROUP BY source, kind, where_, substr(message,1,120) ORDER BY last DESC LIMIT 100""", (t0, t1))
    samples = {x["id"]: x for x in _q(f"SELECT id, stack, user, ip, browser FROM errors WHERE id IN ({','.join('?' for _ in groups) or 0})",
                                      tuple(g["sample_id"] for g in groups))} if groups else {}
    for g in groups:
        g["sample"] = samples.get(g["sample_id"])
    http5 = _q("""SELECT method, route, status, count(*) n, max(ts) last, group_concat(DISTINCT error) errors FROM requests
                  WHERE status>=500 AND ts>=? AND ts<? GROUP BY method, route, status ORDER BY n DESC LIMIT 50""", (t0, t1))
    return jsonify({"range": r, "groups": groups, "http_5xx": http5})


LOG_TABLES = {
    "requests": ("SELECT id, ts, method, path, module, status, ms, bytes, user, ip, country, browser, os, device, ref, error "
                 "FROM requests", ("user", "ip", "path", "module", "browser", "country")),
    "pageviews": ("SELECT id, ts, path, title, user, vid, ip, country, browser, os, device, screen, ref, dur FROM pageviews",
                  ("user", "ip", "path", "vid", "browser", "country")),
    "events": ("SELECT id, ts, kind, user, actor, ip, country, detail FROM events", ("user", "actor", "ip", "kind", "detail")),
    "errors": ("SELECT id, ts, source, kind, message, where_, path, user, ip, browser FROM errors",
               ("user", "ip", "path", "message", "kind")),
}


def _log_rows(limit_max=1000):
    kind = request.args.get("kind", "requests")
    if kind not in LOG_TABLES:
        kind = "requests"
    base, cols = LOG_TABLES[kind]
    r, t0, t1, _ = _range()
    where, args = ["ts>=?", "ts<?"], [t0, t1]
    qtxt = (request.args.get("q") or "").strip()
    if qtxt:
        where.append("(" + " OR ".join(f"{c} LIKE ?" for c in cols) + ")")
        args += [f"%{qtxt}%"] * len(cols)
    if request.args.get("user"):
        where.append("user=?")
        args.append(request.args["user"])
    if request.args.get("ip"):
        where.append("ip=?")
        args.append(request.args["ip"])
    st = request.args.get("status")
    if kind == "requests" and st in ("2xx", "3xx", "4xx", "5xx"):
        lo = int(st[0]) * 100
        where.append("status>=? AND status<?")
        args += [lo, lo + 100]
    if request.args.get("before"):
        where.append("id<?")
        args.append(int(request.args["before"]))
    limit = max(1, min(int(request.args.get("limit") or 200), limit_max))
    rows = _q(f"{base} WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT {limit}", tuple(args))
    return kind, r, rows


@bp.route("/api/admin/analytics/log")
def log():
    kind, r, rows = _log_rows()
    return jsonify({"kind": kind, "range": r, "rows": rows, "next_before": rows[-1]["id"] if rows else None})


@bp.route("/api/admin/analytics/export.csv")
def export_csv():
    kind, r, rows = _log_rows(limit_max=100000)
    buf = io.StringIO()
    buf.write("﻿")  # Excel mở đúng tiếng Việt
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            row["ts"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["ts"]))
            w.writerow(row)
    A.event("admin_export", table=kind, range=r, rows=len(rows))
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=tracking_{kind}_{r}.csv"})


@bp.route("/api/admin/analytics/user")
def user_detail():
    email = auth._norm_email(request.args.get("email"))
    r, t0, t1, _ = _range()
    a = (email, t0, t1)
    u = auth._read()["users"].get(email)
    profile = auth._public(email, u) if u else {"email": email, "deleted": True}
    stats = _one("""SELECT count(*) requests, sum(method!='GET') actions, sum(status>=400) errors, count(DISTINCT ip) ips,
                    min(ts) first, max(ts) last, avg(ms) avg_ms FROM requests WHERE user=? AND ts>=? AND ts<?""", a)
    pv = _one("SELECT count(*) pageviews, sum(dur) time_s, count(DISTINCT vid) devices FROM pageviews WHERE user=? AND ts>=? AND ts<?", a)
    tools = _q("""SELECT module, count(*) requests, sum(method!='GET') actions, max(ts) last FROM requests
                  WHERE user=? AND ts>=? AND ts<? GROUP BY module ORDER BY actions DESC, requests DESC""", a)
    places = _q("""SELECT ip, country, browser, os, device, count(*) n, min(ts) first, max(ts) last FROM requests
                   WHERE user=? AND ts>=? AND ts<? GROUP BY ip, browser, os ORDER BY last DESC LIMIT 30""", a)
    timeline = []
    for x in _q("SELECT ts, path, title, dur, ip, browser, device FROM pageviews WHERE user=? AND ts>=? AND ts<? ORDER BY ts DESC LIMIT 400", a):
        timeline.append({"ts": x["ts"], "type": "page", "what": x["path"], "info": (f"ở lại {round(x['dur'])}s" if x["dur"] else ""),
                         "ip": x["ip"], "device": f"{x['browser']} · {x['device']}"})
    for x in _q("""SELECT ts, method, path, module, status, ms, ip, error FROM requests WHERE user=? AND ts>=? AND ts<?
                   AND (method!='GET' OR status>=400) ORDER BY ts DESC LIMIT 600""", a):
        timeline.append({"ts": x["ts"], "type": "action" if x["status"] < 400 else "fail", "what": f"{x['method']} {x['path']}",
                         "info": f"{x['status']} · {round(x['ms'])} ms" + (f" · {x['error']}" if x["error"] else ""),
                         "module": x["module"], "ip": x["ip"]})
    for x in _q("SELECT ts, kind, actor, ip, detail FROM events WHERE (user=? OR actor=?) AND ts>=? AND ts<? ORDER BY ts DESC LIMIT 200",
                (email, email, t0, t1)):
        timeline.append({"ts": x["ts"], "type": "event", "what": x["kind"], "info": x["detail"] or "", "ip": x["ip"],
                         "actor": x["actor"]})
    for x in _q("SELECT ts, source, kind, message, path FROM errors WHERE user=? AND ts>=? AND ts<? ORDER BY ts DESC LIMIT 100", a):
        timeline.append({"ts": x["ts"], "type": "error", "what": f"{x['source']}: {x['kind']}", "info": x["message"] or "",
                         "path": x["path"]})
    timeline.sort(key=lambda e: -e["ts"])
    return jsonify({"range": r, "profile": profile, "stats": {**stats, **pv}, "tools": tools, "places": places,
                    "timeline": timeline[:800]})


# ── Hệ thống ─────────────────────────────────────────────────
_gpu_cache = {"t": 0, "v": None}


def _gpu_info():
    if time.time() - _gpu_cache["t"] < 10:
        return _gpu_cache["v"]
    v = None
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip().splitlines()
            v = []
            for line in out:
                name, util, used, total, temp, power = [x.strip() for x in line.split(",")]
                v.append({"name": name, "util": float(util), "mem_used_mb": float(used), "mem_total_mb": float(total),
                          "temp_c": float(temp), "power_w": float(power) if power not in ("[N/A]", "") else None})
        except Exception as e:
            v = [{"error": f"{type(e).__name__}"}]
    _gpu_cache.update(t=time.time(), v=v)
    return v


def _dir_size(path, limit=200000):
    total, n = 0, 0
    for root, _, files in os.walk(path):
        for f in files:
            n += 1
            if n > limit:
                return total, True
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total, False


_size_cache = {"t": 0, "v": None}


@bp.route("/api/admin/analytics/system")
def system():
    import psutil

    vm = psutil.virtual_memory()
    disks = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            disks.append({"mount": p.mountpoint, "total": u.total, "used": u.used, "percent": u.percent})
        except (PermissionError, OSError):
            pass
    proc = psutil.Process()
    if time.time() - _size_cache["t"] > 300:
        sizes = {}
        for label, path in (("Dữ liệu Hub (data)", config.DATA_DIR), ("File tải lên (uploads)", config.UPLOAD_DIR)):
            sizes[label] = _dir_size(path)[0] if os.path.isdir(path) else 0
        _size_cache.update(t=time.time(), v=sizes)
    st = {}
    for j in list(hubjobs.jobs.values()):
        st[j.get("status", "?")] = st.get(j.get("status", "?"), 0) + 1
    net = psutil.net_io_counters()
    return jsonify({
        "cpu_percent": psutil.cpu_percent(interval=0.3), "cpu_count": psutil.cpu_count(),
        "load_per_cpu": psutil.cpu_percent(interval=None, percpu=True),
        "memory": {"total": vm.total, "used": vm.used, "percent": vm.percent},
        "disks": disks, "gpu": _gpu_info(), "gpu_queue": gpu.status(),
        "process": {"rss": proc.memory_info().rss, "threads": proc.num_threads(), "uptime_s": round(time.time() - PROC_START),
                    "pid": proc.pid},
        "boot_time": psutil.boot_time(), "net": {"sent": net.bytes_sent, "recv": net.bytes_recv},
        "jobs": st, "sizes": _size_cache["v"],
        "analytics": {"db_bytes": os.path.getsize(A.DB_PATH) if os.path.exists(A.DB_PATH) else 0, "queue": A._q.qsize(),
                      "dropped": A.dropped, "retention_days": (config.get().get("analytics") or {}).get("retention_days", 90)},
    })
