"""
Phân tích xác định trên dữ liệu đã trích xuất: tổng hợp hoá đơn, lọc, tổng hợp theo tháng,
hợp nhất bảng nhiều file, công nợ và tuổi nợ. Mọi tổng tiền tính bằng Decimal, tách theo loại tiền,
mỗi dòng kết quả mang tham chiếu tới chứng từ nguồn.
"""

from collections import defaultdict
from datetime import date

from .. import db, money
from ..extract.base import fold, parse_date

VERIFIED_SET = ("VERIFIED", "VALID_EXTRACTED", "REVIEWED")


def invoices(org_id, file_ids=None):
    """file_ids=None: toàn tổ chức (nội bộ); danh sách (kể cả rỗng): chỉ các file đó."""
    rows = db.all_(
        """SELECT i.*, f.original_name file_name, d.data_json doc_data FROM cur_invoices i
           JOIN files f ON f.id=i.file_id JOIN cur_documents d ON d.id=i.document_id WHERE i.org_id=?
           ORDER BY i.issue_date, i.number""", (org_id,))
    scope = None if file_ids is None else set(file_ids)
    out = []
    for r in rows:
        if scope is not None and r["file_id"] not in scope:
            continue
        data = db.loads(r.pop("doc_data"), {})
        r["vat_groups"] = (data.get("invoice") or {}).get("vat_groups") or []
        r["issues"] = db.loads(r.pop("issues_json"), [])
        out.append(r)
    return out


def dedupe_for_totals(rows, dup_groups):
    """Bỏ bản trùng (cùng khoá, cùng tiền) khỏi phép cộng: giữ bản XML nếu có, nếu không giữ bản đầu tiên."""
    drop = set()
    for g in dup_groups:
        if g["type"] != "INVOICE_DUPLICATE":
            continue
        ids = g["invoice_ids"]
        members = [r for r in rows if r["id"] in ids]
        if len(members) < 2:
            continue
        keep = next((m for m in members if m["source_format"] == "xml"), members[0])
        drop.update(m["id"] for m in members if m["id"] != keep["id"])
    return [r for r in rows if r["id"] not in drop], drop


def counterparty_of(r):
    if r["direction"] == "sale":
        return r["buyer_name"] or r["buyer_tax_id"] or "(không rõ)", r["buyer_tax_id"]
    return r["seller_name"] or r["seller_tax_id"] or "(không rõ)", r["seller_tax_id"]


def summarize_invoices(rows):
    by_cp = {}
    vat = {}
    unverified = []
    for r in rows:
        cur = r["currency"] or "VND"
        name, tax = counterparty_of(r)
        key = (tax or fold(name), cur, r["direction"])
        s = by_cp.setdefault(key, {"counterparty": name, "tax_id": tax, "currency": cur, "direction": r["direction"],
                                   "count": 0, "subtotal": money.ZERO, "vat": money.ZERO, "total": money.ZERO,
                                   "unverified_count": 0, "invoice_ids": []})
        s["count"] += 1
        s["invoice_ids"].append(r["id"])
        if r["status"] not in VERIFIED_SET:
            s["unverified_count"] += 1
            unverified.append(r["id"])
            continue
        s["subtotal"] += money.D(r["subtotal"]) or money.ZERO
        s["vat"] += money.D(r["vat_amount"]) or money.ZERO
        s["total"] += money.D(r["total"]) or money.ZERO
        for g in r["vat_groups"]:
            k = (g.get("label") or "?", cur, r["direction"])
            v = vat.setdefault(k, {"rate": g.get("label") or "?", "currency": cur, "direction": r["direction"],
                                   "taxable": money.ZERO, "vat": money.ZERO, "count": 0})
            v["taxable"] += money.D(g.get("taxable")) or money.ZERO
            v["vat"] += money.D(g.get("vat")) or money.ZERO
            v["count"] += 1
    cps = sorted(by_cp.values(), key=lambda s: (s["currency"], -s["total"]))
    totals = defaultdict(lambda: {"subtotal": money.ZERO, "vat": money.ZERO, "total": money.ZERO, "count": 0})
    for s in cps:
        t = totals[s["currency"]]
        for k in ("subtotal", "vat", "total"):
            t[k] += s[k]
        t["count"] += s["count"] - s["unverified_count"]
    return {"by_counterparty": cps, "vat_breakdown": sorted(vat.values(), key=lambda v: (v["currency"], v["rate"])),
            "totals_by_currency": dict(totals), "unverified_invoice_ids": unverified}


