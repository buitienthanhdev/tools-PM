"""
Xử lý một job: lập kế hoạch → (chuẩn hoá) → chạy CLI backend của REAL-Video-Enhancer → kiểm tra đầu ra.

Vì sao có bước chuẩn hoá (đã đọc mã upstream, commit ghi trong VENDOR.md):
- RVE nhận --start_time/--end_time nhưng lệnh đọc khung hình KHÔNG dùng chúng → tự cắt đoạn thử ra file trung gian.
- RVE đọc khung hình thô với kích thước cố định → video xoay / SAR ≠ 1 / kích thước lẻ phải được đưa về dạng chuẩn.
- RVE ghi fps cố định = fps × hệ số → video fps biến thiên phải đổi sang fps cố định trước, nếu không thời lượng sai.
- RVE luôn ghép phụ đề bằng "-c:s copy" vào MP4 → phụ đề dạng văn bản/ảnh làm ffmpeg lỗi → bỏ phụ đề (báo rõ).
File trung gian dùng FFV1 (không mất dữ liệu), âm thanh giữ nguyên (copy).

Theo dõi tiến trình: RVE in "Total Output Frames: N" (stderr) và "FPS: x Current Frame: n ETA: …" (stdout, '\\r').
Khi một luồng render của RVE lỗi, tiến trình KHÔNG tự thoát (đã gặp khi thử) → phát hiện "Exception in thread" / không
có khung hình mới quá stall_timeout_s → diệt cả cây tiến trình.
"""

import os
import re
import shutil
import subprocess
import threading
import time
from fractions import Fraction

import psutil

from . import catalog, db, models, probe, settings

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STD_FPS = [Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001), Fraction(30), Fraction(48),
           Fraction(50), Fraction(60000, 1001), Fraction(60), Fraction(100), Fraction(120)]


class JobError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Cancelled(Exception):
    pass


# ── Kế hoạch ─────────────────────────────────────────────────────
def std_fps(fps):
    """fps đo được → phân số chuẩn gần nhất (24 → 24, 23.976 → 24000/1001), sai số tối đa 0,2%."""
    best = min(STD_FPS, key=lambda f: abs(float(f) - fps))
    if abs(float(best) - fps) / fps <= 0.002:
        return best
    return Fraction(fps).limit_denominator(1001)


def normalized_size(v):
    """Kích thước khung sau bước chuẩn hoá — PHẢI khớp đúng bộ lọc ffmpeg trong Runner._normalize:
    ffmpeg xoay khung trước (SAR đảo khi xoay 90/270), rồi scale=trunc(iw*sar/2)*2:ih, rồi làm chẵn trunc(x/2)*2."""
    w, h = v["width"], v["height"]
    try:
        sar = Fraction(str(v.get("sar") or "1:1").replace(":", "/"))
    except (ValueError, ZeroDivisionError):
        sar = Fraction(1)
    if sar <= 0:
        sar = Fraction(1)
    if v.get("rotation") in (90, 270):
        w, h, sar = h, w, 1 / sar
    if sar != 1:
        w = int(float(w) * float(sar) / 2) * 2  # cùng phép tính dấu phẩy động với biểu thức của ffmpeg
    return w // 2 * 2, h // 2 * 2


