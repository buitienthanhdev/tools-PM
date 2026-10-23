-- AAAP schema v1. Tiền lưu TEXT dạng thập phân chuẩn (Decimal), không dùng REAL.
-- Mọi bảng nghiệp vụ mang org_id; truy vấn luôn lọc theo org_id ở tầng repository.

CREATE TABLE orgs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  tax_id TEXT,
  base_currency TEXT NOT NULL DEFAULT 'VND',
  accounting_regime TEXT NOT NULL DEFAULT 'TT99_2025',
  created_by TEXT NOT NULL,
  created_at REAL NOT NULL
);

CREATE TABLE org_members (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  user_email TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN','ACCOUNTANT','REVIEWER','APPROVER','AUDITOR','VIEWER')),
  added_by TEXT NOT NULL,
  added_at REAL NOT NULL,
  PRIMARY KEY (org_id, user_email, role)
);
CREATE INDEX ix_members_user ON org_members(user_email);

CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  created_by TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX ix_conv_org ON conversations(org_id, updated_at);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  role TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content TEXT NOT NULL,
  task_id TEXT,
  created_by TEXT,
  created_at REAL NOT NULL
);
CREATE INDEX ix_msg_conv ON messages(conversation_id, created_at);

-- File gốc bất biến, định danh theo nội dung trong từng tổ chức
CREATE TABLE files (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  sha256 TEXT NOT NULL,
  size INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  kind TEXT NOT NULL,
  mime TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  parent_file_id TEXT REFERENCES files(id),
  archive_path TEXT,
  scan_status TEXT NOT NULL,
  status TEXT NOT NULL,
  error_json TEXT,
  uploaded_by TEXT NOT NULL,
  uploaded_at REAL NOT NULL,
  UNIQUE (org_id, sha256)
);

CREATE TABLE uploads (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  file_id TEXT REFERENCES files(id),
  conversation_id TEXT REFERENCES conversations(id),
  original_name TEXT NOT NULL,
  duplicate_of_existing INTEGER NOT NULL DEFAULT 0,
  outcome TEXT NOT NULL,
  error_json TEXT,
  uploaded_by TEXT NOT NULL,
  uploaded_at REAL NOT NULL
);
CREATE INDEX ix_uploads_conv ON uploads(conversation_id);

CREATE TABLE extractions (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  file_id TEXT NOT NULL REFERENCES files(id),
  parser TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  status TEXT NOT NULL,
  error_json TEXT,
  stats_json TEXT,
  text_content TEXT,
  created_at REAL NOT NULL,
  UNIQUE (file_id, parser, parser_version)
);

CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  file_id TEXT NOT NULL REFERENCES files(id),
  extraction_id TEXT NOT NULL REFERENCES extractions(id),
  doc_type TEXT NOT NULL,
  title TEXT,
  data_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX ix_docs_file ON documents(file_id);

-- Provenance cho từng giá trị trích xuất
CREATE TABLE fields (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  document_id TEXT NOT NULL REFERENCES documents(id),
  file_id TEXT NOT NULL REFERENCES files(id),
  source_file_hash TEXT NOT NULL,
  field_name TEXT NOT NULL,
  extracted_value TEXT,
  normalized_value TEXT,
  confidence REAL NOT NULL,
  extraction_method TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  model_id TEXT,
  source_page INTEGER,
  sheet_name TEXT,
  cell_reference TEXT,
  source_location_json TEXT,
  validation_status TEXT NOT NULL,
  extracted_at REAL NOT NULL
);
CREATE INDEX ix_fields_doc ON fields(document_id);

CREATE TABLE invoices (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  document_id TEXT NOT NULL REFERENCES documents(id),
  file_id TEXT NOT NULL REFERENCES files(id),
  source_format TEXT NOT NULL,
  form_no TEXT, series TEXT, number TEXT,
  issue_date TEXT,
  seller_tax_id TEXT, seller_name TEXT,
  buyer_tax_id TEXT, buyer_name TEXT,
  currency TEXT, fx_rate TEXT,
  subtotal TEXT, vat_amount TEXT, total TEXT,
  invoice_kind TEXT NOT NULL DEFAULT 'original',
  related_invoice TEXT,
  authority_code TEXT,
  business_key TEXT,
  direction TEXT NOT NULL DEFAULT 'unknown',
  status TEXT NOT NULL,
  issues_json TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL
);
CREATE INDEX ix_inv_org_key ON invoices(org_id, business_key);

CREATE TABLE invoice_lines (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  invoice_id TEXT NOT NULL REFERENCES invoices(id),
  line_no INTEGER NOT NULL,
  description TEXT, unit TEXT,
  quantity TEXT, unit_price TEXT, amount TEXT,
  vat_rate TEXT, vat_amount TEXT
);

CREATE TABLE bank_transactions (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  document_id TEXT NOT NULL REFERENCES documents(id),
  file_id TEXT NOT NULL REFERENCES files(id),
  account_no TEXT,
  txn_date TEXT,
  description TEXT,
  reference TEXT,
  debit TEXT, credit TEXT,
  amount TEXT NOT NULL,
  currency TEXT,
  balance TEXT,
  counterparty TEXT,
  row_ref TEXT NOT NULL
);

-- Bút toán/sổ quỹ nhập từ file (dữ liệu nguồn để đối soát), không phải sổ cái của hệ thống
CREATE TABLE imported_entries (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  document_id TEXT NOT NULL REFERENCES documents(id),
  file_id TEXT NOT NULL REFERENCES files(id),
  entry_date TEXT,
  doc_no TEXT,
  description TEXT,
  account TEXT,
  amount TEXT NOT NULL,
  counterparty TEXT,
  row_ref TEXT NOT NULL
);

