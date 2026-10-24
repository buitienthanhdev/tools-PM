"""RVE giả cho kiểm thử (không cần GPU): cùng tham số dòng lệnh và cùng định dạng tiến độ với rve-backend.py thật.
Tạo đầu ra bằng ffmpeg (scale × hệ số, fps × hệ số, ghép âm thanh). STUB_MODE: ok | slow | stall | crash."""
import argparse
import os
import re
import subprocess
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input")
ap.add_argument("-o", "--output")
ap.add_argument("--upscale_model")
ap.add_argument("--interpolate_model")
ap.add_argument("--interpolate_factor", type=float, default=1.0)
ap.add_argument("--extra_restoration_models", action="append")
ap.add_argument("--ffmpeg_path")
ap.add_argument("--list_backends", action="store_true")
a, _ = ap.parse_known_args()
mode = os.environ.get("STUB_MODE", "ok")

if a.list_backends:
    print("RVE Backend Version: stub\nPyTorch Version: 0.0\nPyTorch GPU 0: Stub GPU\nHalf precision support: True\n"
          "Available Backends: ['pytorch (cuda)']")
    sys.exit(0)

ff = a.ffmpeg_path
probe = subprocess.run([ff, "-hide_banner", "-i", a.input], capture_output=True, text=True, errors="replace").stderr
w, h = map(int, re.search(r", (\d{2,5})x(\d{2,5})", probe).groups())
fps = float(re.search(r"([\d.]+) fps", probe).group(1))
dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe).groups()
seconds = int(dur[0]) * 3600 + int(dur[1]) * 60 + float(dur[2])
name = os.path.basename(a.upscale_model or "").lower()
scale = (4 if ("4x" in name or "x4" in name) else 2) if a.upscale_model else 1
factor = int(a.interpolate_factor)
total = int(round(seconds * fps)) * factor
print(f"BACKEND: Total Output Frames: {total}", file=sys.stderr, flush=True)
time.sleep(0.5)
steps = 8 if mode != "slow" else 200
for k in range(1, steps + 1):
    if mode == "stall" and k > 2:
        time.sleep(3600)
    if mode == "crash" and k == 3:
        print("Exception in thread Thread-1 (render):\nTraceback (most recent call last):\nRuntimeError: CUDA out of memory. Tried to allocate 2 GiB",
              file=sys.stderr, flush=True)
        time.sleep(3600)  # như RVE thật: luồng render chết nhưng tiến trình không thoát
    sys.stdout.write(f"\rFPS: 30 Current Frame: {total * k // steps} ETA: 0:00:0{steps - k}")
    sys.stdout.flush()
    time.sleep(0.15 if mode != "slow" else 0.3)
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", a.input, "-map", "0:v:0", "-map", "0:a?",
                "-vf", f"scale={w * scale}:{h * scale},fps={fps * factor}", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", a.output], check=True)
print("\nBACKEND: Time to complete render: 1.0", file=sys.stderr, flush=True)
