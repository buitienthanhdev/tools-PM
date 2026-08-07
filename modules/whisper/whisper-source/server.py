"""
Whisper Studio — Production Server
Uses Waitress WSGI server instead of Flask dev server
"""
from waitress import serve
from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("  Whisper Studio — Production Server (Waitress)")
    print("  Running on http://0.0.0.0:5000")
    print("  Expose via: cloudflared tunnel run whisper-studio")
    print("=" * 60)
    serve(
        app,
        host='0.0.0.0',
        port=5000,
        threads=8,               # Handle concurrent requests
        channel_timeout=300,     # 5min timeout for long transcriptions
        connection_limit=100,
    )