CREATE TABLE accounts (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  acct_type TEXT NOT NULL,
  normal_side TEXT NOT NULL CHECK (normal_side IN ('D','C','DC')),
  parent_code TEXT,
  postable INTEGER NOT NULL DEFAULT 1,
  regime TEXT NOT NULL,
  verification TEXT NOT NULL,
  PRIMARY KEY (org_id, code)
);

CREATE TABLE periods (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','locked')),
  locked_by TEXT, locked_at REAL,
  UNIQUE (org_id, start_date)
);

CREATE TABLE journal_entries (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  entry_date TEXT NOT NULL,
  description TEXT NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('DRAFT','PROPOSED','APPROVED','POSTED','REVERSED','REJECTED')),
  source TEXT NOT NULL,
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  task_id TEXT,
  reversal_of TEXT REFERENCES journal_entries(id),
  idempotency_key TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL, created_at REAL NOT NULL,
  posted_by TEXT, posted_at REAL,
  UNIQUE (org_id, idempotency_key)
);

CREATE TABLE journal_lines (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  entry_id TEXT NOT NULL REFERENCES journal_entries(id),
  line_no INTEGER NOT NULL,
  account_code TEXT NOT NULL,
  debit TEXT NOT NULL DEFAULT '0',
  credit TEXT NOT NULL DEFAULT '0',
  counterparty TEXT,
  memo TEXT,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  UNIQUE (entry_id, line_no)
);

-- Sổ cái chỉ được ghi khi bút toán POSTED (triggers chặn sửa/xoá)
CREATE TABLE ledger_entries (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  entry_id TEXT NOT NULL REFERENCES journal_entries(id),
  line_id TEXT NOT NULL REFERENCES journal_lines(id) UNIQUE,
  entry_date TEXT NOT NULL,
  account_code TEXT NOT NULL,
  debit TEXT NOT NULL,
  credit TEXT NOT NULL,
  posted_at REAL NOT NULL
);
CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger_entries
BEGIN SELECT RAISE(ABORT, 'ledger_entries is append-only'); END;
CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger_entries
BEGIN SELECT RAISE(ABORT, 'ledger_entries is append-only'); END;

CREATE TABLE approvals (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED','EXECUTED')),
  requested_by TEXT NOT NULL, requested_at REAL NOT NULL,
  decided_by TEXT, decided_at REAL,
  reason TEXT
);
CREATE INDEX ix_appr_org ON approvals(org_id, status);

CREATE TABLE review_items (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  task_id TEXT,
  kind TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  title TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('OPEN','RESOLVED','DISMISSED')),
  created_at REAL NOT NULL,
  resolved_by TEXT, resolved_at REAL,
  resolution_json TEXT,
  UNIQUE (org_id, kind, target_type, target_id)
);

CREATE TABLE feedback (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  user_email TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  field_name TEXT,
  old_value TEXT, new_value TEXT,
  note TEXT,
  status TEXT NOT NULL DEFAULT 'RECORDED',
  created_at REAL NOT NULL
);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  conversation_id TEXT REFERENCES conversations(id),
  created_by TEXT NOT NULL,
  command TEXT NOT NULL,
  file_ids_json TEXT NOT NULL,
  status TEXT NOT NULL,
  plan_json TEXT,
  plan_source TEXT,
  summary_json TEXT,
  error_json TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  not_before REAL NOT NULL DEFAULT 0,
  lease_until REAL,
  worker_id TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX ix_tasks_status ON tasks(status, not_before);
CREATE INDEX ix_tasks_org ON tasks(org_id, created_at);

CREATE TABLE task_steps (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  task_id TEXT NOT NULL REFERENCES tasks(id),
  seq INTEGER NOT NULL,
  tool TEXT NOT NULL,
  goal TEXT NOT NULL,
  params_json TEXT NOT NULL,
  depends_json TEXT NOT NULL,
  task_class TEXT NOT NULL,
  risk TEXT NOT NULL,
  approval_required INTEGER NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  started_at REAL, finished_at REAL,
  output_json TEXT,
  error_json TEXT,
  UNIQUE (task_id, seq)
);

CREATE TABLE task_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id TEXT NOT NULL,
  task_id TEXT NOT NULL REFERENCES tasks(id),
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  message TEXT NOT NULL,
  data_json TEXT
);
CREATE INDEX ix_events_task ON task_events(task_id, id);

CREATE TABLE artifacts (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  task_id TEXT REFERENCES tasks(id),
  conversation_id TEXT,
  root_id TEXT NOT NULL,
  parent_id TEXT REFERENCES artifacts(id),
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  spec_json TEXT,
  sha256 TEXT NOT NULL,
  size INTEGER NOT NULL,
  storage_path TEXT NOT NULL,
  validation_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at REAL NOT NULL,
  UNIQUE (root_id, version)
);

CREATE TABLE reconciliations (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  task_id TEXT,
  summary_json TEXT NOT NULL,
  created_at REAL NOT NULL
);

CREATE TABLE recon_matches (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  recon_id TEXT NOT NULL REFERENCES reconciliations(id),
  status TEXT NOT NULL,
  bank_ids_json TEXT NOT NULL,
  entry_ids_json TEXT NOT NULL,
  score REAL NOT NULL,
  reasons_json TEXT NOT NULL
);

-- Nhật ký kiểm toán chuỗi băm, chỉ thêm
CREATE TABLE audit_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  org_id TEXT,
  ts REAL NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  details_json TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL
);
CREATE INDEX ix_audit_org ON audit_events(org_id, seq);
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
