"""
Tool registry. AI chỉ được gọi công cụ trong registry; mỗi công cụ khai báo:
capability, input/output schema, lớp tác vụ, quyền, side effect, timeout, idempotency, hành vi lỗi.

Không có công cụ chạy shell hoặc chạy mã do AI sinh ra (docs/accounting/adr/0004-no-generated-code.md).
Đầu ra công cụ: {"summary", "data", "sections"(sheet báo cáo), "warnings"} — mọi dòng có "_src".
"""

import re
from dataclasses import dataclass, field

from .. import db, extract, money, storage
from ..engine import analysis, duplicates, journal, proposals, reconcile, tabular, workbook
from ..extract.base import fold
from . import review
from .schema import validate

# Lớp tác vụ (PHẦN VI 6.2)
READ_ONLY = "READ_ONLY"
TRANSFORM = "TRANSFORM"
GENERATE_ARTIFACT = "GENERATE_ARTIFACT"
PROPOSE = "PROPOSE_ACCOUNTING_ENTRY"
WRITE_DRAFT = "WRITE_INTERNAL_DRAFT"
COMMIT = "COMMIT_ACCOUNTING"
EXTERNAL = "EXTERNAL_ACTION"


class ToolInputError(Exception):
    """Tham số sai / thiếu dữ liệu — không thử lại."""


class NeedsInput(Exception):
    def __init__(self, question, details=None):
        super().__init__(question)
        self.details = details or {}


@dataclass
class Tool:
    name: str
    description: str
    task_class: str
    params: dict
    handler: object
    permission: str = "run_task"
    side_effects: str = "none"
    timeout_s: int = 600
    idempotency: str = "pure"
    failure: str = "fail_step"
    risk: str = "low"
    produces_sections: bool = True
    output: dict = field(default_factory=lambda: {"type": "object", "required": ["summary"]})


REGISTRY = {}


def tool(**kw):
    def deco(fn):
        REGISTRY[kw["name"]] = Tool(handler=fn, **kw)
        return fn
    return deco


def obj(props=None, required=()):
    return {"type": "object", "properties": props or {}, "required": list(required), "additionalProperties": False}


def check_params(name, params):
    t = REGISTRY.get(name)
    if not t:
        raise ToolInputError(f"Công cụ không tồn tại: {name}")
    validate(params or {}, t.params)
    return t


def catalog():
    return [{"name": t.name, "description": t.description, "class": t.task_class, "params": t.params,
             "side_effects": t.side_effects, "risk": t.risk} for t in REGISTRY.values()]


# ── tiện ích ─────────────────────────────────────────────────────
def _src(file_id, loc=None):
    return [[file_id, loc]]


def _m(v):
    return money.fmt(v) if v is not None else None


def _direction_param(run, direction):
    """Lọc theo chiều mua/bán chỉ khi biết MST tổ chức; nếu không → không lọc, cảnh báo và hỏi lại (không trả rỗng âm thầm).
    AI bỏ trống tham số nhưng câu lệnh nói rõ "mua vào"/"bán ra" → theo câu lệnh."""
    if direction in (None, ""):
        f = fold(run.task["command"])
        buy = any(w in f for w in ("mua vao", "dau vao"))
        sell = any(w in f for w in ("ban ra", "dau ra"))
        direction = "purchase" if buy and not sell else "sale" if sell and not buy else None
    if direction not in ("sale", "purchase"):
        return None
    if not run.org.get("tax_id"):
        run.warn("Chưa khai báo MST của tổ chức nên không phân biệt được hoá đơn mua vào / bán ra — đã xử lý tất cả hoá đơn")
        run.ask("Hãy khai báo mã số thuế của tổ chức (Cài đặt) để hệ thống phân biệt hoá đơn mua vào và bán ra.")
        return None
    return direction


def _check_org_relation(run, invs):
    """Hoá đơn không có MST tổ chức ở bên bán lẫn bên mua → nói rõ thay vì trả kết quả rỗng âm thầm."""
    if not invs or not run.org.get("tax_id"):
        return
    unrelated = [i for i in invs if i["direction"] == "unrelated"]
    if len(unrelated) == len(invs):
        run.warn(f"Không hoá đơn nào có MST của tổ chức ({run.org['tax_id']}) ở bên bán hoặc bên mua")
        run.ask(f"MST của tổ chức trong Cài đặt là {run.org['tax_id']}, nhưng không hoá đơn nào mang MST này. "
                "Hãy kiểm tra lại MST, hoặc xác nhận đây là hoá đơn của đơn vị khác.")
    elif unrelated:
        run.warn(f"{len(unrelated)}/{len(invs)} hoá đơn không có MST của tổ chức — không tính là mua vào hay bán ra")


def _files(run, kinds=None):
    rows = run.files()
    return [f for f in rows if not kinds or f["kind"] in kinds]


# ── Công cụ ──────────────────────────────────────────────────────
@tool(name="inspect_files", description="Liệt kê chứng từ của tác vụ: định dạng thật, kích thước, kết quả quét, cảnh báo.",
      task_class=READ_ONLY, params=obj())
def inspect_files(run, p):
    rows = []
    for f in run.files():
        meta = db.loads(f["error_json"], {}) or {}
        rows.append({"file": f["original_name"], "kind": f["kind"], "size": f["size"], "scan": f["scan_status"],
                     "sha256": f["sha256"], "warnings": "; ".join(meta.get("warnings") or []), "_src": _src(f["id"])})
    return {"summary": f"{len(rows)} chứng từ trong phạm vi tác vụ", "data": {"count": len(rows)},
            "sections": [{"name": "Chứng từ", "title": "Danh sách chứng từ đầu vào", "columns": [
                {"key": "file", "label": "File"}, {"key": "kind", "label": "Định dạng"},
                {"key": "size", "label": "Kích thước (byte)", "type": "number"}, {"key": "scan", "label": "Quét virus"},
                {"key": "warnings", "label": "Cảnh báo"}, {"key": "sha256", "label": "SHA-256"}], "rows": rows}]}


@tool(name="extract_documents", description="Trích xuất dữ liệu có cấu trúc từ mọi chứng từ (PDF, OCR, XML hoá đơn, Excel, CSV, DOCX) kèm provenance.",
      task_class=TRANSFORM, params=obj(), timeout_s=3600, idempotency="cached_by_parser_version",
      failure="continue_other_files", side_effects="writes extraction records (internal, idempotent)")
def extract_documents(run, p):
    rows, ok, failed = [], 0, 0
    files = run.files()
    for i, f in enumerate(files, start=1):
        run.progress(f"Đang đọc {f['original_name']} ({i}/{len(files)})", i, len(files))
        try:
            e = extract.ensure(run.ctx.org_id, f["id"], run.org.get("tax_id"), actor=run.ctx.user)
        except extract.ExtractError as ex:
            e = {"status": "FAILED", "parser": "-", "error_json": db.dumps({"code": ex.code, "message": str(ex)})}
        err = db.loads(e.get("error_json"), None)
        docs = db.all_("SELECT doc_type, status FROM documents WHERE extraction_id=?", (e.get("id"),)) if e.get("id") else []
        if e["status"] in ("OK", "PARTIAL"):
            ok += 1
        else:
            failed += 1
            run.warn(f"Không trích xuất được {f['original_name']}: {(err or {}).get('message', e['status'])}")
        kinds = {}
        for d in docs:
            kinds[d["doc_type"]] = kinds.get(d["doc_type"], 0) + 1
        rows.append({"file": f["original_name"], "parser": e.get("parser"), "status": e["status"],
                     "content": ", ".join(f"{k}×{v}" for k, v in kinds.items()) or "-",
                     "error": (err or {}).get("message"), "_src": _src(f["id"])})
        run.heartbeat()
    m = run.manifest(refresh=True)
    return {"summary": f"Đã đọc {ok}/{len(files)} file; {m['invoices']} hoá đơn, {m['bank_txns']} giao dịch sao kê, "
                       f"{m['ledger_entries']} dòng sổ, {m['tables']} bảng dữ liệu" + (f"; {failed} file lỗi" if failed else ""),
            "data": {"ok": ok, "failed": failed, "manifest": m},
            "sections": [{"name": "Trích xuất", "title": "Kết quả trích xuất từng file", "columns": [
                {"key": "file", "label": "File"}, {"key": "parser", "label": "Bộ đọc"}, {"key": "status", "label": "Trạng thái"},
                {"key": "content", "label": "Nội dung nhận diện"}, {"key": "error", "label": "Lỗi"}], "rows": rows}]}


INVOICE_COLS = [
    {"key": "number", "label": "Số HĐ"}, {"key": "series", "label": "Ký hiệu"}, {"key": "issue_date", "label": "Ngày", "type": "date"},
    {"key": "seller", "label": "Người bán"}, {"key": "seller_tax_id", "label": "MST bán"}, {"key": "buyer", "label": "Người mua"},
    {"key": "direction", "label": "Chiều"}, {"key": "currency", "label": "Tiền tệ"},
    {"key": "subtotal", "label": "Tiền hàng", "type": "money"}, {"key": "vat", "label": "Thuế GTGT", "type": "money"},
    {"key": "total", "label": "Tổng thanh toán", "type": "money"}, {"key": "status", "label": "Trạng thái"},
    {"key": "issues", "label": "Vấn đề"},
]
DIRECTION_VN = {"sale": "Bán ra", "purchase": "Mua vào", "unknown": "Chưa rõ", "unrelated": "Không liên quan"}
ST_VN = {"VERIFIED": "Hợp lệ", "VALID_EXTRACTED": "Hợp lệ (văn bản)", "REVIEWED": "Đã kiểm duyệt", "NEEDS_REVIEW": "Cần kiểm duyệt",
         "NEEDS_EVIDENCE": "Thiếu chứng cứ", "CONFLICTED": "Mâu thuẫn", "UNKNOWN": "Chưa rõ"}


