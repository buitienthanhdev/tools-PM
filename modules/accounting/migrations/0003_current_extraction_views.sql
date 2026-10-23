-- Khi parser được nâng phiên bản, file được trích xuất lại; bản cũ đánh dấu SUPERSEDED (không xoá, giữ lịch sử).
-- Các view cur_* chỉ chứa dữ liệu từ bản trích xuất hiện hành — mọi truy vấn phân tích dùng view này.
CREATE VIEW cur_documents AS SELECT d.* FROM documents d JOIN extractions e ON e.id = d.extraction_id WHERE e.status IN ('OK','PARTIAL');
CREATE VIEW cur_invoices AS SELECT i.* FROM invoices i JOIN cur_documents d ON d.id = i.document_id;
CREATE VIEW cur_bank_transactions AS SELECT b.* FROM bank_transactions b JOIN cur_documents d ON d.id = b.document_id;
CREATE VIEW cur_imported_entries AS SELECT e.* FROM imported_entries e JOIN cur_documents d ON d.id = e.document_id;