def filter_invoices(rows, min_total=None, max_total=None, date_from=None, date_to=None, counterparty=None,
                    direction=None, status=None):
    out = []
    lo = money.to_decimal(min_total) if min_total not in (None, "") else None
    hi = money.to_decimal(max_total) if max_total not in (None, "") else None
    for r in rows:
        t = money.D(r["total"])
        if lo is not None and (t is None or t <= lo):
            continue
        if hi is not None and (t is None or t > hi):
            continue
        if date_from and (not r["issue_date"] or r["issue_date"] < date_from):
            continue
        if date_to and (not r["issue_date"] or r["issue_date"] > date_to):
            continue
        if counterparty and fold(counterparty) not in fold(f"{r['seller_name']} {r['buyer_name']} {r['seller_tax_id']} {r['buyer_tax_id']}"):
            continue
        if direction and r["direction"] != direction:
            continue
        if status and r["status"] != status:
            continue
        out.append(r)
    return out


def _docs(org_id, file_ids, types):
    q = ",".join("?" for _ in types)
    rows = db.all_(f"""SELECT d.*, f.original_name file_name FROM cur_documents d JOIN files f ON f.id=d.file_id
                       WHERE d.org_id=? AND d.doc_type IN ({q})""", (org_id, *types))
    scope = None if file_ids is None else set(file_ids)
    return [dict(r, data=db.loads(r["data_json"], {})) for r in rows if scope is None or r["file_id"] in scope]


REVENUE_HINTS = ("doanh thu", "ban hang", "revenue", "sales", "thu nhap")
EXPENSE_HINTS = ("chi phi", "expense", "chi tieu", "cost", "mua hang")


def _side_hint(text):
    t = fold(text)
    if any(h in t for h in REVENUE_HINTS):
        return "revenue"
    if any(h in t for h in EXPENSE_HINTS):
        return "expense"
    return None


def monthly_summary(org_id, file_ids=None):
    """
    Theo tháng, tách hai cơ sở không được cộng lẫn:
    - Tiền (sổ quỹ): thu (cash_in), chi (cash_out) — dòng tiền, không phải doanh thu/chi phí.
    - Dồn tích (bảng doanh thu/chi phí): revenue, expense — nhận diện qua tên file/sheet/khoản mục.
    """
    months = defaultdict(lambda: {"cash_in": money.ZERO, "cash_out": money.ZERO, "revenue": money.ZERO,
                                  "expense": money.ZERO, "rows": 0})
    sources, skipped = [], []
    for d in _docs(org_id, file_ids, ("ledger", "table", "bank_statement")):
        data = d["data"]
        idx = data.get("col_index") or {}
        if "date" not in idx:
            continue
        doc_side = _side_hint(f"{d['file_name']} {data.get('sheet') or ''} {data.get('context') or ''}")
        sem = data.get("semantics")
        if d["doc_type"] == "bank_statement":
            continue  # tiền vào/ra tài khoản ≠ doanh thu/chi phí
        for rn, row in zip(data.get("row_numbers") or [], data.get("rows") or []):
            def cell(role):
                c = idx.get(role)
                return row[c] if c is not None and c < len(row) else None

            iso, _ = parse_date(cell("date"))
            if not iso:
                skipped.append({"file": d["file_name"], "row": rn, "reason": "không đọc được ngày"})
                continue
            side, amt = None, None
            if sem == "cashbook":
                inflow = money.parse_amount(cell("inflow"))
                outflow = money.parse_amount(cell("outflow"))
                if inflow.status == "OK" and inflow.value:
                    side, amt = "cash_in", inflow.value
                elif outflow.status == "OK" and outflow.value:
                    side, amt = "cash_out", outflow.value
            else:
                p = money.parse_amount(cell("amount"))
                if p.status == "OK" and p.value is not None:
                    side = _side_hint(f"{cell('category') or ''}") or doc_side
                    amt = p.value
            if side is None or amt is None:
                skipped.append({"file": d["file_name"], "row": rn, "reason": "không xác định được thu/chi hoặc số tiền"})
                continue
            m = iso[:7]
            months[m][side] += amt
            months[m]["rows"] += 1
            sources.append({"month": m, "side": side, "amount": money.fmt(amt), "file": d["file_name"],
                            "file_id": d["file_id"], "sheet": data.get("sheet"), "row": rn})
    rows = []
    for m in sorted(months):
        v = months[m]
        rows.append({"month": m, "cash_in": v["cash_in"], "cash_out": v["cash_out"],
                     "net_cash": v["cash_in"] - v["cash_out"], "revenue": v["revenue"], "expense": v["expense"],
                     "rows": v["rows"]})
    has = {k: any(r[k] for r in rows) for k in ("cash_in", "cash_out", "revenue", "expense")}
    return {"months": rows, "sources": sources, "skipped": skipped, "has": has}


