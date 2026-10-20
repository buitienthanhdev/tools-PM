"""
PM Tools Hub — High Availability Watchdog Supervisor
Monitors server.py (http://127.0.0.1:5000/api/health) and cloudflared tunnel 24/7.
Automatically recovers from crashes, hangs, network drops, or process kills.
"""

import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Logging Configuration ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Watchdog")

PYTHON_EXE = str(BASE_DIR / ".venv" / "Scripts" / "python.exe")
if not os.path.exists(PYTHON_EXE):
    PYTHON_EXE = sys.executable

# Locate cloudflared.exe
CF_CMD = "cloudflared"
cf_candidates = [
    r"C:\cloudflared\cloudflared.exe",
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
]
for path in cf_candidates:
    if os.path.exists(path):
        CF_CMD = path
        break

CONFIG_FILE = str(BASE_DIR / "cloudflared-config.yml")
TUNNEL_ID = "f8c3bf93-35c2-43ae-86ce-8ad5f4ac25ce"
HEALTH_URL = "http://127.0.0.1:5000/api/health"
CHECK_INTERVAL = 5  # seconds
MAX_FAILURES = 3
STARTUP_TASK = "PM Tools Hub Watchdog"

# SpaceT (God's Eye View): vite preview on 4173, public gateway on 4174.
SPACET_DIR = BASE_DIR / "modules" / "spacet"
SPACET_APP_DIR = SPACET_DIR / "gods-eye-view"
SPACET_HEALTH_URL = "http://127.0.0.1:4174/"
SPACET_TUNNEL_CONFIG = str(SPACET_DIR / "cloudflared-spacet.yml")
SPACET_TUNNEL_ID = "5e661490-f1f6-4283-ada6-5a64194be715"
NODE_EXE = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"

server_proc = None
tunnel_proc = None
spacet_procs = []
spacet_tunnel_proc = None
fail_count = 0
spacet_fail_count = 0


def kill_port(port):
    """Kill any process occupying the given TCP port."""
    logger.warning(f"Clearing port {port}...")
    try:
        if sys.platform == "win32":
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
            subprocess.run(cmd, shell=True, capture_output=True)
    except Exception as e:
        logger.error(f"Error clearing port {port}: {e}")


def kill_port_5000():
    """Kill any process occupying port 5000."""
    kill_port(5000)


def is_cloudflared_running():
    """Check the tunnel process owned by this watchdog, not any cloudflared process."""
    return tunnel_proc is not None and tunnel_proc.poll() is None


def ensure_startup_task():
    """Start the hidden watchdog automatically after the user logs in to Windows."""
    if sys.platform != "win32":
        return

    vbs_script = str(BASE_DIR / "run_silent.vbs")
    wscript = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "wscript.exe")
    task_command = f'"{wscript}" "{vbs_script}"'
    result = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            STARTUP_TASK,
            "/SC",
            "ONLOGON",
            "/TR",
            task_command,
            "/RL",
            "LIMITED",
            "/F",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        logger.info("Startup task is installed: %s", STARTUP_TASK)
    else:
        run_key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
        fallback = subprocess.run(
            ["reg", "add", run_key, "/v", STARTUP_TASK, "/t", "REG_SZ", "/d", task_command, "/f"],
            capture_output=True,
            text=True,
            check=False,
        )
        if fallback.returncode == 0:
            logger.info("Startup registry entry is installed: %s", STARTUP_TASK)
        else:
            logger.warning(
                "Could not install startup task or registry entry: %s",
                fallback.stderr.strip() or result.stderr.strip(),
            )


def start_server():
    """Start server.py WSGI backend with redirected output."""
    global server_proc
    logger.info("Starting PM Tools WSGI Server (server.py)...")
    kill_port_5000()
    time.sleep(1)

    server_script = str(BASE_DIR / "server.py")
    server_log = open(LOG_DIR / "server.log", "a", encoding="utf-8")

    server_proc = subprocess.Popen(
        [PYTHON_EXE, server_script],
        cwd=str(BASE_DIR),
        stdout=server_log,
        stderr=server_log,
    )
    logger.info(f"Server started with PID: {server_proc.pid}")


def start_tunnel():
    """Start Cloudflare Tunnel with redirected output."""
    global tunnel_proc
    logger.info("Starting Cloudflare Tunnel...")

    tunnel_log = open(LOG_DIR / "tunnel.log", "a", encoding="utf-8")
    cmd = [
        CF_CMD,
        "--config",
        CONFIG_FILE,
        "tunnel",
        "--protocol",
        "http2",
        "run",
        TUNNEL_ID,
    ]

    tunnel_proc = subprocess.Popen(
        cmd, cwd=str(BASE_DIR), stdout=tunnel_log, stderr=tunnel_log
    )
    logger.info(f"Cloudflare Tunnel started with PID: {tunnel_proc.pid}")