def _inv_row(i):
    return {"number": i["number"], "series": i["series"], "issue_date": i["issue_date"], "seller": i["seller_name"],
            "seller_tax_id": i["seller_tax_id"], "buyer": i["buyer_name"], "direction": DIRECTION_VN.get(i["direction"], i["direction"]),
            "currency": i["currency"], "subtotal": i["subtotal"], "vat": i["vat_amount"], "total": i["total"],
            "status": i["status"], "issues": "; ".join(x["message"] for x in i["issues"]),
            "_src": _src(i["file_id"], f"hoá đơn {i['series'] or ''}/{i['number'] or ''}"), "_invoice_id": i["id"]}


@tool(name="validate_invoices", description="Kiểm tra từng hoá đơn: trường bắt buộc, số học dòng hàng, tổng, thuế GTGT theo thuế suất, hoá đơn điều chỉnh, ngoại tệ.",
      task_class=READ_ONLY, params=obj(), side_effects="creates review items (idempotent)")
def validate_invoices(run, p):
    invs = analysis.invoices(run.ctx.org_id, run.file_ids)
    rows, exc = [], []
    for i in invs:
        rows.append(_inv_row(i))
        for x in i["issues"]:
            exc.append({"invoice": f"{i['series'] or ''}/{i['number'] or '?'}", "file": i["file_name"], "rule": x["rule_id"],
                        "severity": x["severity"], "field": x["field"], "message": x["message"],
                        "expected": x.get("expected"), "actual": x.get("actual"), "_src": _src(i["file_id"])})
        if i["status"] not in analysis.VERIFIED_SET:
            review.open_item(run, "invoice_check", "invoice", i["id"],
                             f"Hoá đơn {i['series'] or ''}/{i['number'] or '?'} — {i['status']}",
                             {"issues": i["issues"], "file": i["file_name"]})
    by = {}
    for i in invs:
        by[i["status"]] = by.get(i["status"], 0) + 1
    _check_org_relation(run, invs)
    if invs:
        ok_n = sum(v for k, v in by.items() if k in analysis.VERIFIED_SET)
        parts = [f"{ok_n} hợp lệ"] + [f"{v} {ST_VN.get(k, k).lower()}" for k, v in sorted(by.items()) if k not in analysis.VERIFIED_SET]
        answer = f"Đã kiểm tra {len(invs)} hoá đơn: " + ", ".join(parts) + "."
        probs = [f"{i['series'] or ''}/{i['number'] or '?'}: {i['issues'][0]['message']}" for i in invs if i["issues"]][:5]
        if len(invs) <= 3:  # ít hoá đơn: nêu luôn nội dung chính đã đọc được
            answer += " " + " ".join(
                f"HĐ {i['series'] or ''}/{i['number'] or '?'} ngày {i['issue_date'] or '?'}, người bán {i['seller_name'] or '?'} "
                f"(MST {i['seller_tax_id'] or '?'}), tổng {money.vn(i['total']) if i['total'] else '?'} {i['currency'] or 'VND'} — "
                f"{ST_VN.get(i['status'], i['status']).lower()}" + (" (đọc bằng OCR, cần đối chiếu bản gốc)" if str(i["source_format"] or "").startswith("ocr") else "")
                + "." for i in invs)
        if probs:
            answer += " Vấn đề chính: " + "; ".join(probs) + ("…" if sum(1 for i in invs if i["issues"]) > 5 else "") + "."
    else:
        answer = "Không có hoá đơn nào trong các file của phiên này."
    return {"summary": answer, "answer": answer,
            "data": {"count": len(invs), "by_status": by},
            "sections": [{"name": "Hoá đơn", "title": "Danh sách hoá đơn và kết quả kiểm tra", "columns": INVOICE_COLS, "rows": rows},
                         {"name": "Ngoại lệ hoá đơn", "title": "Các vấn đề phát hiện trên hoá đơn", "columns": [
                             {"key": "invoice", "label": "Hoá đơn"}, {"key": "file", "label": "File"}, {"key": "rule", "label": "Quy tắc"},
                             {"key": "severity", "label": "Mức"}, {"key": "field", "label": "Trường"}, {"key": "message", "label": "Mô tả"},
                             {"key": "expected", "label": "Kỳ vọng", "type": "money"}, {"key": "actual", "label": "Thực tế", "type": "money"}],
                          "rows": exc}] if invs else []}


@tool(name="detect_duplicates", description="Phát hiện trùng file, trùng hoá đơn (theo khoá nghiệp vụ), xung đột khoá, nghi trùng, dòng sao kê trùng, nghi chi trùng.",
      task_class=READ_ONLY, params=obj(), side_effects="creates review items (idempotent)")
def detect_duplicates(run, p):
    groups = duplicates.detect(run.ctx.org_id, run.file_ids, int(run.settings["date_tolerance_days"]), run.task["conversation_id"])
    rows = []
    for gi, g in enumerate(groups, start=1):
        ev = g.get("evidence") or []
        rows.append({"group": gi, "type": g["type"], "status": g["status"], "reason": g["reason"],
                     "members": "; ".join(f"{e.get('file')} {e.get('number') or e.get('row') or ''}".strip() for e in ev) or ", ".join(g.get("file_ids", [])),
                     "_src": [[e.get("file_id") or _file_id_by_name(run, e.get("file")), e.get("row")] for e in ev][:5]})
        if g["status"] != "DUPLICATE" or g["type"] == "INVOICE_DUPLICATE":
            target = (g.get("invoice_ids") or g.get("bank_ids") or g.get("file_ids") or ["?"])
            review.open_item(run, f"dup_{g['type'].lower()}", "group", "|".join(sorted(target)), g["reason"][:200], g)
    names = {"FILE_DUPLICATE": "file tải trùng", "INVOICE_DUPLICATE": "hoá đơn trùng", "INVOICE_KEY_CONFLICT": "hoá đơn trùng số nhưng khác tiền",
             "INVOICE_SUSPECTED": "nghi trùng hoá đơn", "ROW_DUPLICATE": "dòng sao kê lặp", "SUSPECTED_DOUBLE_PAYMENT": "nghi chi trùng"}
    by_type = {}
    for g in groups:
        by_type[g["type"]] = by_type.get(g["type"], 0) + 1
    dup_txt = ("Trùng lặp: " + ", ".join(f"{v} {names.get(k, k)}" for k, v in by_type.items()) + " (chi tiết ở sheet 'Trùng lặp').") if groups \
        else "Không phát hiện trùng lặp."
    return {"summary": dup_txt, "answer": dup_txt,
            "data": {"groups": len(groups), "types": sorted({g['type'] for g in groups})},
            "sections": [{"name": "Trùng lặp", "title": "Trùng lặp và nghi vấn (không kết luận trùng chỉ vì cùng số tiền)", "columns": [
                {"key": "group", "label": "Nhóm", "type": "number"}, {"key": "type", "label": "Loại"}, {"key": "status", "label": "Trạng thái"},
                {"key": "reason", "label": "Lý do"}, {"key": "members", "label": "Thành phần"}], "rows": rows}]}


def _file_id_by_name(run, name):
    for f in run.files():
        if f["original_name"] == name:
            return f["id"]
    return None


@tool(name="summarize_invoices", description="Tổng hợp hoá đơn theo nhà cung cấp/khách hàng và theo thuế suất GTGT (chỉ cộng hoá đơn đã kiểm tra; loại bản trùng).",
      task_class=TRANSFORM, params=obj({"direction": {"type": "string", "enum": ["sale", "purchase", "all"]}}))
