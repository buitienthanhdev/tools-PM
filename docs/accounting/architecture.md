# Kiến trúc AAAP trong PM Tools

Modular monolith: module Flask `modules/accounting` gắn vào Hub, có DB, kho file, hàng đợi và worker riêng.
Người dùng truy cập thống nhất tại `https://sonxit.io.vn/accounting` (SPA của Hub) và API `/api/accounting/*`.

```
Trình duyệt (/accounting)                       Cloudflare Tunnel → waitress :5000 (Hub)
 ├─ Workspace: kéo thả → lệnh → timeline → báo cáo    ├─ core/auth: đăng nhập, quyền công cụ "accounting"
 ├─ Chứng từ, Báo cáo, Kiểm duyệt, Phê duyệt          └─ modules/accounting/api.py (chỉ gắn khi accounting.enabled)
 └─ Inspector: xem gốc, bằng chứng, phiên bản               │  security.context(): thành viên + vai trò (ADMIN…VIEWER)
                                                            ▼
 ingest/  sniff (magic bytes) → Defender → SHA-256 → trùng → kho bất biến → ZIP an toàn
 extract/ XML hoá đơn (lxml, chống XXE) · PDF (PyMuPDF, toạ độ) · OCR (EasyOCR GPU) · Excel/CSV/DOCX/JSON
          → documents + fields(provenance) + invoices + bank_transactions + imported_entries
 engine/  validate (Decimal) · duplicates · reconcile · journal (bút toán kép, phê duyệt) · analysis · workbook · rules
 agent/   planner (Ollama + JSON schema, dự phòng quy tắc) → policy → tools(registry) → runner(state machine)
 reports/ spec → Excel (openpyxl, công thức) / PDF (PyMuPDF Story) → verify (mở lại, đối chiếu Decimal)
 jobs.py  hàng đợi SQLite + worker thread (lease, khôi phục, backoff)
 db.py    SQLite WAL, migrations/*.sql, trigger chặn sửa sổ cái/nhật ký · audit.py chuỗi băm
```

## Ba lớp (PHẦN I)

| Lớp | Thành phần | Không bao giờ |
| --- | --- | --- |
| AI Reasoning | `agent/planner.py` | Tính tiền, kết luận kế toán, đọc nội dung chứng từ (chỉ thấy tên file + số đếm) |
| Deterministic Accounting | `engine/`, `extract/`, `reports/` | Dùng float cho tiền; đoán khi dữ liệu mơ hồ (AMBIGUOUS/UNKNOWN thay vì bịa) |
| Execution & Governance | `agent/runner.py`, `agent/policy.py`, `jobs.py`, `security.py`, `audit.py`, `engine/journal.py` | Cho agent ghi sổ; cho tài liệu nâng quyền |

## Luồng một tác vụ

1. `POST /conversations/<id>/messages` → task `CREATED → VALIDATING → QUEUED` (file phải thuộc tổ chức).
2. Worker nhận (lease) → `RUNNING`: bước cố định `inspect_files`, `extract_documents` (cache theo phiên bản parser).
3. Planner nhận yêu cầu + manifest (số hoá đơn, giao dịch, bảng…) → kế hoạch; `planner._sanitize` kiểm tra tên công cụ, schema tham số, policy, artifact thuộc hội thoại.
4. Từng bước chạy, kết quả ghi `task_steps.output_json` (checkpoint), sự kiện ghi `task_events` (UI thăm dò 1,5 s).
5. `generate_excel` dựng spec từ các sheet của các bước, ghi file, **mở lại và xác minh**; không đạt ⇒ task FAILED.
6. `VERIFYING → COMPLETED | PARTIALLY_COMPLETED` (còn câu hỏi/bước lỗi) `| FAILED`. Tin nhắn kết quả được tổng hợp xác định từ đầu ra công cụ (AI không viết số liệu).

## Dữ liệu

- `data/accounting/aaap.db` = danh bạ trung tâm (tổ chức, thành viên); `data/accounting/tenants/<org_id>.db` = database riêng của từng tổ chức (SQLite WAL, `synchronous=FULL`); `objects/<org>/<sha2>/<sha256>` (bản gốc chỉ-đọc), `artifacts/<org>/<id>.xlsx|pdf`. Xem ADR-0006.
- Mọi bảng nghiệp vụ có `org_id`; truy vấn luôn lọc `org_id`. Tiền là TEXT thập phân, tính bằng `Decimal`.
- Provenance (`fields`): file_id, hash, trang, sheet/ô, toạ độ hoặc XPath, phương pháp, phiên bản parser, model, độ tin cậy, trạng thái.

## Trạng thái giá trị

`VERIFIED` (XML + kiểm tra chéo đạt) · `VALID_EXTRACTED` (PDF có chữ, kiểm tra đạt) · `EXTRACTED` · `NEEDS_REVIEW` (OCR luôn ở đây) ·
`NEEDS_EVIDENCE` · `CONFLICTED` · `UNKNOWN`. Đối soát: `MATCHED_EXACT/VERIFIED`, `POTENTIAL_MATCH`, `AMBIGUOUS`, `UNMATCHED`, `CONFLICTED`.
