"""
PM Tools Hub — Production Waitress Server
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from waitress import serve

from app import app

if __name__ == "__main__":
    print("============================================================")
    print("  PM Tools Hub - Production WSGI Server")
    print("  URL: http://localhost:5000")
    print("  Cloudflare Tunnel Domain: https://sonxit.io.vn")
    print("============================================================")
    serve(
        app,
        listen="127.0.0.1:5000",
        threads=8,
        channel_timeout=300,
        connection_limit=100,
    )