def summarize_invoices(run, p):
    rows_all = analysis.invoices(run.ctx.org_id, run.file_ids)
    _check_org_relation(run, rows_all)
    direction = _direction_param(run, p.get("direction"))
    if direction:
        rows_all = [r for r in rows_all if r["direction"] == direction]
    dups = duplicates.detect(run.ctx.org_id, run.file_ids)
    rows, dropped = analysis.dedupe_for_totals(rows_all, dups)
    if dropped:
        run.warn(f"Đã loại {len(dropped)} hoá đơn trùng khỏi phép cộng (giữ bản XML nếu có)")
    s = analysis.summarize_invoices(rows)
    if s["unverified_invoice_ids"]:
        run.warn(f"{len(s['unverified_invoice_ids'])} hoá đơn chưa qua kiểm tra không được cộng vào tổng")
    cp_rows = [{"counterparty": c["counterparty"], "tax_id": c["tax_id"], "direction": DIRECTION_VN.get(c["direction"], c["direction"]),
                "currency": c["currency"], "count": c["count"], "unverified": c["unverified_count"],
                "subtotal": _m(c["subtotal"]), "vat": _m(c["vat"]), "total": _m(c["total"])} for c in s["by_counterparty"]]
    vat_rows = [{"rate": v["rate"], "direction": DIRECTION_VN.get(v["direction"], v["direction"]), "currency": v["currency"],
                 "count": v["count"], "taxable": _m(v["taxable"]), "vat": _m(v["vat"])} for v in s["vat_breakdown"]]
    currencies = sorted(s["totals_by_currency"])
    multi = len(currencies) > 1
    if multi:
        run.warn(f"Có nhiều loại tiền ({', '.join(currencies)}) — tổng được tách theo loại tiền, không cộng lẫn")
    sections = [{"name": "Theo đối tượng", "title": "Tổng hợp hoá đơn theo nhà cung cấp / khách hàng", "columns": [
        {"key": "counterparty", "label": "Đối tượng"}, {"key": "tax_id", "label": "MST"}, {"key": "direction", "label": "Chiều"},
        {"key": "currency", "label": "Tiền tệ"}, {"key": "count", "label": "Số HĐ", "type": "number"},
        {"key": "unverified", "label": "Chưa kiểm tra", "type": "number"}, {"key": "subtotal", "label": "Tiền hàng", "type": "money"},
        {"key": "vat", "label": "Thuế GTGT", "type": "money"}, {"key": "total", "label": "Tổng", "type": "money"}],
        "rows": cp_rows, "totals": [] if multi else ["subtotal", "vat", "total"]},
        {"name": "Thuế GTGT", "title": "Thuế GTGT theo thuế suất (hoá đơn đã kiểm tra)", "columns": [
            {"key": "rate", "label": "Thuế suất"}, {"key": "direction", "label": "Chiều"}, {"key": "currency", "label": "Tiền tệ"},
            {"key": "count", "label": "Số nhóm", "type": "number"}, {"key": "taxable", "label": "Giá tính thuế", "type": "money"},
            {"key": "vat", "label": "Tiền thuế", "type": "money"}], "rows": vat_rows, "totals": [] if multi else ["taxable", "vat"]}]
    tot = {c: {k: _m(v) for k, v in t.items() if k != "count"} | {"count": t["count"]} for c, t in s["totals_by_currency"].items()}
    answers = []
    per = {}
    for c in s["by_counterparty"]:
        e = per.setdefault((c["direction"], c["currency"]), {"n": 0, "subtotal": money.ZERO, "vat": money.ZERO, "total": money.ZERO})
        e["n"] += c["count"] - c["unverified_count"]
        for k in ("subtotal", "vat", "total"):
            e[k] += c[k]
    for (d, cur), e in sorted(per.items()):
        if not e["n"]:
            continue
        what = {"purchase": "Hoá đơn mua vào", "sale": "Hoá đơn bán ra"}.get(d, f"Hoá đơn {DIRECTION_VN.get(d, d).lower()}")
        vat_word = {"purchase": "thuế GTGT đầu vào", "sale": "thuế GTGT đầu ra"}.get(d, "thuế GTGT")
        answers.append(f"{what} đã kiểm tra: {e['n']} hoá đơn, tiền hàng {money.vn(e['subtotal'])} {cur}, "
                       f"{vat_word} {money.vn(e['vat'])} {cur}, tổng thanh toán {money.vn(e['total'])} {cur}.")
    unv = [r for r in rows if r["id"] in set(s["unverified_invoice_ids"])]
    if unv:
        vat_unv = money.sum_(money.D(r["vat_amount"]) for r in unv if r["vat_amount"])
        answers.append(f"{len(unv)} hoá đơn còn vấn đề (cần kiểm duyệt/mâu thuẫn) chưa được cộng — thuế GTGT ghi trên các hoá đơn này: "
                       f"{money.vn(vat_unv)}. Xem sheet 'Theo đối tượng' và mục Kiểm duyệt.")
    if not answers:
        answers.append("Không có hoá đơn nào đã qua kiểm tra để tổng hợp" + (f" ({DIRECTION_VN[direction].lower()})" if direction else "") + ".")
    if direction == "purchase" and per:
        run.note("Số thuế GTGT đầu vào ở đây là số ghi trên hoá đơn đã kiểm tra; điều kiện khấu trừ (thanh toán không dùng tiền mặt, "
                 "hoá đơn hợp pháp…) cần kế toán xác nhận.")
    return {"summary": " ".join(answers), "answer": " ".join(answers),
            "data": {"totals_by_currency": tot, "dropped_duplicates": len(dropped)}, "sections": sections}


def _amount_vn(text):
    """'20 triệu' → 20000000; '1,5 tỷ' → 1500000000; '500k' → 500000."""
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(trieu|tr|ty|ti|nghin|ngan|k)?(?![a-z])", fold(text))
    if not m:
        return None
    num, unit = m.group(1), m.group(2)
    mult = {"trieu": 10**6, "tr": 10**6, "ty": 10**9, "ti": 10**9, "nghin": 10**3, "ngan": 10**3, "k": 10**3}.get(unit, 1)
    if unit:
        seps = re.findall(r"[.,]", num)
        if len(seps) == 1 and len(num.split(seps[0])[1]) <= 2:  # "1,5 tỷ" / "2.5 triệu": dấu thập phân
            num = num.replace(",", ".")
            return money.to_decimal(num) * mult
    p = money.parse_amount(num, "VND")
    return p.value * mult if p.status == "OK" else None


@tool(name="filter_invoices", description="Lọc hoá đơn theo ngưỡng tổng tiền (VND), khoảng ngày (yyyy-mm-dd), đối tượng, chiều mua/bán.",
      task_class=TRANSFORM, params=obj({
          "min_total": {"type": ["string", "number", "null"]}, "max_total": {"type": ["string", "number", "null"]},
          "date_from": {"type": ["string", "null"], "maxLength": 10}, "date_to": {"type": ["string", "null"], "maxLength": 10},
          "counterparty": {"type": ["string", "null"], "maxLength": 120},
          "direction": {"type": ["string", "null"], "enum": ["sale", "purchase", None]}}))
def filter_invoices(run, p):
    def amt(v):
        if v in (None, ""):
            return None
        if isinstance(v, (int, float)):
            return money.to_decimal(v)
        a = _amount_vn(str(v))
        if a is None:
            raise ToolInputError(f"Không hiểu ngưỡng tiền: {v}")
        return a

    lo, hi = amt(p.get("min_total")), amt(p.get("max_total"))
    rows = analysis.filter_invoices(analysis.invoices(run.ctx.org_id, run.file_ids), lo, hi, p.get("date_from"),
                                    p.get("date_to"), p.get("counterparty"), _direction_param(run, p.get("direction")))
    desc = []
    if lo is not None:
        desc.append(f"> {money.fmt(lo)}")
    if hi is not None:
        desc.append(f"≤ {money.fmt(hi)}")
    if p.get("date_from") or p.get("date_to"):
        desc.append(f"ngày {p.get('date_from') or '…'} → {p.get('date_to') or '…'}")
    if p.get("counterparty"):
        desc.append(f"đối tượng chứa '{p['counterparty']}'")
    if any((r["currency"] or "VND") != "VND" for r in rows) and (lo is not None or hi is not None):
        run.warn("Ngưỡng tiền so sánh theo nguyên tệ của từng hoá đơn; hoá đơn ngoại tệ không được quy đổi")
    title = "Hoá đơn " + (" ".join(desc) if desc else "(không lọc)")
    return {"summary": f"{len(rows)} hoá đơn thoả điều kiện {' '.join(desc)}".strip(), "data": {"count": len(rows), "criteria": desc},
            "sections": [{"name": "Hoá đơn đã lọc", "title": title, "columns": INVOICE_COLS, "rows": [_inv_row(r) for r in rows],
                          "totals": ["subtotal", "vat", "total"] if len({r['currency'] for r in rows}) <= 1 else []}]}


@tool(name="reconcile_bank", description="Đối soát sao kê ngân hàng với sổ kế toán/sổ quỹ (hoặc với hoá đơn nếu không có sổ). Tầng: exact, verified, potential, ambiguous, conflicted, unmatched; nhiều-một/một-nhiều.",
      task_class=TRANSFORM, params=obj({"tolerance_days": {"type": "integer", "minimum": 0, "maximum": 30},
                                        "against": {"type": "string", "enum": ["auto", "ledger", "invoices"]}}),
      side_effects="stores reconciliation result; creates review items (idempotent)")
