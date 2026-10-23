# ADR-0002 SQLite (WAL) cho giai đoạn đầu

**Bối cảnh.** Không có PostgreSQL trên máy chủ; cài thêm dịch vụ cần phê duyệt vận hành. Tải dự kiến: một máy chủ, ít người dùng đồng thời.

**Quyết định.** SQLite WAL, `synchronous=FULL`, `foreign_keys=ON`, migration đánh số (`migrations/*.sql`), giao dịch `BEGIN IMMEDIATE`.
Bất biến đặt trong DB: UNIQUE (idempotency, file theo hash), CHECK (vai trò, trạng thái), trigger chặn UPDATE/DELETE sổ cái,
nhật ký kiểm toán, dòng bút toán đã ghi sổ, danh tính file gốc. Tiền: TEXT thập phân, tính bằng `Decimal`.

**Hệ quả / giới hạn.** Một máy ghi; không mở rộng ngang. Schema dùng kiểu dữ liệu chuyển được sang Postgres (TEXT/INTEGER/REAL,
FK, UNIQUE); trigger cần viết lại bằng PL/pgSQL khi chuyển. Sao lưu: `sqlite3 .backup` (xem deployment.md).
