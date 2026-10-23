"""
Accounting AI (AAAP) — module kế toán tự động của PM Tools Hub, phục vụ tại /accounting.

Ba lớp tách bạch (docs/accounting/architecture.md):
- AI Reasoning: agent/planner.py — chỉ hiểu yêu cầu và lập kế hoạch từ công cụ đã đăng ký.
- Deterministic Accounting: engine/, extract/, reports/ — mọi phép tính tiền, đối soát, kiểm tra.
- Execution & Governance: agent/runner.py, jobs.py, security.py, audit.py — thực thi, phân quyền,
  phê duyệt, nhật ký.
"""