def plan(info, conf, cfg=None):
    """Kiểm tra cấu hình theo danh mục + giới hạn, tính thông số đầu ra. Raise JobError nếu không hợp lệ."""
    cfg = cfg or settings.get()
    allowed = catalog.allowed(cfg)
    v = info["video"]
    warnings = []
    up = conf.get("upscale")
    it = conf.get("interpolate")
    rs = list(conf.get("restore") or [])
    if up and (up not in allowed or allowed[up]["kind"] != "upscale"):
        raise JobError("bad_model", "Model tăng độ phân giải không hợp lệ")
    if it and (it not in allowed or allowed[it]["kind"] != "interpolate"):
        raise JobError("bad_model", "Model nội suy không hợp lệ")
    if len(rs) > 2 or len(set(rs)) != len(rs) or any(r not in allowed or allowed[r]["kind"] != "restore" for r in rs):
        raise JobError("bad_model", "Model phục hồi không hợp lệ (tối đa 2, không trùng)")
    if len({allowed[r]["group"] for r in rs}) != len(rs):
        raise JobError("bad_model", "Chỉ chọn một model cho mỗi loại phục hồi")
    target = conf.get("target_fps") if it else None
    if target is not None:
        if not isinstance(target, int) or isinstance(target, bool) or target not in catalog.TARGET_FPS:
            raise JobError("bad_target", f"fps đích phải là {', '.join(map(str, catalog.TARGET_FPS))}")
        if conf.get("factor") is not None:
            raise JobError("bad_option", "Chọn hệ số nội suy HOẶC fps đích, không chọn cả hai")
        raw = None
    else:
        raw = conf.get("factor") if it else 1
    # Không làm tròn ngầm (2.5 → 2 là sai ý người dùng): chỉ nhận đúng số nguyên trong danh sách
    factor = raw if isinstance(raw, int) and not isinstance(raw, bool) else -1
    if it and target is None and factor not in catalog.INTERPOLATE_FACTORS:
        raise JobError("bad_factor", f"Hệ số nội suy phải là {', '.join(map(str, catalog.INTERPOLATE_FACTORS))}")
    if not (up or it or rs):
        raise JobError("nothing", "Chưa chọn thao tác nào")
    sd = conf.get("scene_detect") or "pyscenedetect"
    if sd not in catalog.SCENE_DETECT:
        raise JobError("bad_option", "Phương pháp phát hiện chuyển cảnh không hợp lệ")
    if it and rs and sd == "pyscenedetect":
        sd = "mean"
        warnings.append("Khi kết hợp phục hồi với nội suy, phát hiện chuyển cảnh dùng phương pháp 'độ sáng trung bình' "
                        "(PySceneDetect của backend lỗi với tổ hợp này)")
    duration = info["duration"]
    start = end = None
    if conf.get("preview"):
        try:
            start = max(0.0, float(conf["preview"].get("start") or 0))
        except (TypeError, ValueError, AttributeError) as e:
            raise JobError("bad_option", "Thời điểm bắt đầu xử lý thử không hợp lệ") from e
        start = min(start, max(0.0, duration - 1))
        end = min(duration, start + float(cfg["preview_seconds"]))
        duration = end - start
    if info["duration"] > cfg["max_duration_s"]:
        raise JobError("too_long", f"Video dài {info['duration']:.0f}s vượt giới hạn {cfg['max_duration_s']}s")
    w, h = normalized_size(v)
    if w * h > cfg["max_input_pixels"]:
        raise JobError("too_large", f"Độ phân giải đầu vào {w}×{h} vượt giới hạn")
    scale = catalog.MODELS[up]["scale"] if up else 1
    ow, oh = w * scale, h * scale
    if ow * oh > cfg["max_output_pixels"]:
        lim = cfg["max_output_pixels"]
        raise JobError("output_too_large", f"Đầu ra {ow}×{oh} vượt giới hạn {lim // 1_000_000} megapixel — chọn model hệ số nhỏ hơn "
                                            f"hoặc video độ phân giải thấp hơn")
    fps_in = std_fps(v["fps"] or 30)
    resample = False
    if target is not None:
        if target <= float(fps_in) * 1.01:
            raise JobError("bad_target", f"fps đích {target} phải lớn hơn fps gốc {float(fps_in):.3f}")
        factor = next((f for f in catalog.INTERPOLATE_FACTORS if float(fps_in) * f >= target - 0.01), None)
        if factor is None:
            raise JobError("bad_target", f"Từ {float(fps_in):.3f} fps không lên được {target} fps (tối đa ×{max(catalog.INTERPOLATE_FACTORS)})")
        resample = abs(float(fps_in) * factor - target) > 0.01
        fps_out = Fraction(target) if resample else fps_in * factor
        if resample:
            warnings.append(f"Nội suy ×{factor} ({float(fps_in) * factor:.3f} fps) rồi đổi về đúng {target} fps — "
                            "một số khung nội suy bị bỏ, chuyển động có thể không đều bằng hệ số nguyên")
    else:
        fps_out = fps_in * factor
    if float(fps_out) > cfg["max_output_fps"]:
        raise JobError("fps_too_high", f"fps đầu ra {float(fps_out):.2f} vượt giới hạn {cfg['max_output_fps']}")
    reasons = probe.needs_normalize(info, start, end)
    codecs = info.get("subtitle_codecs") or []
    subs_keep = [i for i, c in enumerate(codecs) if c in catalog.TEXT_SUBS]
    if info["subtitles"]:
        reasons.append("tách phụ đề (ghép lại ở bước cuối)")
        dropped = [c for c in codecs if c not in catalog.TEXT_SUBS]
        if subs_keep:
            warnings.append(f"Giữ {len(subs_keep)} phụ đề dạng chữ (chuyển sang mov_text trong MP4)")
        if dropped:
            warnings.append(f"Bỏ {len(dropped)} phụ đề dạng ảnh ({', '.join(sorted(set(dropped)))}) — MP4 không chứa được loại này")
    a = info["audio"]
    audio = "none"
    if a:
        audio = "copy" if a["browser_ok"] else "aac"
        if audio == "aac":
            warnings.append(f"Âm thanh {a['codec']} không phát được trên trình duyệt trong MP4 → chuyển sang AAC 192 kbps")
        if a["count"] > 1:
            warnings.append(f"Video có {a['count']} luồng âm thanh — tất cả được giữ")
    hdr = bool(v["hdr"])
    if hdr:
        warnings.append("Video HDR: xử lý ở chế độ HDR của backend, xuất H.265 10-bit (HEVC). Một số trình duyệt không phát được "
                        "HEVC — vẫn tải xuống được để xem bằng trình phát video")
    elif v["bit_depth"] > 8:
        warnings.append(f"Video {v['bit_depth']}-bit SDR: backend xử lý ở 8-bit, đầu ra H.264 8-bit (mất độ sâu màu)")
    if v["vfr"]:
        warnings.append(f"Video có fps biến thiên → chuyển sang {float(fps_in):.3f} fps cố định trước khi xử lý")
    if v["rotation"]:
        warnings.append(f"Video có metadata xoay {v['rotation']}° → xoay thật khung hình trước khi xử lý")
    if it and factor and (v["fps"] or 0) * factor > 120:
        warnings.append(f"fps đầu ra {float(fps_out):.0f} — nhiều màn hình/trình duyệt chỉ hiển thị tối đa 60–144 fps")
    frames = round(duration * float(fps_out))
    return {
        "upscale": up, "interpolate": it, "factor": factor, "target_fps": target, "resample": resample, "subs_keep": subs_keep,
        "restore": rs, "scene_detect": sd if it else None,
        "start": start, "end": end, "duration": round(duration, 3),
        "input": {"width": w, "height": h, "fps": float(fps_in), "fps_fraction": f"{fps_in.numerator}/{fps_in.denominator}"},
        "output": {"width": ow, "height": oh, "fps": round(float(fps_out), 3), "frames": frames,
                   "codec": "hevc" if hdr else "h264", "pix_fmt": "yuv420p10le" if hdr else "yuv420p", "container": "mp4",
                   "audio": audio},
        "hdr": hdr, "normalize": reasons, "warnings": warnings,
        "models": {k: {"id": k, "file": catalog.MODELS[k]["file"], "sha256": catalog.MODELS[k]["sha256"],
                       "license": catalog.MODELS[k]["license"]} for k in [x for x in (up, it, *rs) if x]},
    }


