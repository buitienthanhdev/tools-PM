# Reviewing CV — /reviewingCV

Chấm CV theo một tin tuyển dụng, dùng bộ quy tắc của
[MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search) (MIT, commit `407dc34`).

| Thành phần | Vị trí |
| --- | --- |
| Bộ quy tắc (rút gọn từ repo gốc) | `knowledge/` · giấy phép: `../../THIRD_PARTY_LICENSES/` |
| Đọc quy tắc + gọi AI local (Ollama) | `engine.py` |
| API `/api/cv/status`, `/api/cv/review`, `/api/cv/jobs/<id>` | `api.py`, đăng ký trong `app.py` |
| Giao diện | `../../static/modules/reviewingcv/reviewingcvModule.js`, đăng ký trong `static/js/main.js` |

Repo gốc là một bộ lệnh cho Claude Code, không phải web app. Hub chỉ giữ 3 file quy tắc,
đọc trực tiếp từ `knowledge/`:

- `04-job-evaluation.md`: cổng điều kiện, cổng ngôn ngữ, 5 tiêu chí chấm, trọng số, ngưỡng
- `05-cv-templates.md`: sửa từng mục CV, ATS, giới hạn 2 trang, cắt theo mức liên quan
- `03-writing-style.md`: văn phong (cho đề xuất sửa và thư xin việc)

Sửa các file này rồi khởi động lại Hub để đổi cách chấm.
Điểm tổng và kết luận tính ở server theo trọng số 30/25/15/30 của repo.

## Cấu hình và kiểm tra chất lượng

Chạy hoàn toàn trên máy bằng Ollama (qua `core/llm.py`, xếp hàng GPU chung), không cần API key.
Model chọn ở `models.cv` trong `data/config.json` (mặc định `gemma4:12b`; `qwen3.8:27b` chính xác hơn
nhưng chậm hơn nhiều trên GPU 16 GB).

- Cùng đầu vào cho cùng điểm (nhiệt độ thấp + `seed` cố định).
- **Kiểm tra sau-AI** (`check_edits`): mỗi đề xuất sửa được gắn cảnh báo nếu (a) đoạn "cũ" không có nguyên văn
  trong CV, (b) chữ mới có từ khoá/số liệu CV không hề nhắc tới (vd. thêm "SAFe" khi CV không có),
  (c) làm mất số liệu thật. Cảnh báo hiện màu vàng dưới từng đề xuất; người dùng quyết định.