def reconcile_bank(run, p):
    org = run.ctx.org_id
    tol = int(p.get("tolerance_days", run.settings["date_tolerance_days"]))
    scope = run.file_ids
    q = ",".join("?" for _ in scope) or "''"
    bank = db.all_(f"""SELECT b.id, b.txn_date date, b.amount, b.reference, b.description, b.counterparty, b.row_ref, b.file_id,
                       f.original_name file FROM cur_bank_transactions b JOIN files f ON f.id=b.file_id
                       WHERE b.org_id=? AND b.file_id IN ({q})""", (org, *scope))
    if not bank:
        raise NeedsInput("Không có sao kê ngân hàng trong các file đã tải lên — hãy thêm file sao kê (Excel/CSV).")
    against = p.get("against", "auto")
    book = db.all_(f"""SELECT e.id, e.entry_date date, e.amount, e.doc_no reference, e.description, e.counterparty, e.row_ref,
                       e.file_id, f.original_name file FROM cur_imported_entries e JOIN files f ON f.id=e.file_id
                       WHERE e.org_id=? AND e.file_id IN ({q})""", (org, *scope))
    mode = "ledger"
    if against == "invoices" or (against == "auto" and not book):
        mode = "invoices"
        invs = [i for i in analysis.invoices(org, scope) if i["direction"] in ("sale", "purchase")
                and i["status"] in analysis.VERIFIED_SET and (i["currency"] or "VND") == "VND"]
        invs, _ = analysis.dedupe_for_totals(invs, duplicates.detect(org, scope))
        book = [{"id": i["id"], "date": i["issue_date"], "amount": i["total"] if i["direction"] == "sale" else money.fmt(-money.D(i["total"])),
                 "reference": i["number"], "description": f"HĐ {i['series']}/{i['number']}",
                 "counterparty": analysis.counterparty_of(i)[0], "row_ref": f"HĐ {i['number']}", "file_id": i["file_id"],
                 "file": i["file_name"]} for i in invs]
        tol = max(tol, 60)  # thanh toán hoá đơn có thể cách ngày lập xa
        run.warn("Không có sổ kế toán — đối soát sao kê với hoá đơn (dung sai ngày 60)" if against == "auto" else "Đối soát với hoá đơn")
    if not book:
        raise NeedsInput("Không có sổ kế toán/sổ quỹ hoặc hoá đơn hợp lệ để đối soát với sao kê.")
    matches, summ = reconcile.reconcile(bank, book, tol)
    rid = db.new_id()
    with db.tx() as c:
        db.insert(c, "reconciliations", {"id": rid, "org_id": org, "task_id": run.task["id"],
                                         "summary_json": db.dumps({**summ, "mode": mode, "tolerance_days": tol}), "created_at": db.now()})
        for m in matches:
            db.insert(c, "recon_matches", {"id": db.new_id(), "org_id": org, "recon_id": rid, "status": m["status"],
                                           "bank_ids_json": db.dumps(m["bank"]), "entry_ids_json": db.dumps(m["book"]),
                                           "score": m["score"], "reasons_json": db.dumps(m["reasons"])})
    rows = []
    for m in matches:
        b = m["bank_rows"]
        k = m["book_rows"]
        rows.append({"status": m["status"],
                     "bank_date": ", ".join(x["date"] or "" for x in b), "bank_ref": ", ".join(x["reference"] or "" for x in b),
                     "bank_desc": " | ".join(x["description"] or "" for x in b),
                     "bank_amount": _m(money.sum_(money.D(x["amount"]) for x in b)) if b else None,
                     "book_date": ", ".join(x["date"] or "" for x in k), "book_ref": ", ".join(x["reference"] or "" for x in k),
                     "book_desc": " | ".join(x["description"] or "" for x in k),
                     "book_amount": _m(money.sum_(money.D(x["amount"]) for x in k)) if k else None,
                     "reasons": "; ".join(m["reasons"]),
                     "_src": [[x["file_id"], x["row_ref"]] for x in b + k][:6]})
        if m["status"] in ("AMBIGUOUS", "POTENTIAL_MATCH", "CONFLICTED"):
            review.open_item(run, f"recon_{m['status'].lower()}", "recon", "|".join(sorted(m["bank"] + m["book"])),
                             f"Đối soát {m['status']}: {m['reasons'][0][:150]}", {"recon_id": rid, **{k2: m[k2] for k2 in ("bank", "book", "reasons")}})
    order = ["CONFLICTED", "AMBIGUOUS", "UNMATCHED", "POTENTIAL_MATCH", "MATCHED_VERIFIED", "MATCHED_EXACT"]
    rows.sort(key=lambda r: order.index(r["status"]) if r["status"] in order else 9)
    st_rows = [{"status": k, "count": v["count"], "bank_amount": v["bank_amount"], "book_amount": v["book_amount"]}
               for k, v in sorted(summ["by_status"].items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 9)]
    side = "sổ kế toán" if mode == "ledger" else "hoá đơn"
    return {"summary": f"Đối soát {summ['bank_count']} giao dịch sao kê với {summ['book_count']} dòng {side}: " +
                       ", ".join(f"{r['status']} {r['count']}" for r in st_rows) + f"; chênh lệch {summ['difference']}",
            "data": {"reconciliation_id": rid, "mode": mode, "summary": summ},
            "sections": [
                {"name": "Đối soát - Tổng hợp", "title": f"Tổng hợp đối soát sao kê ↔ {side}", "columns": [
                    {"key": "status", "label": "Trạng thái"}, {"key": "count", "label": "Số nhóm", "type": "number"},
                    {"key": "bank_amount", "label": "Tiền sao kê", "type": "money"}, {"key": "book_amount", "label": f"Tiền {side}", "type": "money"}],
                 "rows": st_rows, "notes": [f"Tổng sao kê {summ['bank_total']}, tổng {side} {summ['book_total']}, chênh lệch {summ['difference']}.",
                                            summ["note"]]},
                {"name": "Đối soát - Chi tiết", "title": "Chi tiết so khớp và bằng chứng", "columns": [
                    {"key": "status", "label": "Trạng thái"}, {"key": "bank_date", "label": "Ngày sao kê"}, {"key": "bank_ref", "label": "Tham chiếu"},
                    {"key": "bank_desc", "label": "Diễn giải sao kê"}, {"key": "bank_amount", "label": "Tiền sao kê", "type": "money"},
                    {"key": "book_date", "label": "Ngày sổ"}, {"key": "book_ref", "label": "Số CT"}, {"key": "book_desc", "label": "Diễn giải sổ"},
                    {"key": "book_amount", "label": "Tiền sổ", "type": "money"}, {"key": "reasons", "label": "Bằng chứng / lý do"}], "rows": rows}]}


@tool(name="analyze_workbook", description="Kiểm tra workbook Excel: lỗi công thức (#REF!, #DIV/0!…), SUM bỏ sót dòng, tổng nhập tay, giá trị lưu khác giá trị tính lại, liên kết ngoài, sheet ẩn.",
      task_class=READ_ONLY, params=obj())
def analyze_workbook(run, p):
    rows, files = [], _files(run, ("xlsx", "xlsm"))
    if not files:
        raise NeedsInput("Không có file Excel (.xlsx/.xlsm) trong các file đã tải lên.")
    totals = {"errors": 0, "warnings": 0, "formulas": 0, "recalculated": 0}
    for f in files:
        try:
            a = workbook.analyze(storage.abspath(f["storage_path"]), f["original_name"])
        except Exception as e:
            run.warn(f"Không phân tích được {f['original_name']}: {type(e).__name__}")
            continue
        for k in totals:
            totals[k] += a["summary"].get(k, 0)
        for x in a["findings"]:
            rows.append({"file": f["original_name"], "sheet": x["sheet"], "cell": x["cell"], "severity": x["severity"],
                         "type": x["type"], "message": x["message"], "formula": x.get("formula"),
                         "_src": _src(f["id"], f"{x['sheet']}!{x['cell']}" if x["cell"] else x["sheet"])})
        run.note(a["recalc_scope"])
    return {"summary": f"{len(files)} workbook, {totals['formulas']} công thức ({totals['recalculated']} được tính lại): "
                       f"{totals['errors']} lỗi, {totals['warnings']} cảnh báo",
            "data": totals,
            "sections": [{"name": "Kiểm tra công thức", "title": "Kết quả kiểm tra workbook", "columns": [
                {"key": "file", "label": "File"}, {"key": "sheet", "label": "Sheet"}, {"key": "cell", "label": "Ô"},
                {"key": "severity", "label": "Mức"}, {"key": "type", "label": "Loại"}, {"key": "message", "label": "Mô tả"},
                {"key": "formula", "label": "Công thức"}], "rows": rows,
                "notes": ["Chỉ tự tính lại SUM(phạm vi) và cộng/trừ ô đơn giản; công thức khác chỉ kiểm tra cấu trúc."]}]}


@tool(name="monthly_summary", description="Tổng hợp theo tháng: thu/chi theo sổ quỹ (cơ sở tiền) và doanh thu/chi phí theo bảng dữ liệu; kèm biểu đồ.",
      task_class=TRANSFORM, params=obj())
def monthly_summary(run, p):
    ms = analysis.monthly_summary(run.ctx.org_id, run.file_ids)
    if not ms["months"]:
        raise NeedsInput("Không tìm thấy bảng có cột ngày và số tiền thu/chi/doanh thu/chi phí để tổng hợp theo tháng.")
    has = ms["has"]
    cols = [{"key": "month", "label": "Tháng"}]
    totals = []
    for k, label in (("cash_in", "Thu (sổ quỹ)"), ("cash_out", "Chi (sổ quỹ)"), ("net_cash", "Chênh lệch thu - chi"),
                     ("revenue", "Doanh thu"), ("expense", "Chi phí")):
        if (k == "net_cash" and (has["cash_in"] or has["cash_out"])) or has.get(k):
            cols.append({"key": k, "label": label, "type": "money"})
            totals.append(k)
    rows = [{**{k: (_m(v) if k != "month" and k != "rows" else v) for k, v in r.items()}} for r in ms["months"]]
    files_by_month = {}
    for s in ms["sources"]:
        files_by_month.setdefault(s["month"], set()).add(s["file_id"])
    for r in rows:
        r["_src"] = [[fid, None] for fid in sorted(files_by_month.get(r["month"], []))]
    value_cols = [c["key"] for c in cols[1:] if c["key"] in ("cash_in", "cash_out", "revenue", "expense")][:4]
    detail = [{"month": s["month"], "side": {"cash_in": "Thu", "cash_out": "Chi", "revenue": "Doanh thu", "expense": "Chi phí"}[s["side"]],
               "amount": s["amount"], "file": s["file"], "row": f"{s['sheet']}!{s['row']}" if s["sheet"] else s["row"],
               "_src": _src(s["file_id"], f"{s['sheet']} dòng {s['row']}")} for s in ms["sources"]]
    if ms["skipped"]:
        run.warn(f"{len(ms['skipped'])} dòng không tổng hợp được (thiếu ngày/số tiền hoặc không rõ thu/chi) — xem sheet Chi tiết theo tháng")
    if has["cash_in"] and has["revenue"]:
        run.note("Thu/chi sổ quỹ (cơ sở tiền) và doanh thu/chi phí (bảng dữ liệu) được trình bày riêng, không cộng lẫn.")
    return {"summary": f"{len(rows)} tháng ({rows[0]['month']} → {rows[-1]['month']}) từ {len({s['file_id'] for s in ms['sources']})} file",
            "data": {"months": len(rows)},
            "sections": [{"name": "Theo tháng", "title": "Tổng hợp theo tháng", "columns": cols, "rows": rows, "totals": totals,
                          "charts": [{"type": "bar", "title": "So sánh theo tháng", "category": "month", "values": value_cols}]},
                         {"name": "Chi tiết theo tháng", "title": "Dòng nguồn được tổng hợp", "columns": [
                             {"key": "month", "label": "Tháng"}, {"key": "side", "label": "Loại"}, {"key": "amount", "label": "Số tiền", "type": "money"},
                             {"key": "file", "label": "File"}, {"key": "row", "label": "Vị trí"}], "rows": detail}]}