def start_spacet():
    """Start SpaceT: the God's Eye View preview server and its public gateway."""
    global spacet_procs
    logger.info("Starting SpaceT (God's Eye View)...")
    for proc in spacet_procs:
        if proc.poll() is None:
            proc.terminate()
    spacet_procs = []
    kill_port(4173)
    kill_port(4174)
    time.sleep(1)

    if not (SPACET_APP_DIR / "dist" / "index.html").exists():
        logger.error("SpaceT build missing: run 'npm run build' in %s", SPACET_APP_DIR)
        return

    spacet_log = open(LOG_DIR / "spacet.log", "a", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    commands = [
        (
            [
                NODE_EXE,
                str(SPACET_APP_DIR / "node_modules" / "vite" / "bin" / "vite.js"),
                "preview",
                "--host",
                "127.0.0.1",
                "--port",
                "4173",
                "--strictPort",
            ],
            SPACET_APP_DIR,
        ),
        ([NODE_EXE, str(SPACET_DIR / "gateway.mjs")], SPACET_DIR),
    ]
    for cmd, cwd in commands:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=spacet_log,
            stderr=spacet_log,
            creationflags=flags,
        )
        spacet_procs.append(proc)
        logger.info(f"SpaceT process started with PID: {proc.pid}")


def start_spacet_tunnel():
    """Start the dedicated Cloudflare Tunnel for spacet.sonxit.io.vn."""
    global spacet_tunnel_proc
    logger.info("Starting SpaceT Cloudflare Tunnel...")
    tunnel_log = open(LOG_DIR / "spacet-tunnel.log", "a", encoding="utf-8")
    spacet_tunnel_proc = subprocess.Popen(
        [
            CF_CMD,
            "--config",
            SPACET_TUNNEL_CONFIG,
            "tunnel",
            "--protocol",
            "http2",
            "run",
            SPACET_TUNNEL_ID,
        ],
        cwd=str(BASE_DIR),
        stdout=tunnel_log,
        stderr=tunnel_log,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    logger.info(f"SpaceT Tunnel started with PID: {spacet_tunnel_proc.pid}")


def check_url(url):
    """Return True when the URL answers 200."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PMTools-Watchdog/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            return response.status == 200
    except Exception:
        return False


def check_health():
    """Ping local health endpoint."""
    return check_url(HEALTH_URL)


def check_spacet():
    """Ping the SpaceT gateway (answers 502 while the preview server is down)."""
    return check_url(SPACET_HEALTH_URL)


def main():
    global fail_count, spacet_fail_count
    logger.info("=" * 60)
    logger.info("  PM Tools Hub — Watchdog Supervisor Initialized")
    logger.info("  Target Domain: https://sonxit.io.vn")
    logger.info("  Health URL: http://127.0.0.1:5000/api/health")
    logger.info("=" * 60)

    ensure_startup_task()

    # Initial boot of services if not running
    if not check_health():
        start_server()
        time.sleep(3)

    if not check_spacet():
        start_spacet()
    start_spacet_tunnel()

    if not is_cloudflared_running():
        start_tunnel()

    logger.info("Watchdog protection active. Monitoring continuously...")

    while True:
        try:
            # 1. Check Python Server Health
            if check_health():
                if fail_count > 0:
                    logger.info("Server recovered to healthy state!")
                fail_count = 0
            else:
                fail_count += 1
                logger.warning(f"Health check failed ({fail_count}/{MAX_FAILURES})")
                if fail_count >= MAX_FAILURES:
                    logger.error("Server unresponsive! Restarting WSGI server...")
                    start_server()
                    fail_count = 0
                    time.sleep(5)

            # 2. Check SpaceT (a SpaceT fault never takes the hub down)
            if check_spacet():
                spacet_fail_count = 0
            else:
                spacet_fail_count += 1
                if spacet_fail_count >= MAX_FAILURES:
                    logger.error("SpaceT unresponsive! Restarting SpaceT...")
                    try:
                        start_spacet()
                    except Exception as e:
                        logger.error(f"SpaceT restart failed: {e}")
                    spacet_fail_count = 0

            if spacet_tunnel_proc is not None and spacet_tunnel_proc.poll() is not None:
                logger.warning("SpaceT tunnel process missing! Restarting...")
                start_spacet_tunnel()

            # 3. Check Cloudflare Tunnel
            if not is_cloudflared_running():
                logger.warning(
                    "Cloudflare tunnel process missing! Restarting tunnel..."
                )
                start_tunnel()

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Watchdog stopped manually by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected Watchdog exception: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
