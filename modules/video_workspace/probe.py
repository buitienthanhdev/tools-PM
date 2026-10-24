"""
Phân tích video bằng ffprobe (nội dung thật, không tin đuôi file): kích thước hiển thị, fps, VFR, xoay, SAR,
HDR / độ sâu màu / không gian màu, âm thanh, phụ đề. Kết quả là dict gọn để lưu DB và hiện cho người dùng.
"""

import json
import re
import statistics
import subprocess
from fractions import Fraction

from . import settings

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}
# Âm thanh MP4 phát được trên trình duyệt → giữ nguyên; còn lại chuyển AAC (báo rõ)
BROWSER_AUDIO = {"aac", "mp3"}


class ProbeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _run(args, timeout=60):
    r = subprocess.run([settings.ffprobe(), "-v", "error", *args], capture_output=True, timeout=timeout,
                       creationflags=NO_WINDOW)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _fps(s):
    try:
        f = Fraction(s)
        return float(f) if f > 0 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def _rotation(st):
    for sd in st.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                return int(round(float(sd["rotation"]))) % 360
            except (TypeError, ValueError):
                pass
    try:
        return int((st.get("tags") or {}).get("rotate", 0)) % 360
    except (TypeError, ValueError):
        return 0


def _vfr(path, fps):
    """Đo khoảng cách timestamp 300 gói đầu: lệch nhiều so với 1/fps → fps biến thiên."""
    code, out, _ = _run(["-select_streams", "v:0", "-read_intervals", "%+#300", "-show_entries", "packet=pts_time",
                         "-of", "csv=p=0", path], timeout=60)
    pts = sorted(float(x) for x in out.split() if re.match(r"^-?\d+(\.\d+)?$", x.strip().rstrip(",")))
    if len(pts) < 10 or not fps:
        return False, None
    d = [b - a for a, b in zip(pts, pts[1:]) if b > a]
    if not d:
        return False, None
    exp = 1 / fps
    off = sum(1 for x in d if abs(x - exp) > exp * 0.25)
    return off / len(d) > 0.05, round(statistics.pstdev(d) * 1000, 2)


def probe(path):
    code, out, err = _run(["-print_format", "json", "-show_format", "-show_streams", path], timeout=120)
    if code != 0:
        # Không lộ đường dẫn máy chủ: bỏ tiền tố "[demuxer @ 0x…]" và tên file khỏi thông báo của ffprobe
        why = [re.sub(r"^\[[^\]]*\]\s*", "", ln).strip() for ln in err.splitlines() if ln.strip() and path not in ln]
        raise ProbeError("not_media", "File không phải video hợp lệ hoặc đã hỏng" + (f" ({why[0][:120]})" if why else ""))
    data = json.loads(out or "{}")
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    if not v:
        raise ProbeError("no_video", "File không có luồng hình (video)")
    fmt = data.get("format") or {}
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    if w <= 0 or h <= 0:
        raise ProbeError("bad_video", "Không đọc được kích thước khung hình")
    r_fps, avg_fps = _fps(v.get("r_frame_rate")), _fps(v.get("avg_frame_rate"))
    fps = avg_fps or r_fps
    duration = None
    for src in (v.get("duration"), fmt.get("duration")):
        try:
            duration = float(src)
            break
        except (TypeError, ValueError):
            continue
    if not duration or duration <= 0:
        raise ProbeError("no_duration", "Không xác định được thời lượng video")
    sar = v.get("sample_aspect_ratio") or "1:1"
    try:
        sar_f = Fraction(sar.replace(":", "/")) if sar not in ("0:1", "N/A") else Fraction(1)
    except (ValueError, ZeroDivisionError):
        sar_f = Fraction(1)
    rot = _rotation(v)
    disp_w, disp_h = (round(w * sar_f), h)
    if rot in (90, 270):
        disp_w, disp_h = disp_h, disp_w
    pix = v.get("pix_fmt") or ""
    m = re.search(r"p(\d+)(le|be)?$", pix)
    bit_depth = int(v.get("bits_per_raw_sample") or 0) or (int(m.group(1)) if m and int(m.group(1)) > 8 else 8)
    transfer = v.get("color_transfer")
    hdr = transfer in HDR_TRANSFERS or (v.get("color_primaries") == "bt2020" and bit_depth > 8)
    vfr, jitter = _vfr(path, fps)
    if r_fps and avg_fps and abs(r_fps - avg_fps) / r_fps > 0.02:
        vfr = True
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    subs = [s for s in streams if s.get("codec_type") == "subtitle"]
    a = audio[0] if audio else None
    frames = None
    try:
        frames = int(v.get("nb_frames")) if v.get("nb_frames") else None
    except ValueError:
        frames = None
    return {
        "container": fmt.get("format_name"), "size": int(fmt.get("size") or 0), "bitrate": int(fmt.get("bit_rate") or 0) or None,
        "duration": round(duration, 3),
        "video": {"codec": v.get("codec_name"), "profile": v.get("profile"), "width": w, "height": h,
                  "display_width": disp_w, "display_height": disp_h, "sar": sar, "rotation": rot,
                  "fps": round(fps, 3) if fps else None, "r_fps": round(r_fps, 3) if r_fps else None,
                  "vfr": bool(vfr), "frame_jitter_ms": jitter, "frames": frames, "pix_fmt": pix, "bit_depth": bit_depth,
                  "color_space": v.get("color_space"), "color_primaries": v.get("color_primaries"),
                  "color_transfer": transfer, "color_range": v.get("color_range"), "hdr": bool(hdr),
                  "bitrate": int(v.get("bit_rate") or 0) or None},
        "audio": ({"codec": a.get("codec_name"), "channels": a.get("channels"), "layout": a.get("channel_layout"),
                   "sample_rate": int(a.get("sample_rate") or 0) or None, "bitrate": int(a.get("bit_rate") or 0) or None,
                   "browser_ok": a.get("codec_name") in BROWSER_AUDIO, "count": len(audio)} if a else None),
        "subtitles": len(subs),
        "subtitle_codecs": [s.get("codec_name") for s in subs],
    }


def needs_normalize(info, start=None, end=None):
    """Lý do phải tạo file trung gian trước khi đưa vào RVE (RVE không cắt đoạn, không xử lý xoay/VFR)."""
    v = info["video"]
    why = []
    if start is not None or end is not None:
        why.append("cắt đoạn xử lý thử")
    if v["rotation"]:
        why.append(f"xoay {v['rotation']}°")
    if v["sar"] not in ("1:1", "0:1", "N/A"):
        why.append(f"điểm ảnh không vuông (SAR {v['sar']})")
    if v["vfr"]:
        why.append("fps biến thiên → chuyển sang fps cố định")
    if v["width"] % 2 or v["height"] % 2:
        why.append("kích thước lẻ")
    return why