@tool(name="consolidate_tables", description="Gộp các bảng cùng cấu trúc tiêu đề từ nhiều file/sheet thành một bảng, giữ nguồn từng dòng.",
      task_class=TRANSFORM, params=obj())
def consolidate_tables(run, p):
    groups = analysis.consolidate(run.ctx.org_id, run.file_ids)
    if not groups:
        raise NeedsInput("Không có bảng dữ liệu có tiêu đề để gộp.")
    sections = []
    for gi, g in enumerate(groups[:10], start=1):
        cols = []
        money_roles = {c for r, c in g["roles"].items() if r in ("amount", "inflow", "outflow", "bank_debit", "bank_credit",
                                                                  "led_debit", "led_credit", "vat", "subtotal", "balance")}
        for ci, h in enumerate(g["header"]):
            cols.append({"key": f"c{ci}", "label": str(h or f"Cột {ci + 1}")[:60], "type": "money" if ci in money_roles else "text"})
        cols.append({"key": "src_file", "label": "File nguồn"})
        rows = []
        for r in g["rows"]:
            row = {}
            for ci in range(len(g["header"])):
                v = r["values"][ci] if ci < len(r["values"]) else None
                if ci in money_roles and v not in (None, ""):
                    pv = money.parse_amount(v)
                    v = money.fmt(pv.value) if pv.status == "OK" else None
                row[f"c{ci}"] = v
            row["src_file"] = r["file"]
            row["_src"] = _src(r["file_id"], f"{r['sheet']}!{r['row']}")
            rows.append(row)
        sections.append({"name": f"Hợp nhất {gi}", "title": f"Hợp nhất {len(g['files'])} file: {', '.join(g['files'])[:150]}",
                         "columns": cols, "rows": rows, "totals": [f"c{ci}" for ci in sorted(money_roles)]})
    return {"summary": f"{len(groups)} nhóm bảng cùng cấu trúc; lớn nhất {len(groups[0]['rows'])} dòng từ {len(groups[0]['files'])} file",
            "data": {"groups": len(groups)}, "sections": sections}


@tool(name="profile_tables", description="Đếm và thống kê bảng dữ liệu bất kỳ (danh sách nhân sự/sinh viên, bảng kê…): số dòng dữ liệu, số giá trị khác nhau, min/max/trung bình cột số, phân bố theo cột ít giá trị; lọc theo cột chứa giá trị. Dùng cho câu hỏi 'bao nhiêu', 'đếm', 'thống kê', 'phân bố', 'có mấy'.",
      task_class=READ_ONLY, params=obj({"filter_column": {"type": ["string", "null"], "maxLength": 80},
                                        "filter_value": {"type": ["string", "null"], "maxLength": 120},
                                        "group_by": {"type": ["string", "null"], "maxLength": 80}}))
def profile_tables(run, p):
    if bool(p.get("filter_column")) != bool(p.get("filter_value")):
        raise ToolInputError("Lọc cần cả tên cột và giá trị")
    tabs = analysis.profile(run.ctx.org_id, run.file_ids, p.get("filter_column"), p.get("filter_value"), p.get("group_by"))
    if not tabs:
        raise NeedsInput("Không tìm thấy bảng có dòng tiêu đề trong các file đã tải lên" +
                         (f" (hoặc không có cột '{p['filter_column']}')" if p.get("filter_column") else "") + ".")
    overview, colrows, dist, answers = [], [], [], []
    for t in tabs:
        # Ưu tiên mã định danh thật (Mã SV, Mã NV…) hơn số thứ tự — STT không chứng minh các dòng là người/vật khác nhau
        ids_ = [c for c in t["columns"] if c["id_like"]]
        idc = next((c for c in ids_ if fold(c["column"]) != "stt"), ids_[0] if ids_ else None)
        where = f"'{t['sheet']}'" if t["sheet"] not in (None, "CSV", "TSV") else f"'{t['file']}'"
        ans = f"{where}: {t['rows']} dòng dữ liệu" + (f" ({t['filter']})" if t["filter"] else "")
        if idc:
            ans += f", cột '{idc['column']}' có {idc['distinct']} giá trị khác nhau"
        if t["skipped_rows"]:
            ans += f"; đã bỏ {len(t['skipped_rows'])} dòng không phải dữ liệu (tổng/chữ ký/ghi chú)"
        answers.append(ans)
        loc = f"{t['sheet']}!{t['row_range'][0]}-{t['row_range'][1]}" if t["row_range"] else t["sheet"]
        overview.append({"table": t["sheet"], "file": t["file"], "header_row": t["header_row"], "rows": t["rows"],
                         "id_column": idc["column"] if idc else None, "filter": t["filter"],
                         "skipped": ", ".join(map(str, t["skipped_rows"][:20])), "_src": _src(t["file_id"], loc)})
        for c in t["columns"]:
            colrows.append({"table": t["sheet"], "column": c["column"], "non_empty": c["non_empty"], "distinct": c["distinct"],
                            "min": c.get("min"), "max": c.get("max"), "avg": c.get("avg"),
                            "note": "dữ liệu cá nhân — không liệt kê giá trị" if c["sensitive"] else ""})
            for v, n in c.get("distribution") or []:
                dist.append({"table": t["sheet"], "column": c["column"], "value": v, "count": n,
                             "pct": money.fmt((money.to_decimal(n) / max(1, t["rows"])).quantize(money.to_decimal("0.0001")))})
    run.note("Số dòng dữ liệu = các dòng dưới dòng tiêu đề, bỏ dòng tổng cộng và dòng chữ ký/ghi chú (ít ô hơn nửa số cột).")
    sections = [
        {"name": "Tổng quan bảng", "title": "Số dòng dữ liệu theo từng bảng", "columns": [
            {"key": "table", "label": "Bảng/sheet"}, {"key": "file", "label": "File"}, {"key": "header_row", "label": "Dòng tiêu đề", "type": "number"},
            {"key": "rows", "label": "Số dòng dữ liệu", "type": "number"}, {"key": "id_column", "label": "Cột định danh"},
            {"key": "filter", "label": "Bộ lọc"}, {"key": "skipped", "label": "Dòng đã bỏ qua"}], "rows": overview},
        {"name": "Thống kê cột", "title": "Thống kê từng cột", "columns": [
            {"key": "table", "label": "Bảng"}, {"key": "column", "label": "Cột"}, {"key": "non_empty", "label": "Có giá trị", "type": "number"},
            {"key": "distinct", "label": "Khác nhau", "type": "number"}, {"key": "min", "label": "Nhỏ nhất", "type": "number"},
            {"key": "max", "label": "Lớn nhất", "type": "number"}, {"key": "avg", "label": "Trung bình", "type": "number"},
            {"key": "note", "label": "Ghi chú"}], "rows": colrows}]
    if dist:
        sections.append({"name": "Phân bố", "title": "Phân bố theo cột ít giá trị", "columns": [
            {"key": "table", "label": "Bảng"}, {"key": "column", "label": "Cột"}, {"key": "value", "label": "Giá trị"},
            {"key": "count", "label": "Số dòng", "type": "number"}, {"key": "pct", "label": "Tỉ lệ", "type": "percent"}], "rows": dist})
    return {"summary": "; ".join(answers), "data": {"tables": len(tabs), "rows": [t["rows"] for t in tabs]}, "sections": sections}


FILTER_SCHEMA = {"type": "array", "maxItems": 5, "items": {"type": "object", "required": ["column", "value"], "properties": {
    "column": {"type": "string", "maxLength": 80}, "op": {"type": "string", "enum": list(tabular.FILTER_OPS)},
    "value": {"type": ["string", "number"]}}}}


@tool(name="analyze_table", description="Tính toán trên bảng dữ liệu bất kỳ (bảng kê bán hàng, danh sách sinh viên/nhân viên, bảng lương…): "
      "đếm (count), tổng (sum), trung bình (avg), nhỏ/lớn nhất (min/max), top N cao/thấp nhất (top/bottom), liệt kê dòng thoả điều kiện (list); "
      "có lọc (filters: cột, op eq/ne/contains/gt/gte/lt/lte, giá trị) và nhóm theo cột (group_by; 'tháng'/'quý'/'năm' suy ra từ cột ngày). "
      "Tên cột viết theo lời người dùng, hệ thống tự ánh xạ sang cột thật. Dùng cho: 'có bao nhiêu sinh viên nữ', 'tổng doanh thu theo mặt hàng', "
      "'ai điểm cao nhất', 'lọc danh sách…', 'doanh thu tháng 5'.",
      task_class=READ_ONLY, params=obj({
          "operation": {"type": "string", "enum": list(tabular.OPS)},
          "value_column": {"type": ["string", "null"], "maxLength": 80},
          "group_by": {"type": ["string", "null"], "maxLength": 80},
          "filters": FILTER_SCHEMA,
          "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 5000},
          "sort": {"type": ["string", "null"], "enum": ["asc", "desc", None]},
          "subject": {"type": ["string", "null"], "maxLength": 40}}, ["operation"]))
