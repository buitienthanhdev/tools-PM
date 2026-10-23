/* Accounting AI — gọi API, upload theo lô, định dạng. Không đổi tiền sang float trong trình duyệt. */

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export class ApiError extends Error {
  constructor(msg, status, code, data) { super(msg); this.status = status; this.code = code; this.data = data; }
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const res = await fetch(`/api/accounting${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error || `HTTP ${res.status}`, res.status, data.code, data);
  return data;
}

/** Tải file theo lô (mặc định 8 file/lô) để request ngắn; onProgress(sentBytes, totalBytes, doneFiles). */
export async function uploadFiles(org, files, conversationId, onProgress, batch = 8) {
  const total = files.reduce((s, f) => s + f.size, 0);
  let sentBefore = 0;
  const results = [];
  const fileIds = [];
  for (let i = 0; i < files.length; i += batch) {
    const chunk = files.slice(i, i + batch);
    const fd = new FormData();
    chunk.forEach((f) => fd.append('files', f, f.name));
    if (conversationId) fd.append('conversation_id', conversationId);
    const data = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `/api/accounting/o/${org}/files`);
      xhr.upload.onprogress = (e) => onProgress?.(sentBefore + e.loaded, total, i);
      xhr.onload = () => {
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch { /* bỏ qua */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(d);
        else reject(new ApiError(d.error || `HTTP ${xhr.status}`, xhr.status, d.code, d));
      };
      xhr.onerror = () => reject(new ApiError('Mất kết nối khi tải file', 0));
      xhr.send(fd);
    });
    sentBefore += chunk.reduce((s, f) => s + f.size, 0);
    results.push(...data.results);
    fileIds.push(...data.file_ids);
    onProgress?.(sentBefore, total, Math.min(i + batch, files.length));
  }
  return { results, fileIds };
}

/** "1234567.5" → "1.234.567,5" (định dạng VN) trên chuỗi, không qua float. */
export function money(v, scale = null) {
  if (v === null || v === undefined || v === '') return '';
  let s = String(v).trim();
  if (!/^-?\d+(\.\d+)?$/.test(s)) return esc(s);
  const neg = s.startsWith('-');
  if (neg) s = s.slice(1);
  let [int, frac = ''] = s.split('.');
  if (scale !== null) frac = frac.padEnd(scale, '0').slice(0, scale);
  int = int.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${neg ? '-' : ''}${int}${frac ? ',' + frac : ''}`;
}

export const date = (iso) => (iso && /^\d{4}-\d{2}-\d{2}/.test(iso) ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : esc(iso ?? ''));
export const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '');
export const bytes = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);

const OK = ['COMPLETED', 'VERIFIED', 'MATCHED_EXACT', 'MATCHED_VERIFIED', 'POSTED', 'OK', 'CLEAN', 'stored', 'RESOLVED', 'EXECUTED', 'APPROVED', 'ACTIVE', 'REVIEWED', 'VALID_EXTRACTED'];
const WARN = ['PARTIALLY_COMPLETED', 'NEEDS_REVIEW', 'NEEDS_EVIDENCE', 'NEEDS_INPUT', 'POTENTIAL_MATCH', 'AMBIGUOUS', 'WAITING_FOR_INPUT', 'WAITING_FOR_APPROVAL',
  'PROPOSED', 'PENDING', 'PARTIAL', 'NOT_SCANNED', 'duplicate', 'RETRY_SCHEDULED', 'OPEN', 'EXTRACTED', 'UNKNOWN'];
const BAD = ['FAILED', 'CONFLICTED', 'UNMATCHED', 'REJECTED', 'CANCELLED', 'rejected', 'INFECTED', 'ERROR', 'REVERSED'];
const RUN = ['RUNNING', 'QUEUED', 'CREATED', 'VALIDATING', 'VERIFYING'];

export const VN = {
  COMPLETED: 'Hoàn thành', PARTIALLY_COMPLETED: 'Hoàn thành một phần', FAILED: 'Lỗi', CANCELLED: 'Đã huỷ', RUNNING: 'Đang chạy',
  QUEUED: 'Đang chờ', CREATED: 'Mới tạo', VALIDATING: 'Đang kiểm tra', VERIFYING: 'Đang xác minh', RETRY_SCHEDULED: 'Sẽ thử lại',
  WAITING_FOR_INPUT: 'Cần thông tin', WAITING_FOR_APPROVAL: 'Chờ phê duyệt', VERIFIED: 'Đã xác minh', VALID_EXTRACTED: 'Hợp lệ (văn bản)',
  NEEDS_REVIEW: 'Cần kiểm duyệt', NEEDS_EVIDENCE: 'Thiếu chứng cứ', CONFLICTED: 'Mâu thuẫn', REVIEWED: 'Đã kiểm duyệt', NEEDS_INPUT: 'Cần bổ sung',
  PENDING: 'Chờ', PROPOSED: 'Đề xuất', POSTED: 'Đã ghi sổ', REVERSED: 'Đã đảo', MATCHED_EXACT: 'Khớp chính xác',
  MATCHED_VERIFIED: 'Khớp có bằng chứng', POTENTIAL_MATCH: 'Có thể khớp', AMBIGUOUS: 'Mơ hồ', UNMATCHED: 'Chưa khớp', EXTRACTED: 'Đã trích xuất',
  UNKNOWN: 'Chưa rõ', OPEN: 'Đang mở', RESOLVED: 'Đã xử lý', DISMISSED: 'Bỏ qua', EXECUTED: 'Đã thực hiện', REJECTED: 'Từ chối',
};

export function status(s) {
  const cls = OK.includes(s) ? 'ok' : WARN.includes(s) ? 'warn' : BAD.includes(s) ? 'bad' : RUN.includes(s) ? 'run' : '';
  return `<span class="ac-status ${cls}">${esc(VN[s] || s || '—')}</span>`;
}

export const TERMINAL = ['COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED', 'WAITING_FOR_INPUT'];
