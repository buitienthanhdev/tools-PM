# Thành phần bên thứ ba của Video Workspace

Không thành phần nào dưới đây nằm trong git của PM Tools. Tất cả được cài bằng `scripts/setup_video_workspace.py`, ghim phiên bản và kiểm tra.

## REAL-Video-Enhancer (backend xử lý)

- Nguồn: https://github.com/TNTwise/REAL-Video-Enhancer
- Commit: `8541c46ca14e6f84fc86c5b9d3b75373e25732e5` (2026-09-01, "Update README.md"; backend version 2.4.1). Không có submodule.
- Vị trí: `modules/video_workspace/vendor/real-video-enhancer/` (gitignore). **Không sửa mã upstream**: script cài đặt từ chối nếu `git status` có thay đổi.
- Giấy phép: **GNU AGPL-3.0**. File `LICENSE` của upstream giữ nguyên trong thư mục vendor.
  - PM Tools chỉ gọi CLI `backend/rve-backend.py` như một chương trình riêng, qua tiến trình con với tham số dòng lệnh. Không import, không liên kết, không sửa.
  - Trang `/video` ghi rõ tên, giấy phép, link mã nguồn và commit đang chạy.
  - Nếu sau này **sửa** mã RVE thì theo AGPL §13 phải cung cấp mã nguồn bản đã sửa cho mọi người dùng tương tác qua mạng.
  - Nên có ý kiến pháp lý trước khi dùng thương mại.
- Phần dùng: CLI backend (PyTorch). **Không dùng** giao diện desktop (PySide6), Discord RPC, trình cập nhật hay trình tải model của GUI.

## Môi trường Python riêng (`D:\tools PM\venvs\video`)

Cài theo `requirements-video.txt` (torch 2.14.1+cu130, torchvision 0.29.1+cu130, numpy 2.5.2, opencv-python-headless 5.0.0.93, scenedetect 0.7.2, einops, safetensors…).

- Tách khỏi venv của Hub để không đổi phiên bản thư viện mà các công cụ khác đang dùng.
- Requirements của upstream ghim torch 2.7.0 bản cu126, không có kernel cho RTX 5090 (sm_120). Vì vậy dùng bản cu130 đã kiểm thử.
- Không dùng TensorRT: torch_tensorrt 2.7 của upstream không tương thích torch 2.14.

## ffmpeg / ffprobe

- 7.1.1 essentials build của gyan.dev, tải qua https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip
- SHA-256 file zip: `04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4`
- Giấy phép: GPL-3.0 (bản build có libx264/libx265). Chạy như chương trình riêng, không phân phối lại.

## Model (`D:\tools PM\venvs\video-models`)

- Chỉ dùng các model trong `catalog.py`.
- Tải từ bản phát hành chính thức mà ứng dụng RVE tự dùng (https://github.com/TNTwise/real-video-enhancer-models/releases/tag/models) và kiểm tra SHA-256 trước khi dùng.
- Người dùng không đưa được model khác vào.

| Model | Giấy phép | Ghi chú |
| --- | --- | --- |
| RIFE 4.26, 4.6 | MIT (hzwer/Practical-RIFE) | |
| Real-ESRGAN General v3 4x | BSD-3-Clause (xinntao/Real-ESRGAN) | |
| Nomos8k SPAN 4x | CC BY 4.0 theo trang của tác giả | chưa đối chiếu file giấy phép |
| **OpenProteus 2x** | **CC BY-NC 4.0** (Sirosky/Upscale-Hub) | **phi thương mại** |
| **AnimeJaNai V3 2x** | **CC BY-NC-SA 4.0** (the-database/mpv-AnimeJaNai) | **phi thương mại** |
| DeH264 SPAN 1x | CC BY 4.0 (Phhofm/models) | |
| SCUNet | Apache-2.0 (cszn/SCUNet) | |
| DRUNet | MIT (cszn/DPIR) | |
| NAFNet GoPro | MIT (megvii-research/NAFNet) | |

Nếu dùng thương mại, đặt `"video": {"allow_noncommercial_models": false}`. Khi đó các preset sẽ tự đổi sang Real-ESRGAN 4x.