def analyze_table(run, p):
    op = p["operation"]
    try:
        res = tabular.analyze(run.ctx.org_id, run.file_ids, op, p.get("value_column"), p.get("group_by"),
                              p.get("filters") or [], p.get("limit"), p.get("sort") or "desc")
    except tabular.ColumnNotFound as e:
        raise NeedsInput(str(e)) from e
    if not res["results"]:
        raise NeedsInput("Không có bảng dữ liệu có dòng tiêu đề trong các file của phiên này.")
    for n in res["notes"]:
        run.note(n)
    subject = re.sub(r"[^\w\s/-]", "", str(p.get("subject") or "")).strip()[:40] or "dòng"
    answers, sections = [], []
    for r in res["results"]:
        where = f"bảng '{r['sheet']}'" if r["sheet"] not in (None, "CSV", "TSV") else f"file '{r['file']}'"
        cond = tabular.describe_filters(r["filters"])
        cond_txt = f" có {cond}" if cond else ""
        vc = r["value_column"]
        if r["non_numeric"]:
            run.warn(f"{where}: {r['non_numeric']} ô trong cột '{vc}' không phải số — không được tính")
        src = _src(r["file_id"], r["sheet"])
        if r.get("groups") is not None:
            g = r["groups"]
            measure = "count" if op in ("count", "list") else ("sum" if op in ("top", "bottom") else op)
            label = {"count": "Số dòng", "sum": f"Tổng {vc}", "avg": f"Trung bình {vc}", "min": f"Giá trị nhỏ nhất của một dòng '{vc}'",
                     "max": f"Giá trị lớn nhất của một dòng '{vc}'"}[measure]
            if op in ("top", "bottom"):
                label = f"{'Cao' if op == 'top' else 'Thấp'} nhất theo tổng {vc}"
            parts = [f"{x['key']}: {x['count'] if measure == 'count' else money.vn(x[measure])}" for x in g[:8]]
            more = f" … (+{len(g) - 8} nhóm)" if len(g) > 8 else ""
            ans = f"{label} theo '{r['group_by']}'{cond_txt} ({where}): " + "; ".join(parts) + more
            if measure != "count" and r["sum"] is not None and op in ("sum", "top", "bottom"):
                ans += f". Tổng cộng {money.vn(r['sum'])}"
            if op in ("max", "min", "avg") and g and vc:  # nêu thêm nhóm có tổng lớn nhất để không hiểu nhầm
                big = max(g, key=lambda x: x["sum"] or 0)
                ans += f". Nhóm có tổng '{vc}' lớn nhất: {big['key']} — {money.vn(big['sum'])}"
            elif measure == "count":
                ans += f". Tổng {money.vn(r['matched'])} {subject}"
            answers.append(ans + ".")
            cols = [{"key": "key", "label": r["group_by"]}, {"key": "count", "label": "Số dòng", "type": "number"}]
            if vc:
                cols += [{"key": "sum", "label": f"Tổng {vc}", "type": "number"}, {"key": "avg", "label": f"Trung bình {vc}", "type": "number"},
                         {"key": "min", "label": "Nhỏ nhất", "type": "number"}, {"key": "max", "label": "Lớn nhất", "type": "number"}]
            rows = [{"key": x["key"], "count": x["count"], **({k: _m(x[k] if k != "avg" or x[k] is None else x[k].quantize(money.to_decimal("0.01")))
                                                               for k in ("sum", "avg", "min", "max")} if vc else {}),
                     "_src": _src(r["file_id"], f"{r['sheet']} dòng {', '.join(map(str, x['rows'][:15]))}")} for x in g]
            sections.append({"name": "Kết quả theo nhóm", "title": f"{label} theo {r['group_by']}{cond_txt} — {where}", "columns": cols,
                             "rows": rows, "totals": ["count"] + (["sum"] if vc else [])})
        elif r.get("items") is not None:
            items = r["items"]
            if op == "list":
                answers.append((f"Có {money.vn(r['matched'])} {subject}{cond_txt} trên tổng {money.vn(r['total_rows'])} ({where})" if cond else
                                f"Danh sách {money.vn(r['matched'])} {subject} ({where})") + "; danh sách nằm trong sheet 'Danh sách đã lọc'.")
                cols = [{"key": f"c{ci}", "label": h or f"Cột {ci + 1}"} for ci, h in enumerate(r["header"])]
                rows = [{**{f"c{ci}": (it["values"][ci] if ci < len(it["values"]) else None) for ci in range(len(r["header"]))},
                         "_src": _src(r["file_id"], f"{r['sheet']} dòng {it['row']}")} for it in items]
                sections.append({"name": "Danh sách đã lọc", "title": f"{r['matched']} {subject}{cond_txt} — {where}", "columns": cols, "rows": rows})
            else:
                word = {"top": "Cao nhất", "max": "Cao nhất", "bottom": "Thấp nhất", "min": "Thấp nhất"}[op]
                shown = "; ".join(f"{it['label'] or 'dòng ' + str(it['row'])} — {money.vn(it['value'])}" for it in items[:5])
                more = f" (và {len(items) - 5} dòng khác bằng giá trị này)" if op in ("min", "max") and len(items) > 5 else ""
                answers.append(f"{word} theo '{vc}'{cond_txt} ({where}): {shown}{more}." if items else
                               f"Không có dòng nào có giá trị số ở cột '{vc}'{cond_txt} ({where}).")
                lab = " / ".join(r["label_columns"]) or "Dòng"
                rows = [{"rank": k, "label": it["label"], "value": _m(it["value"]), "row": it["row"],
                         "_src": _src(r["file_id"], f"{r['sheet']} dòng {it['row']}")} for k, it in enumerate(items, 1)]
                sections.append({"name": "Xếp hạng", "title": f"{word} theo {vc}{cond_txt} — {where}", "columns": [
                    {"key": "rank", "label": "#", "type": "number"}, {"key": "label", "label": lab},
                    {"key": "value", "label": vc, "type": "number"}, {"key": "row", "label": "Dòng gốc", "type": "number"}], "rows": rows})
        else:
            if op == "count":
                answers.append(f"Có {money.vn(r['matched'])} {subject}{cond_txt}" + (f" trên tổng {money.vn(r['total_rows'])}" if cond else "") + f" ({where}).")
            else:
                word = {"sum": "Tổng", "avg": "Trung bình", "min": "Nhỏ nhất", "max": "Lớn nhất"}[op]
                v = r[op]
                answers.append(f"{word} '{vc}'{cond_txt}: {money.vn(v)} (tính trên {money.vn(r['n_values'])} dòng, {where})." if v is not None
                               else f"Không có giá trị số trong cột '{vc}'{cond_txt} ({where}).")
            sections.append({"name": "Kết quả", "title": f"Kết quả tính toán — {where}", "columns": [
                {"key": "metric", "label": "Chỉ số"}, {"key": "value", "label": "Giá trị", "type": "number"}],
                "rows": [{"metric": m_, "value": _m(v_), "_src": src} for m_, v_ in (
                    ("Số dòng thoả điều kiện", r["matched"]), ("Tổng số dòng", r["total_rows"]),
                    *(((f"Tổng {vc}", r["sum"]), (f"Trung bình {vc}", r["avg"].quantize(money.to_decimal("0.01")) if r["avg"] is not None else None),
                       (f"Nhỏ nhất {vc}", r["min"]), (f"Lớn nhất {vc}", r["max"])) if vc else ()))]})
    if len(res["results"]) > 1 and op == "sum" and not p.get("group_by"):
        tot = money.sum_(r["sum"] for r in res["results"] if r["sum"] is not None)
        answers.append(f"Cộng {len(res['results'])} bảng: {money.vn(tot)}.")
    shown = " ".join(answers)
    if res["notes"]:  # cách hiểu cột / điều kiện bị bỏ phải hiện cùng con số, không chỉ nằm trong file Excel
        shown += " (" + "; ".join(res["notes"][:3]) + ")"
    return {"summary": shown, "answer": shown,
            "data": {"results": len(res["results"]), "matched": [r["matched"] for r in res["results"]]}, "sections": sections}


@tool(name="summarize_bank", description="Tổng hợp sao kê ngân hàng: tổng tiền vào, tổng tiền ra, chênh lệch, số dư đầu/cuối kỳ (nếu sao kê có cột số dư), theo tháng.",
      task_class=READ_ONLY, params=obj())
def summarize_bank(run, p):
    q = ",".join("?" for _ in run.file_ids) or "''"
    txns = db.all_(f"""SELECT b.*, f.original_name file FROM cur_bank_transactions b JOIN files f ON f.id=b.file_id
                      WHERE b.org_id=? AND b.file_id IN ({q})""", (run.ctx.org_id, *run.file_ids))
    if not txns:
        raise NeedsInput("Không có giao dịch sao kê ngân hàng trong các file của phiên này.")
    answers, rows, by_file = [], [], {}
    for t in txns:
        by_file.setdefault((t["file_id"], t["file"], t["currency"] or "VND"), []).append(t)
    for (fid, fname, cur), items in by_file.items():
        items.sort(key=lambda t: (t["txn_date"] or "", t["row_ref"] or ""))
        amts = [money.D(t["amount"]) for t in items if t["amount"] not in (None, "")]
        tin = money.sum_(a for a in amts if a > 0)
        tout = -money.sum_(a for a in amts if a < 0)
        months = {}
        for t in items:
            m = (t["txn_date"] or "?")[:7]
            e = months.setdefault(m, {"in": money.ZERO, "out": money.ZERO, "n": 0})
            a = money.D(t["amount"]) or money.ZERO
            e["in" if a > 0 else "out"] += abs(a)
            e["n"] += 1
        bal = [t for t in items if t["balance"] not in (None, "")]
        opening = closing = None
        if bal:
            first, last = bal[0], bal[-1]
            opening = money.D(first["balance"]) - (money.D(first["amount"]) or money.ZERO)
            closing = money.D(last["balance"])
            expect = opening + tin - tout
            if bal[0] is items[0] and bal[-1] is items[-1] and expect != closing:
                run.warn(f"{fname}: số dư đầu + vào − ra = {money.vn(expect)} khác số dư cuối trên sao kê {money.vn(closing)} — cần kiểm tra sao kê")
        period = f"{items[0]['txn_date'] or '?'} → {items[-1]['txn_date'] or '?'}"
        ans = (f"Sao kê '{fname}' ({period}, {len(items)} giao dịch): tiền vào {money.vn(tin)} {cur}, tiền ra {money.vn(tout)} {cur}, "
               f"chênh lệch {money.vn(tin - tout)}")
        if closing is not None:
            ans += f"; số dư đầu kỳ {money.vn(opening)}, số dư cuối kỳ {money.vn(closing)}"
        else:
            ans += "; sao kê không có cột số dư nên không xác định được số dư cuối kỳ"
        answers.append(ans + ".")
        for m, e in sorted(months.items()):
            rows.append({"file": fname, "month": m, "count": e["n"], "inflow": _m(e["in"]), "outflow": _m(e["out"]),
                         "net": _m(e["in"] - e["out"]), "_src": _src(fid)})
        rows.append({"file": fname, "month": "Cả kỳ", "count": len(items), "inflow": _m(tin), "outflow": _m(tout), "net": _m(tin - tout),
                     "opening": _m(opening), "closing": _m(closing), "_src": _src(fid)})
    return {"summary": " ".join(answers), "answer": " ".join(answers), "data": {"files": len(by_file), "txns": len(txns)},
            "sections": [{"name": "Tổng hợp sao kê", "title": "Tiền vào / tiền ra theo tháng", "columns": [
                {"key": "file", "label": "File"}, {"key": "month", "label": "Tháng"}, {"key": "count", "label": "Số giao dịch", "type": "number"},
                {"key": "inflow", "label": "Tiền vào", "type": "money"}, {"key": "outflow", "label": "Tiền ra", "type": "money"},
                {"key": "net", "label": "Chênh lệch", "type": "money"}, {"key": "opening", "label": "Số dư đầu kỳ", "type": "money"},
                {"key": "closing", "label": "Số dư cuối kỳ", "type": "money"}], "rows": rows,
                "charts": [{"type": "bar", "title": "Tiền vào / ra theo tháng", "category": "month", "values": ["inflow", "outflow"]}]
                if len(rows) > 2 else []}]}