def consolidate(org_id, file_ids=None):
    """Gộp các bảng có cùng cấu trúc tiêu đề từ nhiều file thành một tập dữ liệu, giữ nguồn từng dòng."""
    groups = defaultdict(list)
    for d in _docs(org_id, file_ids, ("table", "ledger", "bank_statement")):
        header = d["data"].get("header") or []
        sig = tuple(fold(h) for h in header if fold(h))
        if sig:
            groups[sig].append(d)
    out = []
    for sig, docs in groups.items():
        header = docs[0]["data"]["header"]
        rows = []
        for d in docs:
            for rn, row in zip(d["data"].get("row_numbers") or [], d["data"].get("rows") or []):
                rows.append({"values": row, "file": d["file_name"], "file_id": d["file_id"],
                             "sheet": d["data"].get("sheet"), "row": rn})
        out.append({"header": header, "files": sorted({d["file_name"] for d in docs}), "rows": rows,
                    "doc_type": docs[0]["doc_type"], "roles": docs[0]["data"].get("col_index") or {}})
    out.sort(key=lambda g: -len(g["rows"]))
    return out


def ar_ap(rows, paid_by_invoice=None, as_of=None):
    """Công nợ phải thu (HĐ bán ra) / phải trả (HĐ mua vào), tuổi nợ tính từ ngày hoá đơn."""
    paid_by_invoice = paid_by_invoice or {}
    as_of = as_of or date.today().isoformat()
    buckets = ("0-30", "31-60", "61-90", ">90")
    res = {"receivable": {}, "payable": {}, "as_of": as_of, "has_payment_data": bool(paid_by_invoice)}
    for r in rows:
        if r["direction"] not in ("sale", "purchase") or r["status"] not in VERIFIED_SET:
            continue
        side = "receivable" if r["direction"] == "sale" else "payable"
        name, tax = counterparty_of(r)
        cur = r["currency"] or "VND"
        total = money.D(r["total"]) or money.ZERO
        paid = paid_by_invoice.get(r["id"], money.ZERO)
        open_amt = total - paid
        if open_amt <= 0:
            continue
        try:
            age = (date.fromisoformat(as_of) - date.fromisoformat(r["issue_date"])).days
        except (TypeError, ValueError):
            age = None
        b = buckets[0] if age is None or age <= 30 else buckets[1] if age <= 60 else buckets[2] if age <= 90 else buckets[3]
        e = res[side].setdefault((tax or fold(name), cur), {
            "counterparty": name, "tax_id": tax, "currency": cur, "invoiced": money.ZERO, "paid": money.ZERO,
            "open": money.ZERO, **{k: money.ZERO for k in buckets}, "invoices": []})
        e["invoiced"] += total
        e["paid"] += paid
        e["open"] += open_amt
        e[b] += open_amt
        e["invoices"].append({"invoice_id": r["id"], "number": r["number"], "date": r["issue_date"],
                              "total": money.fmt(total), "paid": money.fmt(paid), "age_days": age})
    for side in ("receivable", "payable"):
        res[side] = sorted(res[side].values(), key=lambda e: -e["open"])
    res["buckets"] = buckets
    return res


