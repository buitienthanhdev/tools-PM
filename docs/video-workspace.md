# Video Workspace (/video)

Workspace web để tăng độ phân giải, phục hồi (khử nén, khử nhiễu, khử nhoè) và nội suy fps cho video. Xử lý bằng **backend của
REAL-Video-Enhancer (RVE)** trên GPU của máy chủ Hub. Nguồn, phiên bản và giấy phép: `modules/video_workspace/VENDOR.md`.

## Kiến trúc

```
Trình duyệt ──(chunk 32 MB, Cloudflare ≤100 MB/request)──► /api/video/*  (Flask blueprint, quyền công cụ "video")
                                                              │  ghi DB (SQLite WAL data/video/video.db), file data/video/
                                                              ▼
                    worker nền trong tiến trình Hub ── khe GPU (khoá file) ── core.gpu.task("video") (xếp hàng chung Whisper/ESRGAN/Ollama)
                                                              │
        chuẩn hoá (ffmpeg, nếu cần) → venvs/video/python rve-backend.py (tiến trình con) → ghép âm thanh gốc → ffprobe kiểm tra
```

- **Không xử lý video trong request web.** Request chỉ tạo job; worker chạy tiến trình con.
- **Máy GPU = máy chạy Hub** (RTX 5090, driver 617.42), nên không cần worker từ xa. Không cổng nào mới được mở; RVE không có REST API và không lắng nghe mạng.
- **Hàng đợi bền:**
  - Bảng `jobs` có trạng thái, giai đoạn, tiến độ, số lần thử, PID, lease, phiên bản model (SHA-256), lỗi, thời hạn.
  - Mỗi GPU chạy 1 job (`gpu_concurrency`). Giới hạn này áp dụng cả giữa nhiều tiến trình Hub nhờ khoá file trong thư mục model.
- **Khởi động lại:** job đang chạy dở được xử lý thế này:
  - diệt tiến trình con còn sót;
  - chạy lại tối đa `max_attempts` lần (mặc định 2);
  - quá số lần đó thì báo lỗi `interrupted`.
- **Phân quyền:**
  - Mọi thao tác với file và job đều kiểm tra chủ sở hữu (người khác nhận 404). Admin xem được log theo job.
  - Công cụ "video" thuộc nhóm nhạy cảm, không tự cấp khi đăng ký.
- **An toàn tham số:**
  - Frontend chỉ gửi id model trong danh mục, hệ số nội suy (2, 3, 4), phương pháp phát hiện chuyển cảnh và thời điểm bắt đầu bản thử.
  - Khoá lạ bị từ chối. Không nhận đường dẫn, lệnh hay tham số ffmpeg.
- **Lưu trữ:**
  - File nằm ngoài web root, với tên nội bộ là UUID.
  - Tải xuống qua `/api/video/jobs/<id>/result`, có kiểm tra quyền và hỗ trợ Range.

## Những điều phát hiện khi đọc mã upstream (commit 8541c46) và cách xử lý

| Upstream | Hệ quả | Xử lý trong adapter |
| --- | --- | --- |
| `--start_time/--end_time` không được dùng trong lệnh đọc khung hình | Không cắt được đoạn thử | Tự cắt ra file trung gian FFV1 (không mất dữ liệu) |
| Đọc khung thô với kích thước cố định | Video xoay / SAR ≠ 1 / kích thước lẻ bị méo | Chuẩn hoá: xoay thật, SAR → 1, làm chẵn |
| Ghi fps cố định = fps × hệ số; hệ số lẻ làm tròn lên số khung | VFR sai thời lượng; ×2.5 thành slow motion | VFR → CFR trước; chỉ cho hệ số 2, 3, 4 |
| Luôn `-c:s copy` phụ đề vào MP4 | ffmpeg lỗi với phụ đề SRT/ASS | Bỏ phụ đề (có cảnh báo) |
| Copy âm thanh qua `-avoid_negative_ts` | Hình lệch khoảng 20 ms do priming AAC | Ghép lại âm thanh từ file gốc, căn theo khung giải mã đầu tiên |
| Luồng render lỗi nhưng tiến trình **không thoát** | Job treo vĩnh viễn | Bắt "Exception in thread" và phát hiện đứng tiến độ (`stall_timeout_s`), rồi diệt cả cây tiến trình |
| PySceneDetect lỗi khi có model phục hồi 1x trước nội suy | Crash (cv2.resize nhận float16) | Tổ hợp này tự dùng phương pháp "mean" (có cảnh báo) |
| `python.exe` của venv sinh tiến trình con trên Windows | Kill PID cha không dừng xử lý | Diệt cả cây tiến trình (psutil) |