@tool(name="propose_journal_entries", description="Đề xuất định khoản từ hoá đơn đã kiểm tra (chỉ đề xuất, không ghi sổ). Thiếu thông tin → hỏi người dùng.",
      task_class=PROPOSE, permission="edit_draft", params=obj({"answers": {"type": "object"},
                                                               "direction": {"type": ["string", "null"], "enum": ["sale", "purchase", "all", None]}}),
      side_effects="creates PROPOSED journal entries (idempotent by invoice)", risk="medium", idempotency="idempotency_key=invoice:<id>:v1")
def propose_journal_entries(run, p):
    invs = analysis.invoices(run.ctx.org_id, run.file_ids)
    _check_org_relation(run, invs)
    direction = _direction_param(run, p.get("direction"))
    if direction:
        others = [i for i in invs if i["direction"] != direction]
        invs = [i for i in invs if i["direction"] == direction]
        if others:
            run.note(f"Chỉ định khoản hoá đơn {DIRECTION_VN[direction].lower()} theo yêu cầu; bỏ qua {len(others)} hoá đơn khác chiều")
    dups = duplicates.detect(run.ctx.org_id, run.file_ids)
    invs, dropped = analysis.dedupe_for_totals(invs, dups)
    if not invs:
        raise NeedsInput("Không có hoá đơn " + (DIRECTION_VN[direction].lower() + " " if direction else "")
                         + "trong các file đã tải lên để định khoản.")
    res = proposals.propose_for_invoices(run.ctx, [i["id"] for i in invs], task_id=run.task["id"], answers=p.get("answers") or {})
    rows = []
    for pr in res["proposed"]:
        e = journal.get(run.ctx.org_id, pr["entry_id"])
        for ln in e["lines"]:
            rows.append({"invoice": pr["invoice"], "entry": pr["entry_id"][:8], "date": e["entry_date"], "account": ln["account_code"],
                         "debit": ln["debit"] if ln["debit"] != "0" else None, "credit": ln["credit"] if ln["credit"] != "0" else None,
                         "memo": ln["memo"], "status": e["status"], "assumption": pr["assumption"],
                         "_src": [[ev.get("file_id"), "hoá đơn"] for ev in ln["evidence"]][:1]})
        review.open_item(run, "journal_proposal", "journal_entry", pr["entry_id"], f"Đề xuất định khoản {pr['invoice']}",
                         {"assumption": pr["assumption"], "entry_id": pr["entry_id"]})
    ask = []
    for n in res["needs_input"]:
        ask.append({"invoice": n["invoice"], "missing": ", ".join(n["missing"]), "question": n["question"],
                    "choices": ", ".join(f"{c['code']} {c['name']}" for c in n.get("choices", []))})
        review.open_item(run, "missing_data", "invoice", n["invoice_id"], n["question"][:200], n)
    skipped = [{"invoice": s["invoice"], "reason": s["reason"]} for s in res["skipped"]]
    answer = f"Đã đề xuất {len(res['proposed'])} bút toán (chưa ghi sổ, cần người phê duyệt)"
    if res["needs_input"]:
        answer += f"; {len(res['needs_input'])} hoá đơn cần bạn bổ sung thông tin"
        run.ask(f"{len(res['needs_input'])} hoá đơn cần bổ sung thông tin trước khi định khoản (ví dụ "
                f"{res['needs_input'][0]['invoice']}: {res['needs_input'][0]['question'][:150]}) — trả lời trong mục Kiểm duyệt.")
    if skipped:
        answer += f"; {len(skipped)} hoá đơn chưa đủ điều kiện ({skipped[0]['invoice']}: {skipped[0]['reason'][:120]}" + (" …" if len(skipped) > 1 else "") + ")"
    answer += "."
    return {"summary": answer, "answer": answer,
            "data": {"proposed": [x["entry_id"] for x in res["proposed"]], "needs_input": res["needs_input"], "skipped": res["skipped"]},
            "sections": [s for s in [
                {"name": "Đề xuất định khoản", "title": "Đề xuất định khoản (PROPOSED — chưa ghi sổ, cần phê duyệt)", "columns": [
                    {"key": "invoice", "label": "Hoá đơn"}, {"key": "entry", "label": "Bút toán"}, {"key": "date", "label": "Ngày", "type": "date"},
                    {"key": "account", "label": "TK"}, {"key": "debit", "label": "Nợ", "type": "money"}, {"key": "credit", "label": "Có", "type": "money"},
                    {"key": "memo", "label": "Diễn giải"}, {"key": "assumption", "label": "Giả định"}, {"key": "status", "label": "Trạng thái"}],
                 "rows": rows, "totals": ["debit", "credit"]} if rows else None,
                {"name": "Cần bổ sung", "title": "Hoá đơn cần bổ sung thông tin trước khi định khoản", "columns": [
                    {"key": "invoice", "label": "Hoá đơn"}, {"key": "missing", "label": "Thiếu"}, {"key": "question", "label": "Câu hỏi"},
                    {"key": "choices", "label": "Lựa chọn gợi ý"}], "rows": ask} if ask else None,
                {"name": "Chưa đủ điều kiện", "title": "Hoá đơn chưa đủ điều kiện định khoản", "columns": [
                    {"key": "invoice", "label": "Hoá đơn"}, {"key": "reason", "label": "Lý do"}], "rows": skipped} if skipped else None] if s]}


@tool(name="build_ar_ap", description="Lập bảng công nợ phải thu/phải trả theo đối tượng và tuổi nợ (0-30, 31-60, 61-90, >90 ngày) từ hoá đơn; trừ khoản đã thanh toán khớp chắc chắn với sao kê.",
      task_class=TRANSFORM, params=obj({"as_of": {"type": ["string", "null"], "maxLength": 10}}))
def build_ar_ap(run, p):
    org = run.ctx.org_id
    invs = analysis.invoices(org, run.file_ids)
    invs, _ = analysis.dedupe_for_totals(invs, duplicates.detect(org, run.file_ids))
    if not invs:
        raise NeedsInput("Không có hoá đơn để lập công nợ.")
    paid = {}
    q = ",".join("?" for _ in run.file_ids) or "''"
    bank = db.all_(f"SELECT id, txn_date date, amount, reference, description, counterparty FROM cur_bank_transactions WHERE org_id=? AND file_id IN ({q})",
                   (org, *run.file_ids))
    if bank:
        book = [{"id": i["id"], "date": i["issue_date"], "amount": i["total"] if i["direction"] == "sale" else money.fmt(-money.D(i["total"])),
                 "reference": i["number"], "description": f"HĐ {i['number']}", "counterparty": analysis.counterparty_of(i)[0]}
                for i in invs if i["direction"] in ("sale", "purchase") and i["status"] in analysis.VERIFIED_SET and i["total"]]
        matches, _ = reconcile.reconcile(bank, book, 60)
        for m in matches:
            if m["status"] in ("MATCHED_EXACT", "MATCHED_VERIFIED") and len(m["book"]) == 1:
                paid[m["book"][0]] = abs(money.sum_(money.D(b["amount"]) for b in m["bank_rows"]))
        run.note("Chỉ trừ thanh toán khớp chắc chắn (MATCHED_EXACT/VERIFIED); khoản khớp tiềm năng vẫn tính là còn nợ.")
    else:
        run.warn("Không có sao kê — công nợ bằng tổng hoá đơn, chưa trừ thanh toán")
    res = analysis.ar_ap(invs, paid, p.get("as_of"))
    sections = []
    for side, title in (("receivable", "Công nợ phải thu (hoá đơn bán ra)"), ("payable", "Công nợ phải trả (hoá đơn mua vào)")):
        rows = [{"counterparty": e["counterparty"], "tax_id": e["tax_id"], "currency": e["currency"], "invoiced": _m(e["invoiced"]),
                 "paid": _m(e["paid"]), "open": _m(e["open"]), **{b: _m(e[b]) for b in res["buckets"]},
                 "invoices": ", ".join(x["number"] or "?" for x in e["invoices"])} for e in res[side]]
        if rows:
            sections.append({"name": "Phải thu" if side == "receivable" else "Phải trả", "title": title, "columns": [
                {"key": "counterparty", "label": "Đối tượng"}, {"key": "tax_id", "label": "MST"}, {"key": "currency", "label": "Tiền tệ"},
                {"key": "invoiced", "label": "Giá trị HĐ", "type": "money"}, {"key": "paid", "label": "Đã thanh toán", "type": "money"},
                {"key": "open", "label": "Còn nợ", "type": "money"}] + [{"key": b, "label": f"{b} ngày", "type": "money"} for b in res["buckets"]]
                + [{"key": "invoices", "label": "Hoá đơn"}], "rows": rows,
                "totals": ["invoiced", "paid", "open", *res["buckets"]] if len({r['currency'] for r in rows}) == 1 else [],
                "notes": [f"Tuổi nợ tính từ ngày hoá đơn đến {res['as_of']} (chưa có hạn thanh toán trên chứng từ)."]})
    ar = money.sum_(e["open"] for e in res["receivable"])
    ap = money.sum_(e["open"] for e in res["payable"])
    return {"summary": f"Phải thu còn {money.fmt(ar)}, phải trả còn {money.fmt(ap)} (tại {res['as_of']})",
            "data": {"receivable_open": money.fmt(ar), "payable_open": money.fmt(ap)}, "sections": sections}