# ── Thống kê bảng bất kỳ (danh sách, bảng kê) ───────────────────
SENSITIVE_HINTS = ("cccd", "cmnd", "can cuoc", "ho ten", "ho dem", "ho va ten", "ten", "ngay sinh", "dien thoai", "sdt",
                   "email", "dia chi", "so tai khoan", "so tk", "ma so thue", "mst", "ho chieu")
ID_HINTS = ("stt", "ma", "so", "id", "code", "msv", "mssv")


def _sensitive(label):
    f = fold(label)
    return any(f == h or f.startswith(h + " ") or f.endswith(" " + h) or f" {h} " in f" {f} " for h in SENSITIVE_HINTS)


def _num(v):
    if isinstance(v, bool) or v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return money.to_decimal(v)
    p = money.parse_amount(str(v), "USD")
    return p.value if p.status == "OK" else None


def profile(org_id, file_ids=None, filter_column=None, filter_value=None, group_by=None):
    """Đếm dòng, giá trị khác nhau, min/max/trung bình cột số, phân bố cột ít giá trị — cho mọi bảng có tiêu đề."""
    out = []
    for d in _docs(org_id, file_ids, ("table", "ledger", "bank_statement")):
        data = d["data"]
        header = data.get("header") or []
        rows = data.get("rows") or []
        nums = data.get("row_numbers") or []
        cols = [(ci, h) for ci, h in enumerate(header) if str(h).strip()]
        applied = None
        if filter_column:
            fc = next((ci for ci, h in cols if fold(h) == fold(filter_column) or fold(filter_column) in fold(h)), None)
            if fc is None:
                continue
            needle = fold(filter_value)
            keep = [i for i, r in enumerate(rows) if fc < len(r) and needle in fold(r[fc])]
            rows, nums = [rows[i] for i in keep], [nums[i] for i in keep]
            applied = f"'{header[fc]}' chứa '{filter_value}'"
        stats = []
        for ci, h in cols:
            vals = [r[ci] for r in rows if ci < len(r) and r[ci] not in (None, "")]
            distinct = {fold(v) if isinstance(v, str) else str(v) for v in vals}
            numeric = [x for x in (_num(v) for v in vals) if x is not None]
            st = {"column": h, "non_empty": len(vals), "distinct": len(distinct), "sensitive": _sensitive(h)}
            if vals and len(numeric) >= 0.9 * len(vals) and not st["sensitive"]:
                st.update(min=money.fmt(min(numeric)), max=money.fmt(max(numeric)),
                          avg=money.fmt((money.sum_(numeric) / len(numeric)).quantize(money.to_decimal("0.01"))))
            want_dist = fold(group_by) in fold(h) if group_by else (len(distinct) <= 12 and len(distinct) < 0.5 * max(1, len(vals)))
            if want_dist and not st["sensitive"] and len(distinct) <= 50:
                counts = {}
                for v in vals:
                    k = str(v).strip()
                    counts[k] = counts.get(k, 0) + 1
                st["distribution"] = sorted(counts.items(), key=lambda kv: -kv[1])
            st["id_like"] = bool(vals) and len(distinct) == len(vals) == len(rows) and any(
                fold(h) == x or fold(h).startswith(x + " ") for x in ID_HINTS)
            stats.append(st)
        out.append({"file": d["file_name"], "file_id": d["file_id"], "sheet": data.get("sheet"), "header_row": data.get("header_row"),
                    "rows": len(rows), "row_range": [nums[0], nums[-1]] if nums else None, "columns": stats,
                    "skipped_rows": data.get("skipped_rows") or [], "filter": applied})
    return out
