"""
Bộ quy tắc pháp lý có phiên bản. Mỗi quy tắc ghi căn cứ, kỳ hiệu lực, mức độ triển khai và test kiểm chứng.

Căn cứ đã được đối chiếu với văn bản trong kho pháp luật local (modules/legal_rag, data/legal/kb.json)
ngày 2026-10-23. implementation_status nói rõ phần nào CHƯA được chuyên gia xác nhận —
hệ thống không tuyên bố tuân thủ pháp luật.
"""

from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    legal_source: str
    legal_reference: str
    effective_from: str
    effective_to: str | None
    rule_version: str
    applicability: str
    implementation_status: str  # IMPLEMENTED | PARTIAL | ARITHMETIC_ONLY | NEEDS_EXPERT_REVIEW
    validation_test: str


RULES = [
    Rule(
        "R-DE-BALANCE", "Bút toán kép: tổng Nợ = tổng Có theo đồng tiền hạch toán",
        "Luật Kế toán 88/2015/QH13", "Nguyên tắc ghi sổ kép; TT 99/2025/TT-BTC Điều 11",
        "2016-01-01", None, "1", "Mọi bút toán", "IMPLEMENTED",
        "tests_hub/test_accounting_engine.py::test_unbalanced_entry_rejected",
    ),
    Rule(
        "R-CORR-REVERSAL", "Không sửa/xoá bút toán đã ghi sổ; sửa bằng bút toán đảo (ghi số âm) rồi ghi lại",
        "Luật Kế toán 88/2015/QH13", "Điều 27 khoản 1 điểm b (ghi số âm)",
        "2016-01-01", None, "1", "Bút toán đã ghi sổ", "IMPLEMENTED",
        "tests_hub/test_accounting_engine.py::test_posted_entry_immutable_and_reversal",
    ),
    Rule(
        "R-PERIOD-LOCK", "Không ghi sổ vào kỳ đã khoá sổ",
        "Thông tư 99/2025/TT-BTC", "Điều 13 (mở sổ, ghi sổ và khoá sổ kế toán)",
        "2026-01-01", None, "1", "Doanh nghiệp áp dụng TT 99/2025", "IMPLEMENTED",
        "tests_hub/test_accounting_engine.py::test_locked_period_rejected",
    ),
    Rule(
        "R-COA-TT99", "Hệ thống tài khoản kế toán doanh nghiệp",
        "Thông tư 99/2025/TT-BTC (thay thế TT 200/2014/TT-BTC)", "Điều 11, Phụ lục II",
        "2026-01-01", None, "1", "Năm tài chính bắt đầu từ/sau 01/01/2026",
        "NEEDS_EXPERT_REVIEW",  # Phụ lục II không có trong kho local; danh mục khởi tạo cần đối chiếu
        "tests_hub/test_accounting_engine.py::test_coa_seeded_and_marked_unverified",
    ),
    Rule(
        "R-INV-REQUIRED", "Hoá đơn phải có các nội dung bắt buộc (ký hiệu mẫu số, ký hiệu, số, ngày, người bán, MST, tiền)",
        "Nghị định 123/2020/NĐ-CP (sửa đổi bởi NĐ 70/2025/NĐ-CP)", "Điều 10",
        "2022-07-01", None, "1", "Hoá đơn điện tử/giấy trong nước", "PARTIAL",
        "tests_hub/test_accounting_extract.py::test_invoice_missing_fields_flagged",
    ),
    Rule(
        "R-VAT-ARITH", "Tiền thuế GTGT = giá tính thuế × thuế suất (dung sai làm tròn theo dòng)",
        "Luật Thuế GTGT 48/2024/QH15", "Điều 7, Điều 11 khoản 1 điểm b",
        "2025-07-01", None, "1", "Hoá đơn GTGT theo phương pháp khấu trừ", "ARITHMETIC_ONLY",
        "tests_hub/test_accounting_extract.py::test_vat_inconsistency_flagged",
    ),
    Rule(
        "R-VAT-RATES", "Thuế suất ghi trên hoá đơn thuộc tập 0%, 5%, 10%; 8% là thuế suất giảm theo chính sách có thời hạn",
        "Luật Thuế GTGT 48/2024/QH15; các NĐ giảm thuế (VD 180/2024/NĐ-CP)", "Điều 9",
        "2025-07-01", None, "1", "Hoá đơn GTGT",
        "NEEDS_EXPERT_REVIEW",  # hiệu lực mức 8% theo từng kỳ chưa được cấu hình → luôn đưa vào kiểm duyệt
        "tests_hub/test_accounting_extract.py::test_reduced_vat_rate_needs_review",
    ),
    Rule(
        "R-INV-WORDS", "Tổng tiền thanh toán bằng chữ tiếng Việt phải khớp bằng số",
        "Nghị định 123/2020/NĐ-CP (sửa đổi bởi NĐ 70/2025/NĐ-CP)", "Điều 10 (tổng tiền thanh toán bằng chữ số Ả-rập và bằng chữ)",
        "2022-07-01", None, "1", "Hoá đơn bằng đồng Việt Nam", "IMPLEMENTED",
        "tests_hub/test_accounting_extract.py::test_amount_in_words_mismatch_flagged",
    ),
    Rule(
        "R-INV-TAXID", "Mã số thuế đúng cấu trúc và chữ số kiểm tra",
        "Cấu trúc mã số thuế (thuật toán chữ số kiểm tra — thư viện python-stdnum stdnum.vn.mst)",
        "Chưa đối chiếu văn bản quy định cấu trúc MST trong kho local",
        "2022-07-01", None, "1", "MST 10 hoặc 13 chữ số", "NEEDS_EXPERT_REVIEW",
        "tests_hub/test_accounting_extract.py::test_invalid_tax_id_flagged",
    ),
    Rule(
        "R-INV-CORRECTION", "Hoá đơn điều chỉnh/thay thế phải tham chiếu hoá đơn gốc",
        "Nghị định 123/2020/NĐ-CP (sửa đổi bởi NĐ 70/2025/NĐ-CP)", "Điều 19",
        "2022-07-01", None, "1", "Hoá đơn điện tử", "PARTIAL",
        "tests_hub/test_accounting_extract.py::test_adjustment_invoice_links_original",
    ),
]

_BY_ID = {r.rule_id: r for r in RULES}


def get(rule_id):
    return _BY_ID[rule_id]


def applicable(rule_id, on_date=None):
    r = _BY_ID[rule_id]
    d = (on_date or date.today().isoformat())[:10]
    return r.effective_from <= d and (r.effective_to is None or d <= r.effective_to)


def as_dicts():
    return [asdict(r) for r in RULES]
