"""
PM Tools Hub — Real-Time Status & Health Diagnostic
"""

import subprocess
import time
import urllib.error
import urllib.request

HEALTH_URL = "http://127.0.0.1:5000/api/health"
PUBLIC_URL = "https://sonxit.io.vn/api/health"


def check_url(url, label):
    start = time.time()
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "PMTools-StatusCheck/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            elapsed = round((time.time() - start) * 1000, 1)
            if resp.status == 200:
                print(f"  [OK] {label:<22} -> HTTP 200 ({elapsed} ms)")
                return True
            else:
                print(f"  [FAIL] {label:<20} -> HTTP {resp.status}")
                return False
    except urllib.error.HTTPError as e:
        print(f"  [FAIL] {label:<20} -> HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  [FAIL] {label:<20} -> {e}")
        return False


def check_process(name, keyword):
    try:
        out = subprocess.check_output(
            f'tasklist /FI "IMAGENAME eq {name}"', shell=True, text=True
        )
        if name in out:
            print(f"  [OK] Process {name:<18} -> RUNNING")
            return True
        else:
            print(f"  [OFF] Process {name:<17} -> STOPPED")
            return False
    except Exception as e:
        print(f"  [ERR] Process {name:<17} -> Error: {e}")
        return False


def main():
    print("=" * 60)
    print("  PM Tools Hub — Uptime & System Health Status")
    print("=" * 60)

    print("\n[Processes]")
    check_process("python.exe", "server.py")
    check_process("cloudflared.exe", "whisper-studio")

    print("\n[Connectivity & Endpoints]")
    local_ok = check_url(HEALTH_URL, "Local Health Check")
    public_ok = check_url(PUBLIC_URL, "Public Domain (sonxit.io.vn)")

    print("\n" + "=" * 60)
    if local_ok and public_ok:
        print("  STATUS: ONLINE & FULLY OPERATIONAL (100% HEALTH)")
    elif local_ok and not public_ok:
        print("  STATUS: SERVER ONLINE, TUNNEL DISCONNECTED")
    else:
        print("  STATUS: SERVER DOWN OR UNRESPONSIVE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
