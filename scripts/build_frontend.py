"""Gộp + rút gọn giao diện vào static/dist/ bằng esbuild (chạy qua npx, cần Node).

    python scripts/build_frontend.py

- dist/main.js + các chunk: toàn bộ JS, giữ tách lazy theo từng công cụ (import() → chunk riêng),
  dịch xuống cú pháp cũ cho trình duyệt điện thoại đời cũ.
- dist/app.css: CSS lõi gộp làm một.
- dist/index.html: bản index trỏ vào các file trên.
- dist/STAMP: mã băm mã nguồn lúc build. Server chỉ dùng dist khi STAMP khớp mã nguồn hiện tại;
  sửa code mà quên build lại → server tự dùng mã nguồn chưa gộp, không bao giờ chạy code cũ.

Chạy lại script này rồi commit static/dist/ mỗi khi sửa JS/CSS.
"""

import os
import re
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from core.assets import source_hash  # noqa: E402

STATIC = os.path.join(BASE, "static")
DIST = os.path.join(STATIC, "dist")
ESBUILD = "esbuild@0.24.2"
TARGET = "chrome70,firefox68,safari13,edge79"


def esbuild(*args):
    cmd = ["npx", "--yes", ESBUILD, *args, "--log-level=warning"]
    subprocess.run(cmd, cwd=BASE, check=True, shell=os.name == "nt")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    index = open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()
    styles = re.findall(r'<link rel="stylesheet" href="/(styles/[^"]+\.css)" />', index)

    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(DIST)

    esbuild("static/js/main.js", "--bundle", "--splitting", "--format=esm", "--minify",
            f"--target={TARGET}", "--outdir=static/dist", "--entry-names=[name]",
            "--chunk-names=c-[hash]", "--legal-comments=none")

    entry = os.path.join(DIST, "_app.css")
    with open(entry, "w", encoding="utf-8") as f:
        f.writelines(f'@import "../{s}";\n' for s in styles)
    esbuild("static/dist/_app.css", "--bundle", "--minify", f"--target={TARGET}",
            "--outfile=static/dist/app.css", "--external:/assets/*", "--external:/fonts/*")
    os.remove(entry)

    html = re.sub(r'\s*<link rel="stylesheet" href="/styles/[^"]+" />', "", index)
    html = re.sub(r'\s*<link rel="modulepreload" href="[^"]+" />', "", html)
    html = re.sub(r"\s*<!-- Tải song song[^>]*-->", "", html)
    # Chunk dùng chung mà main.js import tĩnh → tải song song ngay, không chờ đọc xong main.js
    main_js = open(os.path.join(DIST, "main.js"), encoding="utf-8").read()
    chunks = sorted(set(re.findall(r'(?:from|import)\s*"\./(c-[\w-]+\.js)"', main_js)))
    preloads = "".join(f'  <link rel="modulepreload" href="/dist/{c}" />\n' for c in ["main.js", *chunks])
    html = html.replace("</head>", '  <link rel="stylesheet" href="/dist/app.css" />\n' + preloads + "</head>", 1)
    html = html.replace('src="/js/main.js"', 'src="/dist/main.js"')
    assert 'src="/dist/main.js"' in html, "index.html không còn <script src=/js/main.js>"
    with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    stamp = source_hash(STATIC)
    with open(os.path.join(DIST, "STAMP"), "w", encoding="ascii") as f:
        f.write(stamp)

    total = sum(os.path.getsize(os.path.join(DIST, n)) for n in os.listdir(DIST))
    print(f"dist/ xong: {len(os.listdir(DIST))} file, {total / 1024:.0f}KB (chưa nén), STAMP {stamp}")


if __name__ == "__main__":
    main()