Tiến độ lấy từ chính output của RVE: `Total Output Frames: N` (stderr) và `Current Frame: n` (stdout).
- **Phần trăm** chỉ hiện khi đã có cả hai số.
- **Thời gian còn lại** chỉ hiện sau ít nhất 5 giây xử lý và ít nhất 2% khung hình. Trước đó giao diện ghi rõ "chưa ước lượng được".

## Cấu hình (`data/config.json`, khoá `"video"`)

| Khoá | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `enabled` | false | Bật module (hoặc `PM_VIDEO=1`) |
| `python`, `ffmpeg_dir`, `models_dir` | `D:\tools PM\venvs\video…` | Môi trường xử lý, ngoài git, dùng chung giữa các bản Hub |
| `gpu_concurrency` | 1 | Số job đồng thời trên mỗi GPU |
| `max_upload_mb` / `chunk_mb` | 4096 / 32 | Dung lượng file / kích thước mỗi phần tải lên |
| `max_duration_s` | 1800 | Thời lượng tối đa |
| `max_input_pixels` / `max_output_pixels` | 3840×2160 | Độ phân giải tối đa |
| `max_output_fps` | 240 | |
| `max_queued_per_user` / `max_queued_total` | 3 / 30 | Số job chờ/chạy |
| `max_runtime_s` / `stall_timeout_s` | 14400 / 300 | Thời gian chạy tối đa / không có khung mới |
| `quota_per_user_gb` | 30 | Dung lượng lưu trữ mỗi người |
| `retention_hours` | 72 | Thời hạn lưu video và kết quả (hiện cho người dùng); log giữ thêm 7 ngày |
| `preview_seconds` | 10 | Độ dài bản xử lý thử |
| `allow_noncommercial_models` | true | Tắt nếu dùng thương mại (OpenProteus, AnimeJaNai là CC BY-NC) |
| `allow_model_download` | true | Chỉ tải model trong danh mục, kiểm tra SHA-256 |
| `min_free_disk_gb` | 10 | Dừng an toàn nếu ổ đĩa sắp đầy |

## Cài đặt / triển khai

1. `"D:\tools PM\tools PM\.venv\Scripts\python.exe" scripts\setup_video_workspace.py`. Script làm các bước sau, lần chạy đầu cần mạng và khoảng 4 GB:
   - tải mã nguồn RVE đúng commit;
   - tải ffmpeg và kiểm tra SHA-256;
   - tạo venv;
   - tải model và kiểm tra SHA-256;
   - kiểm tra GPU.
2. `scripts\deploy_accounting.ps1`, chạy bằng quyền Administrator:
   - merge code;
   - chạy bước cài đặt (bỏ qua venv và model đã có);
   - bật `video.enabled` khi đạt;
   - khởi động lại Hub;
   - kiểm tra `/video` và `/api/video/status`.
3. Admin tick "Video Workspace" cho tài khoản cần dùng tại `/admin`.
4. Tắt riêng Video Workspace: chạy `deploy_accounting.ps1 -DisableVideo`. Video và kết quả trong `data\video` vẫn được giữ.

## Kiểm thử (2026-10-24, RTX 5090)

### Video thật

Đoạn *Tears of Steel* © Blender Foundation (CC-BY), 1280×534, 24 fps, có tiếng. Các ca khó được tạo từ chính đoạn này.