@tool(name="search_documents", description="Tìm kiếm từ khoá trong nội dung các chứng từ đã tải lên trong phiên làm việc này.",
      task_class=READ_ONLY, params=obj({"query": {"type": "string", "maxLength": 200}}, ["query"]))
def search_documents(run, p):
    needle = fold(p["query"])
    if len(needle) < 2:
        raise ToolInputError("Từ khoá quá ngắn")
    rows = []
    q = ",".join("?" for _ in run.file_ids) or "''"
    for e in db.all_(f"""SELECT e.file_id, e.text_content, f.original_name FROM extractions e JOIN files f ON f.id=e.file_id
                         WHERE e.org_id=? AND e.status IN ('OK','PARTIAL') AND e.file_id IN ({q})""",
                     (run.ctx.org_id, *run.file_ids)):
        text = e["text_content"] or ""
        for line in text.splitlines():
            if needle in fold(line):
                rows.append({"file": e["original_name"], "snippet": line.strip()[:300], "_src": _src(e["file_id"])})
                if len(rows) >= 500:
                    break
    return {"summary": f"{len(rows)} kết quả cho '{p['query']}'", "data": {"hits": len(rows)},
            "sections": [{"name": "Tìm kiếm", "title": f"Kết quả tìm '{p['query']}'", "columns": [
                {"key": "file", "label": "File"}, {"key": "snippet", "label": "Đoạn văn bản"}], "rows": rows}]}


@tool(name="query_accounting_database", description="Truy vấn dữ liệu kế toán định sẵn (chỉ đọc): trial_balance, journal_entries, open_reviews, account_rules.",
      task_class=READ_ONLY, params=obj({"query": {"type": "string", "enum": ["trial_balance", "journal_entries", "open_reviews", "account_rules"]}}, ["query"]))
def query_accounting_database(run, p):
    org = run.ctx.org_id
    qn = p["query"]
    if qn == "trial_balance":
        tb = journal.trial_balance(org)
        return {"summary": f"Bảng cân đối phát sinh: {len(tb['rows'])} tài khoản, cân đối={tb['balanced']}", "data": tb,
                "sections": [{"name": "Cân đối phát sinh", "title": "Bảng cân đối phát sinh (sổ cái đã ghi)", "columns": [
                    {"key": "account", "label": "TK"}, {"key": "name", "label": "Tên"}, {"key": "debit", "label": "Phát sinh Nợ", "type": "money"},
                    {"key": "credit", "label": "Phát sinh Có", "type": "money"}, {"key": "balance", "label": "Số dư (Nợ - Có)", "type": "money"}],
                    "rows": tb["rows"], "totals": ["debit", "credit"]}]}
    if qn == "journal_entries":
        rows = db.all_("SELECT id, entry_date, description, status, source, created_by FROM journal_entries WHERE org_id=? ORDER BY entry_date DESC LIMIT 1000", (org,))
        return {"summary": f"{len(rows)} bút toán", "data": {"count": len(rows)},
                "sections": [{"name": "Bút toán", "title": "Danh sách bút toán", "columns": [
                    {"key": "entry_date", "label": "Ngày", "type": "date"}, {"key": "description", "label": "Diễn giải"},
                    {"key": "status", "label": "Trạng thái"}, {"key": "source", "label": "Nguồn"}, {"key": "created_by", "label": "Người tạo"}], "rows": rows}]}
    if qn == "open_reviews":
        rows = db.all_("SELECT kind, title, created_at FROM review_items WHERE org_id=? AND status='OPEN' ORDER BY created_at DESC LIMIT 1000", (org,))
        return {"summary": f"{len(rows)} mục chờ kiểm duyệt", "data": {"count": len(rows)},
                "sections": [{"name": "Chờ kiểm duyệt", "title": "Mục chờ kiểm duyệt", "columns": [
                    {"key": "kind", "label": "Loại"}, {"key": "title", "label": "Nội dung"}], "rows": rows}]}
    rows = db.all_("SELECT match_type, match_value, account_code, status, proposed_by, decided_by FROM account_rules WHERE org_id=?", (org,))
    return {"summary": f"{len(rows)} quy tắc hạch toán", "data": {"count": len(rows)},
            "sections": [{"name": "Quy tắc hạch toán", "title": "Quy tắc hạch toán nội bộ", "columns": [
                {"key": k, "label": k} for k in ("match_type", "match_value", "account_code", "status", "proposed_by", "decided_by")], "rows": rows}]}


@tool(name="create_review_request", description="Tạo một mục kiểm duyệt cho người dùng (câu hỏi/ngoại lệ cần người quyết định).",
      task_class=WRITE_DRAFT, permission="run_task", params=obj({"title": {"type": "string", "maxLength": 200},
                                                                 "detail": {"type": "string", "maxLength": 2000}}, ["title"]),
      side_effects="creates review item (idempotent by title)", produces_sections=False)
def create_review_request(run, p):
    rid = review.open_item(run, "agent_request", "task", f"{run.task['id']}:{fold(p['title'])[:80]}", p["title"], {"detail": p.get("detail")})
    return {"summary": f"Đã tạo yêu cầu kiểm duyệt: {p['title']}", "data": {"review_id": rid}, "sections": []}


@tool(name="request_posting", description="Gửi YÊU CẦU ghi sổ cho các bút toán PROPOSED của tác vụ này. Không ghi sổ: việc ghi sổ chỉ xảy ra khi người có vai trò APPROVER (khác người yêu cầu) phê duyệt.",
      task_class=COMMIT, permission="request_commit", params=obj(), risk="high",
      side_effects="creates PENDING approvals (idempotent per entry)", produces_sections=False)
def request_posting(run, p):
    entries = db.all_("SELECT id FROM journal_entries WHERE org_id=? AND task_id=? AND status='PROPOSED'", (run.ctx.org_id, run.task["id"]))
    ids = []
    for e in entries:
        try:
            ids.append(journal.request_post(run.ctx, e["id"]))
        except journal.JournalError as ex:
            run.warn(f"Không gửi được yêu cầu ghi sổ {e['id'][:8]}: {ex}")
    return {"summary": f"Đã gửi {len(ids)} yêu cầu ghi sổ — chờ người phê duyệt (APPROVER khác bạn). Chưa có bút toán nào được ghi sổ.",
            "data": {"approval_ids": ids}, "sections": []}


@tool(name="generate_excel", description="Tạo báo cáo Excel hoàn chỉnh từ kết quả các bước trước (công thức tổng, định dạng, lọc, cố định tiêu đề, biểu đồ, nguồn, cảnh báo) và tự xác minh.",
      task_class=GENERATE_ARTIFACT, params=obj({"title": {"type": ["string", "null"], "maxLength": 150}}),
      side_effects="stores new artifact version", produces_sections=False, failure="fail_task")
def generate_excel(run, p):
    return run.make_artifact("xlsx", p.get("title"))


@tool(name="generate_pdf", description="Tạo báo cáo PDF từ cùng dữ liệu của báo cáo Excel.",
      task_class=GENERATE_ARTIFACT, params=obj({"title": {"type": ["string", "null"], "maxLength": 150}}),
      side_effects="stores new artifact version", produces_sections=False)
def generate_pdf(run, p):
    return run.make_artifact("pdf", p.get("title"))


OPS_SCHEMA = {"type": "array", "maxItems": 20, "items": {"type": "object", "required": ["op"], "properties": {
    "op": {"type": "string", "enum": ["add_computed_column", "add_chart", "split_sheet", "rename_column", "remove_column",
                                      "sort", "filter_rows", "convert_currency", "rename_sheet"]}}}}


@tool(name="revise_artifact", description="Sửa báo cáo Excel đã tạo bằng các thao tác có kiểm soát (thêm cột tính, biểu đồ, tách sheet, đổi tên, lọc, sắp xếp, quy đổi tiền khi có tỷ giá) → phiên bản mới, giữ nguyên phiên bản cũ.",
      task_class=GENERATE_ARTIFACT, params=obj({"artifact_id": {"type": "string", "maxLength": 64}, "ops": OPS_SCHEMA}, ["artifact_id", "ops"]),
      side_effects="stores new artifact version", produces_sections=False, failure="fail_task")
def revise_artifact(run, p):
    return run.revise_artifact(p["artifact_id"], p["ops"])
