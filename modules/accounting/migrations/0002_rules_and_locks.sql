-- Quy tắc hạch toán nội bộ (Organization Knowledge): chỉ có hiệu lực khi được người thứ hai phê duyệt.
CREATE TABLE account_rules (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  match_type TEXT NOT NULL CHECK (match_type IN ('seller_tax_id','buyer_tax_id','keyword')),
  match_value TEXT NOT NULL,
  account_code TEXT NOT NULL,
  note TEXT,
  status TEXT NOT NULL CHECK (status IN ('PROPOSED','ACTIVE','REJECTED','RETIRED')),
  proposed_by TEXT NOT NULL, proposed_at REAL NOT NULL,
  decided_by TEXT, decided_at REAL,
  source_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_rules_org ON account_rules(org_id, status);

-- Dòng bút toán đã ghi sổ không được sửa/xoá (sửa bằng bút toán đảo)
CREATE TRIGGER jl_no_update_posted BEFORE UPDATE ON journal_lines
WHEN (SELECT status FROM journal_entries WHERE id = OLD.entry_id) IN ('POSTED','REVERSED')
BEGIN SELECT RAISE(ABORT, 'journal_lines of posted entry are immutable'); END;
CREATE TRIGGER jl_no_delete_posted BEFORE DELETE ON journal_lines
WHEN (SELECT status FROM journal_entries WHERE id = OLD.entry_id) IN ('POSTED','REVERSED')
BEGIN SELECT RAISE(ABORT, 'journal_lines of posted entry are immutable'); END;
CREATE TRIGGER je_no_delete_posted BEFORE DELETE ON journal_entries
WHEN OLD.status IN ('POSTED','REVERSED')
BEGIN SELECT RAISE(ABORT, 'posted journal entry cannot be deleted'); END;
CREATE TRIGGER je_posted_only_to_reversed BEFORE UPDATE OF status ON journal_entries
WHEN OLD.status = 'POSTED' AND NEW.status <> 'REVERSED'
BEGIN SELECT RAISE(ABORT, 'posted entry can only become REVERSED'); END;
CREATE TRIGGER je_posted_fields_frozen BEFORE UPDATE OF entry_date, description, currency, idempotency_key ON journal_entries
WHEN OLD.status IN ('POSTED','REVERSED')
BEGIN SELECT RAISE(ABORT, 'posted journal entry is immutable'); END;

-- File gốc: không cho đổi nội dung định danh
CREATE TRIGGER files_identity_frozen BEFORE UPDATE OF sha256, storage_path, size ON files
BEGIN SELECT RAISE(ABORT, 'original file identity is immutable'); END;
CREATE TRIGGER files_no_delete BEFORE DELETE ON files
BEGIN SELECT RAISE(ABORT, 'original files cannot be deleted by the application'); END;
