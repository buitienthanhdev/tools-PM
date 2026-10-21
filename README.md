# PM Tools Hub

Bộ công cụ AI chạy trên máy chủ GPU riêng, phục vụ tại `https://sonxit.io.vn`.

| Công cụ | Route | Chạy bằng |
| --- | --- | --- |
| Whisper Speech AI | `/Whisper` | OpenAI Whisper (cần ffmpeg, đã gói qua `imageio-ffmpeg`) |
| VoxCPM Voice AI | `/VoxCPM` | VoxCPM2 (`core/voxengine.py`, không cần gradio) |
| Nét Ảnh AI | `/Image` | Real-ESRGAN ncnn-vulkan (`modules/image_enhancer/bin`) |
| Báo cáo tiến độ | `/genreport` | Ollama (`models.genreport`) + mẫu Word |
| AI Tư vấn pháp luật | `/legal` | RAG lai: BM25 + vector (Ollama) → AI local trả lời có đánh số căn cứ |
| SpaceT | `/SpaceT` | God's Eye View (cổng riêng + tunnel riêng, xem `modules/spacet/README.md`) |
| Reviewing CV | `/reviewingCV` | Ollama (`models.cv`) + quy tắc ai-job-search |

## Cấu trúc

```
app.py            khởi tạo Flask, gắn blueprint
server.py         chạy production (waitress, 127.0.0.1:5000)
watchdog.py       giám sát server + tunnel + SpaceT
core/             config, auth (tài khoản/phân quyền), gpu (hàng đợi GPU), jobs, llm (Ollama), voxengine
routes/           speech (whisper+vox), image, genreport, jobs, system (health, uploads, SPA)
whisper/          mã Whisper (từ openai/whisper, MIT) đã tích hợp vào dự án
voxcpm/           mã VoxCPM (từ openbmb/VoxCPM, Apache-2.0) đã tích hợp vào dự án
modules/          legal_rag, reviewingcv, spacet, image_ai, image_enhancer
static/           giao diện (Webfolio style): index.html, js/, layouts/, modules/, styles/
tests_hub/        kiểm thử Hub:  pytest -q
scripts/          crawl/ingest luật, bảo trì (maintenance.py: xoay log + sao lưu)
THIRD_PARTY_LICENSES/  giấy phép và ghi công các thành phần mã nguồn mở được dùng
```

## Image Workspace

`/Image` cung cấp crop theo phần trăm, xoay/lật, preset màu, độ sáng, tương phản,
bão hòa, sắc độ, blur, hoàn tác/làm lại, so sánh trước/sau và xuất PNG/JPEG/WebP.
Ảnh đầu vào hỗ trợ PNG, JPEG, WebP và BMP.
Các chỉnh sửa và preview mặc định chạy trong trình duyệt; không tải ảnh lên máy
chủ khi chỉ mở/chỉnh/xuất. Giới hạn hiện tại: 50 MB và 32 megapixel mỗi ảnh.
PNG/WebP giữ alpha; JPEG được ghép lên nền trắng.

Real-ESRGAN là tác vụ máy chủ tùy chọn. Người dùng phải đồng ý rõ ràng rồi bấm
“Chạy Real-ESRGAN”; ảnh đã chỉnh sửa sẽ được gửi đến PM Tools. Máy chủ dùng mô
hình ncnn-vulkan đã cấu hình trong `data/config.json` và lưu ảnh tạm theo
`upload_ttl_hours`. Không gửi ảnh đến nhà cung cấp AI bên thứ ba.

Để chạy kiểm thử upload và xác thực ảnh: `pytest tests_hub/test_image_processing.py -q`.
NextGenUp đã được
đánh giá ở commit `d265edb6c30ce532c0558a073bd86f1bc77b52c3` (MIT). Các mô-đun
BiRefNet, LaMa, SCUNet, NAFNet, DDColor và GFPGAN của nguồn cần ONNX Runtime,
OpenCV và các model riêng; chưa được tích hợp vào Hub.

## Tài khoản & phân quyền

- Đăng ký → trạng thái **chờ duyệt** → admin duyệt và tick công cụ được dùng (`/admin`).
- Admin duy nhất: `tienthanh18082003@gmail.com`. Lần đầu, đăng ký email này kèm **mã cài đặt** trong
  `data/admin_setup_code.txt` (file tự xoá sau khi tạo admin). Đổi email admin: `PM_ADMIN_EMAIL`
  hoặc `admin_email` trong `data/config.json`.
- Dữ liệu: `data/users.json` (mật khẩu băm scrypt), khoá phiên `data/secret.key`. **Không commit hai file này.**
- Mọi `/api/*` (trừ đăng nhập và `/api/health`) và `/uploads/*` đều yêu cầu đăng nhập; tác vụ chỉ chủ của nó
  và admin xem được. Đăng nhập sai 5 lần bị khoá 5 phút.
