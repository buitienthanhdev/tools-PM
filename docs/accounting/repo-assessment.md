# Phase 0 — Đánh giá repository

Ngày khảo sát: 2026-10-23. Bằng chứng: đọc mã nguồn PM Tools; GitHub API (`gh api repos/...`) cho repo upstream.

## 1. PM Tools hiện tại

| Hạng mục | Thực tế đã kiểm tra |
| --- | --- |
| Stack | Python 3.12, Flask 3.1 + waitress (`server.py`, 127.0.0.1:5000), SPA vanilla JS (ES modules, không build step) |
| Hosting | Windows 11 Pro, GPU RTX 5090 32 GB; Cloudflare Tunnel `sonxit.io.vn → 127.0.0.1:5000`; `watchdog.py` tự khởi động lại server |
| Xác thực | `core/auth.py`: user lưu `data/users.json` (scrypt), cookie phiên ký, phân quyền theo công cụ, khoá 5 phút sau 5 lần sai |
| AI | Ollama local (`qwen3.8:27b` có tool-calling, `gemma4:31b`, `qwen3-embedding`); `core/gpu.py` xếp hàng GPU trong tiến trình |
| Thư viện có sẵn dùng lại | openpyxl 3.1.5, lxml 6.1, PyMuPDF 2.0, pypdf, python-docx, EasyOCR 1.7 (model `latin_g2` có tiếng Việt), numpy |
| Không có | Docker, PostgreSQL, Redis, LibreOffice/Excel (không có engine tính lại công thức) |
| Có thể dùng | Microsoft Defender (`MpCmdRun.exe`) để quét file; Node 24 (chỉ dùng cho kiểm thử UI) |
| Kiểm thử | pytest + ruff, GitHub Actions. Baseline trước thay đổi: 25 pass / 3 fail (3 test cần binary Real-ESRGAN bị gitignore, không có trong worktree) |
| Lưu ý vận hành | `static/` được phục vụ trực tiếp từ đĩa ⇒ sửa file trong thư mục production = lên production ngay. Vì vậy phát triển trong git worktree riêng `D:\tools PM\aaap-dev` (branch `feature/accounting`) |
| Trạng thái git | Thư mục production đang ở branch `copilot/image-workspace` với 2 file sửa dở chưa commit (`core/llm.py`, `modules/legal_rag/engine.py`) — không đụng tới |

## 2. Repo upstream

| Repo | License (GitHub API) | Duy trì | Kết luận |
| --- | --- | --- | --- |
| bytedance/deer-flow | MIT | push 2026-10-23, 84k★ | Không dùng giai đoạn này: README khuyến nghị Linux + Docker cho server, Windows chỉ để đánh giá; Node 22 + Python + sandbox container; phạm vi “super agent” rộng hơn nhu cầu. Xem ADR-0003 |
| langgenius/dify | Apache-2.0 sửa đổi | hoạt động | Không dùng: cấm vận hành đa tenant nếu không có giấy phép thương mại |
| n8n-io/n8n | Sustainable Use License | hoạt động | Không dùng: không phải OSI; workflow cố định không phù hợp agent |
| opendatalab/MinerU | Apache-2.0 + điều khoản thương mại theo ngưỡng | hoạt động | Ứng viên adapter tương lai cho PDF phức tạp; nặng (model riêng) |
| docling-project/docling | MIT | hoạt động | **Đã tích hợp** làm dự phòng cho bảng PDF không kẻ ô, chạy trong venv riêng `venvs/docai` qua tiến trình con |
| PaddlePaddle/PaddleOCR | Apache-2.0 | hoạt động | **Đã tích hợp** làm OCR dự phòng khi EasyOCR không nhận diện được (venv riêng; `enable_mkldnn=False` trên CPU) |
| jsvine/pdfplumber | MIT | hoạt động | **Đã tích hợp**: bảng dòng hàng hoá đơn PDF, sao kê PDF |
| arthurdejong/python-stdnum | LGPL-2.1+ | hoạt động | **Đã tích hợp**: kiểm tra chữ số kiểm tra MST (`stdnum.vn.mst`); dùng như thư viện, không sửa mã |
| savoirfairelinux/num2words | LGPL-2.1 | hoạt động | **Đã tích hợp**: đối chiếu tổng tiền bằng chữ tiếng Việt; dùng như thư viện |
| rapidfuzz/RapidFuzz | MIT | hoạt động | **Đã tích hợp**: so khớp mờ tên đối tác khi đối soát, sửa nhãn OCR |
| python-excel/xlrd | BSD | duy trì tối thiểu | **Đã tích hợp**: đọc .xls (chỉ giá trị đã lưu) |
| open-telemetry/opentelemetry-python | Apache-2.0 | hoạt động | **Đã tích hợp**: span cho tác vụ/công cụ/trích xuất, xuất JSONL cục bộ |
| paperless-ngx | GPL-3.0 | hoạt động | Ứng dụng hoàn chỉnh, GPL — không nhúng |
| invoice-x/invoice2data | MIT | hoạt động | Ý tưởng template theo nhãn được áp dụng; không thêm dependency vì hoá đơn VN có XML chuẩn |
| frappe/erpnext | GPL-3.0 | hoạt động | ERP đầy đủ, MariaDB — ngoài phạm vi; có thể làm adapter xuất dữ liệu sau |
| beancount/beancount | GPL-2.0 | hoạt động | Không nhúng (copyleft); tự xây engine bút toán kép nhỏ, kiểm thử đầy đủ |
| jmcnamara/XlsxWriter | BSD-2 | hoạt động | Không cần: chỉ ghi; openpyxl (MIT, có sẵn) vừa đọc vừa ghi |
| exceljs/exceljs | MIT | push cuối 2025-01 | Không dùng (JavaScript, chậm duy trì) |
| ClosedXML/ClosedXML | MIT | hoạt động | Không dùng (.NET) |

docling và PaddleOCR **không** cài vào venv của Hub vì sẽ hạ huggingface-hub (2.2→1.33), numpy (2.5.4→2.3.5) và thêm opencv-contrib, làm hỏng Whisper/VoxCPM/Real-ESRGAN. Thiếu venv `venvs/docai` thì module tự bỏ qua hai bộ dự phòng này.

Rủi ro license đã có từ trước: **PyMuPDF là AGPL-3.0** (Hub đang dùng cho module pháp luật). Module kế toán dùng PyMuPDF để lấy toạ độ và vẽ trang bằng chứng — ghi trong risk-register R-09.

## 3. Văn bản pháp luật đã kiểm tra (kho local `data/legal/kb.json`)

- **TT 99/2025/TT-BTC** — chế độ kế toán doanh nghiệp, hiệu lực 01/01/2026, thay TT 200/2014 (Điều 31). Phụ lục II (hệ thống tài khoản) **không có** trong kho ⇒ danh mục tài khoản đánh dấu chưa đối chiếu.
- Luật Kế toán 88/2015 Điều 27 (sửa sổ: ghi số âm ↔ bút toán đảo); NĐ 123/2020 Điều 10, 19 (nội dung hoá đơn, xử lý sai sót; sửa đổi bởi NĐ 70/2025); Luật Thuế GTGT 48/2024 Điều 7, 9, 11.
- Chưa có trong kho: văn bản giảm thuế GTGT 8% áp dụng cho kỳ hiện tại ⇒ hoá đơn 8% luôn vào kiểm duyệt.
