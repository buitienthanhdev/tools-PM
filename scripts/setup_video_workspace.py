"""
Cài môi trường Video Workspace (tái lập được, có kiểm tra). Chạy bằng Python của Hub:
    .venv\\Scripts\\python.exe scripts\\setup_video_workspace.py [--skip-venv] [--skip-models]

1. Mã nguồn REAL-Video-Enhancer đúng commit đã kiểm tra → modules/video_workspace/vendor/real-video-enhancer (giữ LICENSE).
2. ffmpeg/ffprobe 7.1.1 (gyan.dev essentials, qua GitHub GyanD/codexffmpeg) → kiểm SHA-256 → venvs/video-bin.
3. venv riêng venvs/video theo requirements-video.txt (PyTorch CUDA 13.0).
4. Model trong danh mục đã duyệt (catalog.py) từ nguồn chính thức, kiểm SHA-256 → venvs/video-models.
Không đụng tới venv / dữ liệu của Hub.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RVE_REPO = "https://github.com/TNTwise/REAL-Video-Enhancer"
RVE_COMMIT = "8541c46ca14e6f84fc86c5b9d3b75373e25732e5"
FFMPEG_URL = "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip"
FFMPEG_SHA256 = "04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4"


def sh(*args, **kw):
    print("$", " ".join(args))
    subprocess.run(args, check=True, **kw)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def vendor():
    d = os.path.join(ROOT, "modules", "video_workspace", "vendor", "real-video-enhancer")
    if not os.path.isdir(os.path.join(d, ".git")):
        sh("git", "clone", "--recursive", RVE_REPO, d)
    sh("git", "-C", d, "fetch", "--quiet", "origin")
    sh("git", "-C", d, "checkout", "--quiet", RVE_COMMIT)
    sh("git", "-C", d, "submodule", "update", "--init", "--recursive")
    head = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert head == RVE_COMMIT, f"commit {head} != {RVE_COMMIT}"
    dirty = subprocess.run(["git", "-C", d, "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
    assert not dirty, "Mã nguồn upstream bị sửa — tích hợp không được sửa upstream:\n" + dirty
    assert os.path.isfile(os.path.join(d, "LICENSE"))
    print(f"RVE @ {RVE_COMMIT} OK")


def ffmpeg(cfg):
    target = cfg["ffmpeg_dir"]
    if os.path.isfile(os.path.join(target, "ffprobe.exe")):
        print("ffmpeg/ffprobe đã có:", target)
        return
    base = os.path.dirname(os.path.dirname(target))
    os.makedirs(base, exist_ok=True)
    z = os.path.join(base, "ffmpeg.zip")
    print("Tải", FFMPEG_URL)
    urllib.request.urlretrieve(FFMPEG_URL, z)
    got = sha256(z)
    assert got == FFMPEG_SHA256, f"ffmpeg.zip sai SHA-256: {got}"
    with zipfile.ZipFile(z) as f:
        for n in f.namelist():
            if n.startswith("/") or ".." in n.split("/"):
                raise SystemExit(f"Đường dẫn nguy hiểm trong zip: {n}")
        f.extractall(base)
    print("ffmpeg OK:", target)


def venv(cfg):
    py = cfg["python"]
    if not os.path.isfile(py):
        sh(sys.executable if not hasattr(sys, "base_prefix") else os.path.join(sys.base_prefix, "python.exe"), "-m", "venv",
           os.path.dirname(os.path.dirname(py)))
    sh(py, "-m", "pip", "install", "-r", os.path.join(ROOT, "requirements-video.txt"))
    sh(py, "-c", "import torch; assert torch.cuda.is_available(), 'CUDA không khả dụng'; print(torch.__version__, torch.cuda.get_device_name(0))")


def model_files():
    from modules.video_workspace import catalog, models

    for mid, m in catalog.MODELS.items():
        print(f"{mid}: {models.ensure(mid)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-venv", action="store_true")
    ap.add_argument("--skip-models", action="store_true")
    a = ap.parse_args()
    from modules.video_workspace import settings

    cfg = settings.get()
    vendor()
    ffmpeg(cfg)
    if not a.skip_venv:
        venv(cfg)
    if not a.skip_models:
        model_files()
    from modules.video_workspace import models

    caps = models.capabilities(wait=True)
    print("Năng lực:", caps)
    if not caps.get("ok"):
        raise SystemExit("Backend GPU chưa khả dụng")


if __name__ == "__main__":
    main()
