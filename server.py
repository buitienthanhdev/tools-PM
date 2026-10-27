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
        # Mỗi kết nối SSE theo dõi tác vụ và mỗi request AI dài giữ 1 luồng suốt thời gian chạy;
        # 8 luồng cũ bị chiếm hết → /api/ping không được trả lời → watchdog tưởng chết và kill server.
        threads=64,
        channel_timeout=300,
        connection_limit=500,
    )