- Giới hạn đã biết: trang SpaceT là một tên miền riêng (`spacet.sonxit.io.vn`), lớp đăng nhập của Hub
  chỉ chặn việc *mở trang* trong Hub, không chặn người biết thẳng địa chỉ đó.

## Cấu hình

Thứ tự ưu tiên: mặc định → `data/config.json` → biến môi trường.

| Khoá `config.json` | Biến môi trường | Mặc định |
| --- | --- | --- |
| `ollama_url` | `PM_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `models.genreport` | `PM_MODEL_GENREPORT` | `qwen3.8:27b` |
| `models.legal` | `LEGAL_LLM_MODEL` | `gemma4:31b` |
| `models.embed` | `PM_MODEL_EMBED` | `qwen3-embedding:0.6b` |
| `legal_min_similarity` | | `0.35` (dưới ngưỡng này trả lời "chưa có căn cứ", không gọi AI) |
| `models.cv` | `CV_OLLAMA_MODEL` | `gemma4:31b` |
| `genreport_template` | | trống = `templates/report_template.docx` |
| `upload_ttl_hours` | | `24` (file tạm trong `uploads/` tự xoá) |

Legal và Reviewing CV dùng model hội thoại local dùng chung `gemma4:31b` (tag Ollama của Gemma 4 31B). GenReport giữ model chuyên dụng `qwen3.8:27b`; truy xuất pháp luật giữ model embedding chuyên dụng `qwen3-embedding:0.6b`.

## GPU

GPU 16 GB không đủ cho mọi model cùng lúc. `core/gpu.py` cho **mỗi lúc chỉ một tác vụ nặng chạy**, các tác vụ
khác xếp hàng ("Đang chờ đến lượt dùng GPU"). Khi đổi loại model (Whisper ↔ VoxCPM ↔ Ollama ↔ Real-ESRGAN)
VRAM của loại cũ được giải phóng. Trang `/admin` hiện GPU đang chạy gì và tình trạng từng công cụ
(`/api/health/tools`).

## Khởi động lại

`kill_tools.ps1` rồi `start_tools.bat` (chạy PowerShell quyền Administrator vì watchdog chạy bằng quyền admin).
Watchdog tự bật lại server nếu chết. Nhật ký: `logs/server.log`, `logs/watchdog.log`.

## Cài lại Real-ESRGAN (máy mới)

`python scripts/install_realesrgan.py` (tải khoảng 45 MB, cần card đồ hoạ hỗ trợ Vulkan).

## RAG pháp luật (`modules/legal_rag`)

1. **Nạp:** làm sạch (bỏ số trang/đầu trang lặp, nối dòng bị ngắt) → tách theo Chương/Mục/Điều/Khoản
   (Điều dài tự tách theo Khoản, mỗi đoạn mang tiêu đề Điều) → báo cảnh báo nếu văn bản có vẻ OCR vỡ.
   Văn bản trùng nội dung bị từ chối. Admin: trang Pháp luật → biểu tượng khoá.
2. **Tìm kiếm lai:** BM25 (từ + cặp từ + bản bỏ dấu) và vector `qwen3-embedding`, hợp nhất bằng RRF. Vector
   lưu cache theo nội dung (`data/legal/vec_*.npy`). Câu hỏi **không dấu** giảm trọng số vector.
3. **Câu hỏi nối tiếp** ("vậy nếu quá 40 ngày?") được AI viết lại thành câu độc lập trước khi tìm.
4. **Trả lời:** AI chỉ được dùng các căn cứ đã tìm, mỗi nhận định phải kèm `[n]`. Dưới ngưỡng tương đồng thì
   nói thẳng chưa có căn cứ, không gọi AI.
5. **Kiểm chứng:** giao diện cảnh báo khi câu trả lời không trích dẫn căn cứ nào, hoặc nhắc tới Điều không
   nằm trong căn cứ đã tìm được. Chú thích `[n]` bấm được để mở đúng căn cứ.

Đo chất lượng: `pytest tests_hub/test_legal_rag.py -s` (văn bản hư cấu, in recall@3, top-1 của BM25 so với lai).

## Kho vector pháp luật

`modules/legal_rag/vecstore.py` gộp vector embedding thành `data/legal/vectors.npy` + `vectors.json`
(manifest theo từng văn bản). Đổi nội dung hoặc model embedding thì chỉ văn bản đó được tính lại. Các
file `vec_*.npy` cũ được tự động gộp vào kho ở lần chạy đầu tiên.

## Kiểm thử và CI

```
pip install -r requirements.txt pytest ruff
ruff check .
pytest -q
```

GitHub Actions (`.github/workflows/ci.yml`) chạy cùng hai lệnh trên Python 3.12 với torch CPU.