| Ca | Kết quả |
| --- | --- |
| Upscale OpenProteus 2x | 2560×1068 @ 24 fps, 6,0 s, H.264 + AAC (8 s) |
| Real-ESRGAN 4x / Nomos SPAN 4x | 5120×2136 @ 24 fps khi chạy CLI. Trong web bị chặn vì vượt giới hạn 4K đầu ra mặc định |
| RIFE 4.26 ×2 / RIFE 4.6 ×4 / RIFE ×3 (không tiếng) | 48 / 96 / 72 fps, thời lượng giữ nguyên (±1 khung) |
| DeH264 + OpenProteus 2x + RIFE ×2 | 2560×1068 @ 48 fps (16 s); chuyển cảnh = "mean" |
| SCUNet + DeH264 | 1280×534; PSNR so với gốc khoảng 35 dB, tức là model thực sự thay đổi ảnh |
| Metadata xoay 90° | 1068×2560 (đúng chiều dọc) |
| VFR (độ lệch timestamp 26 ms) | Chuyển sang CFR, ×2 thành 48 fps |
| SAR 2:1 (640×534 anamorphic) | 2560×1068 (đúng tỷ lệ hiển thị) |
| HDR10 tagged (HEVC 10-bit PQ/BT.2020) | Xuất HEVC 10-bit, giữ cờ HDR |
| MKV + Opus + phụ đề SRT | MP4 H.264 + AAC, bỏ phụ đề (có cảnh báo) |
| Xử lý thử 10 giây từ giây thứ 2,5 | Đúng đoạn, đúng thời lượng |
| File hỏng / file bị cắt / file giả `.mp4` | Bị từ chối (`not_media`), không lộ đường dẫn |

### Đồng bộ âm thanh

Video thử có chớp sáng và tiếng bíp cùng lúc ở giây 1 và 3. Độ lệch tiếng − hình (ms):

| File | Giây 1 | Giây 3 |
| --- | --- | --- |
| Gốc | 2,7 | 8,0 |
| Upscale | 2,7 | 8,0 |
| Xoay + upscale | 2,7 | 8,0 |

Hai giá trị khác 0 của file gốc là sai số của bộ đo, không phải lệch thật.

Với RIFE ×2, khung gốc chớp sáng nằm đúng ở 1,000 s. Khung nội suy tại điểm chuyển cảnh là bản sao của khung kế tiếp chứ không phải khung trộn, cho thấy phát hiện chuyển cảnh hoạt động.

### Giao diện (Edge headless, staging)

- Tải lên theo phần, phân tích, tính kế hoạch, xử lý thử, hoàn tất, so sánh.
- Khi phát, độ lệch giữa hai video trong khung so sánh là 10–20 ms (dưới 1 khung).
- Không cuộn ngang ở các độ rộng 390, 820 và 1440 px. Không có lỗi JavaScript.

### Test tự động

`tests_hub/test_video_workspace.py`: 8 test dùng RVE giả, kèm 1 test GPU thật (bật bằng `VIDEO_GPU_TEST=1`). Các test bao gồm:
- tải lên theo phần, sai vị trí phần, file giả, vượt dung lượng;
- quyền chủ sở hữu, Range;
- kiểm tra cấu hình (model lạ, sai loại model, hệ số 2.5, tham số ffmpeg lạ);
- đủ các giai đoạn và đầu ra đúng;
- huỷ job diệt cả cây tiến trình và dọn file tạm;
- crash (CUDA OOM) và treo được phát hiện trong dưới 30 giây;
- khởi động lại: chạy lại một lần, sau đó báo `interrupted`;
- giới hạn hàng đợi;
- dọn file hết hạn.

## Giới hạn hiện tại

- Chỉ chạy backend PyTorch CUDA. TensorRT và NCNN chưa bật (chưa kiểm thử với torch 2.14).
- HDR được xử lý bằng chế độ HDR của RVE và xuất HEVC 10-bit. Nhiều trình duyệt không phát được HEVC, nhưng file vẫn tải xuống được. Màu HDR chỉ kiểm tra ở mức metadata, chưa đo bằng mắt trên màn HDR.
- Video SDR 10-bit được xử lý ở 8-bit (có cảnh báo). Phụ đề không được giữ.
- Hệ số nội suy chỉ là số nguyên. Từ 24 fps lên đúng 60 fps là không làm được (24 × 2,5).
- Một video job giữ GPU độc quyền. Trong lúc đó Whisper, Nét Ảnh và các công cụ dùng LLM phải xếp hàng chờ.
