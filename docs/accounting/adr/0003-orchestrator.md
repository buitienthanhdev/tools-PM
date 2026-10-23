# ADR-0003 Orchestrator tự xây, mỏng, trên tool registry có kiểu

**Bối cảnh.** Đặc tả đề xuất DeerFlow nếu phù hợp. Kiểm tra README DeerFlow (2026-10-23): khuyến nghị Linux + Docker cho server,
Windows chỉ đánh giá; cần Node 22 + Python + LangGraph + sandbox container; mục tiêu “super agent” (nghiên cứu, shell, MCP).

**Ba phương án.**
1. DeerFlow làm dịch vụ riêng — không có Docker/Linux; mặc định cho phép bash/file-write trong sandbox ⇒ trái nguyên tắc không chạy lệnh do AI sinh.
2. LangGraph trực tiếp — thêm dependency lớn, không giải quyết vấn đề chính (chính sách, xác minh, provenance).
3. **Chọn:** planner nhỏ trên `core/llm` sẵn có (Ollama, JSON schema ràng buộc tên công cụ) + registry 21 công cụ xác định + policy engine + runner có state machine.

**Lý do.** Phần khó của bài toán là quản trị (quyền, phê duyệt, xác minh, truy vết), không phải điều phối LLM. Planner chỉ chọn công cụ;
mọi tính toán nằm trong công cụ đã kiểm thử. LLM lỗi ⇒ circuit breaker ⇒ planner theo quy tắc (hệ thống vẫn hoạt động khi AI tắt).

**Hệ quả.** Năng lực giới hạn ở các công cụ đã đăng ký; yêu cầu ngoài phạm vi ⇒ “unsupported”/câu hỏi, không ứng biến.
Đánh giá lại DeerFlow khi có máy chủ Linux + Docker và nhu cầu nghiên cứu mở.
