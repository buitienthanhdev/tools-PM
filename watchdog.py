"""
PM Tools Hub — High Availability Watchdog Supervisor
Monitors server.py (http://127.0.0.1:5000/api/health) and cloudflared tunnel 24/7.
Automatically recovers from crashes, hangs, network drops, or process kills.
"""

import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# ── Logging Configuration ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'watchdog.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Watchdog")

PYTHON_EXE = r"C:\Users\TIEN THANH\.conda\envs\paint-ai\python.exe"
if not os.path.exists(PYTHON_EXE):
    PYTHON_EXE = sys.executable

# Locate cloudflared.exe
CF_CMD = "cloudflared"
cf_candidates = [
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe"
]
for path in cf_candidates:
    if os.path.exists(path):
        CF_CMD = path
        break

CONFIG_FILE = str(BASE_DIR / 'cloudflared-config.yml')
HEALTH_URL = "http://127.0.0.1:5000/api/health"
CHECK_INTERVAL = 5 # seconds
MAX_FAILURES = 3

server_proc = None
tunnel_proc = None
fail_count = 0


def kill_port_5000():
    """Kill any process occupying port 5000."""
    logger.warning("Clearing port 5000...")
    try:
        if sys.platform == 'win32':
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
            subprocess.run(cmd, shell=True, capture_output=True)
    except Exception as e:
        logger.error(f"Error clearing port 5000: {e}")


def is_cloudflared_running():
    """Check if cloudflared tunnel is running."""
    if sys.platform == 'win32':
        try:
            cmd = 'tasklist /FI "IMAGENAME eq cloudflared.exe"'
            out = subprocess.check_output(cmd, shell=True, text=True)
            return "cloudflared.exe" in out
        except Exception:
            return False
    return False


def start_server():
    """Start server.py WSGI backend with redirected output."""
    global server_proc
    logger.info("Starting PM Tools WSGI Server (server.py)...")
    kill_port_5000()
    time.sleep(1)
    
    server_script = str(BASE_DIR / 'server.py')
    server_log = open(LOG_DIR / 'server.log', 'a', encoding='utf-8')
    
    server_proc = subprocess.Popen(
        [PYTHON_EXE, server_script],
        cwd=str(BASE_DIR),
        stdout=server_log,
        stderr=server_log
    )
    logger.info(f"Server started with PID: {server_proc.pid}")


def start_tunnel():
    """Start Cloudflare Tunnel with redirected output."""
    global tunnel_proc
    logger.info("Starting Cloudflare Tunnel...")
    
    tunnel_log = open(LOG_DIR / 'tunnel.log', 'a', encoding='utf-8')
    cmd = [CF_CMD, "--config", CONFIG_FILE, "tunnel", "run", "whisper-studio"]
    
    tunnel_proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=tunnel_log,
        stderr=tunnel_log
    )
    logger.info(f"Cloudflare Tunnel started with PID: {tunnel_proc.pid}")


def check_health():
    """Ping local health endpoint."""
    try:
        req = urllib.request.Request(HEALTH_URL, headers={'User-Agent': 'PMTools-Watchdog/1.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    global fail_count
    logger.info("=" * 60)
    logger.info("  PM Tools Hub — Watchdog Supervisor Initialized")
    logger.info("  Target Domain: https://sonxit.io.vn")
    logger.info("  Health URL: http://127.0.0.1:5000/api/health")
    logger.info("=" * 60)

    # Initial boot of services if not running
    if not check_health():
        start_server()
        time.sleep(3)

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

            # 2. Check Cloudflare Tunnel
            if not is_cloudflared_running():
                logger.warning("Cloudflare tunnel process missing! Restarting tunnel...")
                start_tunnel()

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Watchdog stopped manually by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected Watchdog exception: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