# ── Thực thi ─────────────────────────────────────────────────────
def kill_tree(pid):
    """Windows: python.exe của venv sinh thêm tiến trình con; ffmpeg là con của tiến trình đó → diệt cả cây."""
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = p.children(recursive=True) + [p]
    for x in procs:
        try:
            x.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=10)


class Runner:
    """Chạy một job; job: dict từ DB. update(**fields) ghi tiến độ; cancelled() kiểm tra yêu cầu huỷ."""

    def __init__(self, job, video, update, cancelled, log):
        self.job, self.video = job, video
        self.update, self.cancelled, self.log = update, cancelled, log
        self.cfg = settings.get()
        self.work = settings.data_dir("work", job["id"])
        self.proc = None

    def _check(self):
        if self.cancelled():
            raise Cancelled()

    def _disk(self, need_bytes):
        free = shutil.disk_usage(self.work).free
        if free - need_bytes < self.cfg["min_free_disk_gb"] * 1024 ** 3:
            raise JobError("disk_full", f"Máy chủ không đủ dung lượng trống (còn {free / 1024 ** 3:.1f} GB) — job tạm dừng an toàn")

    def run(self):
        p = db.loads(self.job["plan_json"])
        info = db.loads(self.video["info_json"])
        src = self.video["path"]
        out_frames = p["output"]["frames"]
        # Ước tính dung lượng: trung gian FFV1 ~ 1,5 byte/điểm ảnh/khung; đầu ra H.264 ~ 0,1 byte/điểm ảnh/khung
        in_px = p["input"]["width"] * p["input"]["height"] * p["duration"] * p["input"]["fps"]
        out_px = p["output"]["width"] * p["output"]["height"] * out_frames
        self._disk((in_px * 1.5 if p["normalize"] else 0) + out_px * 0.1)
        # 1. Model
        self.update(stage="preparing", message="Chuẩn bị model", progress=None, eta_s=None)
        paths = {}
        for mid in p["models"]:
            self._check()
            paths[mid] = models.ensure(mid, log=self.log)
        # 2. Chuẩn hoá
        rve_in = src
        if p["normalize"]:
            self.update(stage="preparing", message="Chuẩn hoá video: " + ", ".join(p["normalize"]))
            rve_in = self._normalize(src, info, p)
        # 3. RVE
        rve_out = os.path.join(self.work, "rve.mp4")
        self._rve(rve_in, rve_out, p, paths)
        # 4. Ghép âm thanh từ file gốc (RVE copy âm thanh qua container làm lệch ~1 khung AAC priming; bản thử cần cắt chính xác)
        out = os.path.join(self.work, "output.mp4")
        self._mux(rve_out, src, out, p, info)
        # 5. Kiểm tra
        self.update(stage="verifying", message="Kiểm tra file đầu ra", progress=100.0, eta_s=0)
        res = self._verify(out, p, info)
        final = os.path.join(settings.data_dir("results"), f"{self.job['id']}.mp4")
        os.replace(out, final)
        return final, res

    def _mux(self, video, src, out, p, info):
        self.update(stage="encoding", message="Ghép âm thanh gốc", progress=99.0, eta_s=None)
        subs = p.get("subs_keep") or []
        if p["output"]["audio"] == "none" and not subs and not p.get("resample"):
            os.replace(video, out)
            return
        if p.get("resample"):
            self.update(message=f"Đổi về đúng {p['target_fps']} fps")
        # Căn theo thời điểm KHUNG GIẢI MÃ ĐẦU TIÊN (đã áp edit list), không theo start_time của luồng: khi RVE tự ghép
        # âm thanh AAC, -avoid_negative_ts đẩy luồng hình đi một khoảng bằng priming (~21 ms). Đích: hình − tiếng như file gốc
        # (bản thử: khung đầu ↔ mẫu âm thanh tại điểm cắt). Đã kiểm chứng bằng video chớp sáng + tiếng bíp.
        trim = p["start"] is not None
        v_out = (_first_pts(video, "v:0") or 0.0) - (_fmt_start(video) or 0.0)
        if trim:
            want = 0.0
        else:
            s_v, s_a, s_m = _first_pts(src, "v:0") or 0.0, _first_pts(src, "a:0") or 0.0, _fmt_start(src) or 0.0
            want = (s_v - s_m) - (s_a - s_m)
        shift = round(want - v_out, 6)
        self.log(f"MUX căn hình: khung đầu ra {v_out:.4f}s, đích {want:.4f}s → dịch {shift:+.4f}s")
        args = [settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
        if abs(shift) > 0.0005:
            args += ["-itsoffset", f"{shift:.6f}"]
        args += ["-i", video]
        if trim:
            args += ["-ss", f"{p['start']:.3f}", "-t", f"{p['duration']:.3f}"]
        args += ["-i", src, "-map", "0:v:0"]
        if p["output"]["audio"] != "none":
            args += ["-map", "1:a"]
        for i in subs:
            args += ["-map", f"1:s:{i}"]
        if p.get("resample"):  # đổi fps → phải mã lại hình
            args += ["-vf", f"fps={p['target_fps']}", "-crf", str(int(self.cfg["crf"]))]
            args += (["-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1"] if p["hdr"]
                     else ["-c:v", "libx264", "-pix_fmt", "yuv420p"])
        else:
            args += ["-c:v", "copy"]
        if subs:
            args += ["-c:s", "mov_text"]
        if p["output"]["audio"] == "none":
            pass
        elif p["output"]["audio"] == "copy" and not trim:
            args += ["-c:a", "copy"]
        else:  # mã lại: âm thanh không phát được trên trình duyệt, hoặc bản thử (cắt chính xác tới mẫu)
            args += ["-c:a", "aac", "-b:a", "192k"]
        args += ["-movflags", "+faststart", "-shortest" if trim else "-dn", out]
        self.log("MUX: " + " ".join(args))
        r = subprocess.run(args, capture_output=True, timeout=3600, creationflags=NO_WINDOW)
        if r.returncode != 0 or not os.path.isfile(out):
            err = r.stderr.decode("utf-8", "replace")
            self.log("mux: " + err[-2000:])
            raise JobError(_classify(err)[0], "Không ghép được âm thanh: " + _last(err))

    def _normalize(self, src, info, p):
        v = info["video"]
        dst = os.path.join(self.work, "input.mkv")
        args = [settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-fflags", "+genpts"]
        if p["start"] is not None:
            args += ["-ss", f"{p['start']:.3f}"]
        args += ["-i", src]
        if p["end"] is not None:
            args += ["-t", f"{p['end'] - p['start']:.3f}"]
        vf = []
        if v["sar"] not in ("1:1", "0:1", "N/A"):
            vf.append("scale=trunc(iw*sar/2)*2:ih")
        vf.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
        vf.append("setsar=1")
        args += ["-map", "0:v:0", "-an", "-sn", "-dn", "-vf", ",".join(vf)]  # âm thanh ghép lại từ file gốc ở bước cuối
        if v["vfr"]:
            args += ["-fps_mode", "cfr", "-r", p["input"]["fps_fraction"]]
        args += ["-c:v", "ffv1", "-level", "3", "-slices", "16", "-g", "1", "-avoid_negative_ts", "make_zero", dst]
        self.log("NORMALIZE: " + " ".join(args))
        t0 = time.time()
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
        self.update(pid=self.proc.pid)
        err = []
        th = threading.Thread(target=lambda: err.extend(self.proc.stderr.read().decode("utf-8", "replace").splitlines()), daemon=True)
        th.start()
        while self.proc.poll() is None:
            if self.cancelled():
                kill_tree(self.proc.pid)
                raise Cancelled()
            if time.time() - t0 > self.cfg["max_runtime_s"]:
                kill_tree(self.proc.pid)
                raise JobError("timeout", "Chuẩn hoá video quá thời gian cho phép")
            time.sleep(0.5)
        th.join(5)
        for line in err[-20:]:
            self.log("ffmpeg: " + line)
        if self.proc.returncode != 0 or not os.path.isfile(dst):
            raise JobError(_classify("\n".join(err))[0], "Không chuẩn hoá được video: " + (err[-1][:200] if err else "lỗi ffmpeg"))
        return dst

    def _rve(self, src, out, p, paths):
        cfg = self.cfg
        args = [cfg["python"], "-E", "-s", "rve-backend.py", "-i", src, "-o", out, "--backend", cfg["backend"],
                "--device", "cuda", "--pytorch_gpu_id", str(cfg["gpu_id"]), "--ffmpeg_path", settings.ffmpeg(),
                "--cwd", self.work, "--overwrite", "--crf", str(int(cfg["crf"])),
                # Âm thanh của RVE bị thay ở bước ghép; chỉ cần ffmpeg của RVE ghi được (định dạng không vào được MP4 → AAC)
                "--audio_encoder_preset", "copy_audio" if p["output"]["audio"] != "aac" else "aac"]
        if p["hdr"]:
            args += ["--hdr_mode", "--video_encoder_preset", "libx265", "--video_pixel_format", "yuv420p10le"]
        else:
            args += ["--video_encoder_preset", "libx264", "--video_pixel_format", "yuv420p"]
        for r in p["restore"]:
            args += ["--extra_restoration_models", paths[r]]
        if p["upscale"]:
            args += ["--upscale_model", paths[p["upscale"]]]
        if p["interpolate"]:
            args += ["--interpolate_model", paths[p["interpolate"]], "--interpolate_factor", str(p["factor"]),
                     "--scene_detect_method", p["scene_detect"]]
        self.log("RVE: " + " ".join(f'"{a}"' if " " in a else a for a in args))
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        self.update(stage="loading", message="Nạp model lên GPU", progress=None, eta_s=None)
        t0 = time.time()
        self.proc = subprocess.Popen(args, cwd=cfg["rve_dir"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                     creationflags=NO_WINDOW)
        self.update(pid=self.proc.pid)
        st = {"total": None, "done": 0, "last_change": time.time(), "fatal": None, "first": None, "err_tail": []}

        def read_out():
            buf = b""
            while True:
                ch = self.proc.stdout.read(1)
                if not ch:
                    break
                if ch in (b"\r", b"\n"):
                    line = buf.decode("utf-8", "replace").strip()
                    buf = b""
                    m = re.search(r"Current Frame: (\d+)", line)
                    if m:
                        n = int(m.group(1))
                        if n != st["done"]:
                            st["done"], st["last_change"] = n, time.time()
                            st["first"] = st["first"] or (time.time(), n)
                else:
                    buf += ch

        def read_err():
            for raw in iter(self.proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if not line:
                    continue
                self.log(line)
                st["err_tail"] = (st["err_tail"] + [line])[-40:]
                m = re.search(r"Total Output Frames: (\d+)", line)
                if m:
                    st["total"] = int(m.group(1))
                if line.startswith("Exception in thread") or "Traceback (most recent call last)" in line:
                    st["fatal"] = st["fatal"] or time.time()

        ts = [threading.Thread(target=read_out, daemon=True), threading.Thread(target=read_err, daemon=True)]
        for t in ts:
            t.start()
        last_db = 0
        try:
            while self.proc.poll() is None:
                now = time.time()
                if self.cancelled():
                    raise Cancelled()
                if st["fatal"] and now - st["fatal"] > 3:  # chờ traceback in xong rồi dừng (RVE không tự thoát)
                    code, msg = _classify("\n".join(st["err_tail"]) + self._ffmpeg_log())
                    raise JobError(code, msg)
                if now - t0 > cfg["max_runtime_s"]:
                    raise JobError("timeout", f"Job chạy quá {cfg['max_runtime_s'] // 60} phút — đã dừng")
                if now - st["last_change"] > cfg["stall_timeout_s"] and now - t0 > cfg["stall_timeout_s"]:
                    raise JobError("stalled", f"Backend không xử lý thêm khung hình nào trong {cfg['stall_timeout_s']} giây — đã dừng")
                if now - last_db >= 1:
                    last_db = now
                    self._progress(st, p, now)
                time.sleep(0.25)
        except BaseException:
            kill_tree(self.proc.pid)
            raise
        for t in ts:
            t.join(5)
        self._progress(st, p, time.time())
        flog = self._ffmpeg_log()
        if flog.strip():
            self.log("ffmpeg_log.txt:\n" + flog[-3000:])
        if self.proc.returncode != 0 or st["fatal"] or not os.path.isfile(out):
            code, msg = _classify("\n".join(st["err_tail"]) + flog)
            raise JobError(code, msg)

    def _progress(self, st, p, now):
        total = st["total"] or p["output"]["frames"]
        done = st["done"]
        if not done:
            return
        if total and done >= total - max(2, p["factor"]):
            self.update(stage="encoding", message="Hoàn tất mã hoá và ghép âm thanh", frames_done=done, frames_total=total,
                        progress=99.0, eta_s=None)
            return
        eta = None
        fps = None
        if st["first"]:
            t1, n1 = st["first"]
            if now - t1 >= 5 and done - n1 > 0:
                fps = (done - n1) / (now - t1)
                if done / total >= 0.02:
                    eta = (total - done) / fps
        self.update(stage="processing", message="Đang xử lý khung hình", frames_done=done, frames_total=total,
                    progress=round(min(99.0, 100 * done / total), 1) if total else None,
                    eta_s=round(eta) if eta is not None else None, fps=round(fps, 2) if fps else None)

    def _ffmpeg_log(self):
        try:
            with open(os.path.join(self.work, "ffmpeg_log.txt"), encoding="utf-8", errors="replace") as f:
                return f.read()[-4000:]
        except OSError:
            return ""

    def _verify(self, out, p, info):
        try:
            o = probe.probe(out)
        except probe.ProbeError as e:
            raise JobError("bad_output", f"File đầu ra không hợp lệ: {e}") from e
        exp = p["output"]
        v = o["video"]
        problems = []
        if (v["width"], v["height"]) != (exp["width"], exp["height"]):
            problems.append(f"độ phân giải {v['width']}×{v['height']} ≠ {exp['width']}×{exp['height']}")
        if v["fps"] and abs(v["fps"] - exp["fps"]) / exp["fps"] > 0.01:
            problems.append(f"fps {v['fps']} ≠ {exp['fps']}")
        tol = max(0.35, 3 / p["input"]["fps"])
        if abs(o["duration"] - p["duration"]) > tol:
            problems.append(f"thời lượng {o['duration']:.2f}s ≠ {p['duration']:.2f}s")
        if exp["audio"] != "none" and not o["audio"]:
            problems.append("mất âm thanh")
        if problems:
            raise JobError("bad_output", "Đầu ra không đúng: " + "; ".join(problems))
        sync = None
        if o["audio"]:  # (hình − tiếng) của đầu ra so với file gốc; bản thử: so với 0
            def rel(path):
                v0, a0 = _first_pts(path, "v:0"), _first_pts(path, "a:0")
                return None if v0 is None or a0 is None else v0 - a0
            r_out = rel(out)
            r_src = 0.0 if p["start"] is not None else rel(self.video["path"])
            if r_out is not None and r_src is not None:
                sync = round((r_out - r_src) * 1000, 1)
        o["av_offset_ms"] = sync
        if sync is not None and abs(sync) > 100:
            raise JobError("av_desync", f"Âm thanh lệch hình {sync:.0f} ms")
        return o


def _first_pts(path, sel):
    """Thời điểm trình bày của khung/mẫu giải mã đầu tiên (đã áp edit list)."""
    # Đọc vài gói: gói AAC đầu là priming, bị bỏ khi giải mã nên 1 gói có thể không ra mẫu nào
    r = subprocess.run([settings.ffprobe(), "-v", "error", "-select_streams", sel, "-read_intervals", "%+#8",
                        "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0", path],
                       capture_output=True, timeout=60, creationflags=NO_WINDOW)
    for line in r.stdout.decode().splitlines():
        try:
            return float(line.strip().strip(","))
        except ValueError:
            continue
    return None


def _fmt_start(path):
    r = subprocess.run([settings.ffprobe(), "-v", "error", "-show_entries", "format=start_time", "-of", "csv=p=0", path],
                       capture_output=True, timeout=30, creationflags=NO_WINDOW)
    try:
        return float(r.stdout.decode().strip())
    except ValueError:
        return None


def _classify(text):
    t = text or ""
    if re.search(r"CUDA out of memory|OutOfMemoryError|CUBLAS_STATUS_ALLOC_FAILED|cudaErrorMemoryAllocation", t):
        return "gpu_oom", "GPU hết bộ nhớ — thử model nhẹ hơn, hệ số nhỏ hơn hoặc video độ phân giải thấp hơn"
    if re.search(r"No space left|There is not enough space|Errno 28|disk full", t, re.I):
        return "disk_full", "Máy chủ hết dung lượng ổ đĩa khi xử lý"
    if re.search(r"CUDA error|cudaError|CUDA driver|no kernel image", t):
        return "gpu_error", "Lỗi GPU/CUDA khi chạy model"
    if re.search(r"Invalid data|could not find codec|Error while decoding|Error initializing output|Conversion failed|"
                 r"Encoder .* not found|Invalid argument", t, re.I):
        return "codec_error", "Lỗi giải mã/mã hoá video (ffmpeg): " + _last(t)
    return "render_error", "Backend xử lý video báo lỗi: " + _last(t)


def _last(t):
    lines = [x.strip() for x in t.splitlines() if x.strip() and not x.strip().startswith("File ")]
    return (lines[-1] if lines else "không rõ")[:240]
