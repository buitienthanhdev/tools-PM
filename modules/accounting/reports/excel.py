"""
Dựng workbook từ report spec bằng openpyxl.

- Ô dữ liệu ghi giá trị; cột tính và dòng tổng ghi CÔNG THỨC (Excel tự tính khi mở).
- Giá trị tương ứng được hệ thống tính độc lập bằng Decimal (spec.compute/totals) và đối chiếu ở verify().
- openpyxl không tính công thức → file không có giá trị cache; mở bằng Excel/LibreOffice sẽ tính.
"""

import io
from datetime import date

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .. import money
from . import spec as S

HEADER_ROW = 5
FIRST = HEADER_ROW + 1
ACCENT = "FD5B38"
HEAD_FILL = PatternFill("solid", fgColor="1F2937")
TOTAL_FILL = PatternFill("solid", fgColor="F3F4F6")
WARN_FILL = PatternFill("solid", fgColor="FEF3C7")
BAD_FILL = PatternFill("solid", fgColor="FEE2E2")
THIN = Side(style="thin", color="D1D5DB")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def money_format(cur):
    return "#,##0;[Red]-#,##0" if money.scale(cur) == 0 else "#,##0.00;[Red]-#,##0.00"


def _value(v, typ):
    if v in (None, ""):
        return None
    if typ in ("money", "number", "percent"):
        try:
            d = money.D(v) if isinstance(v, str) else money.to_decimal(v)
        except Exception:
            return str(v)
        return int(d) if d == d.to_integral_value() and abs(d) < 10**15 else float(d)
    if typ == "date" and isinstance(v, str) and len(v) >= 10:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return v
    return v


def render(spec):
    S.compute(spec)
    wb = Workbook()
    wb.remove(wb.active)
    cur = spec.get("currency", "VND")
    layout = {}
    for sh in spec["sheets"]:
        layout[sh["name"]] = _sheet(wb, spec, sh, cur)
    _warnings(wb, spec)
    _sources(wb, spec)
    wb.properties.title = spec["title"]
    wb.properties.creator = "PM Tools — Accounting AI"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), layout


def _sheet(wb, spec, sh, cur):
    ws = wb.create_sheet(sh["name"])
    cols = sh["columns"]
    ncol = len(cols) + (1 if any(r.get("_src") for r in sh["rows"]) else 0)
    ws["A1"] = sh["title"]
    ws["A1"].font = Font(bold=True, size=14, color=ACCENT)
    ws["A2"] = spec.get("org_name") or ""
    ws["A2"].font = Font(bold=True)
    ws["A3"] = f"Kỳ báo cáo: {spec.get('period') or '—'}    Đơn vị tiền tệ: {cur}"
    ws["A3"].font = Font(italic=True, color="6B7280")
    letters = {c["key"]: get_column_letter(i + 1) for i, c in enumerate(cols)}
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=HEADER_ROW, column=i, value=c["label"])
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX
    src_col = None
    if ncol > len(cols):
        src_col = len(cols) + 1
        h = ws.cell(row=HEADER_ROW, column=src_col, value="Nguồn")
        h.font, h.fill, h.border = Font(bold=True, color="FFFFFF"), HEAD_FILL, BOX
    exprs = {c["key"]: S.parse_expr(c["expr"], [x for x in cols if x is not c]) for c in cols if c.get("expr")}
    fmt_money = money_format(cur)
    last = FIRST + len(sh["rows"]) - 1
    for ri, r in enumerate(sh["rows"]):
        row = FIRST + ri
        for ci, c in enumerate(cols, start=1):
            cell = ws.cell(row=row, column=ci)
            if c["key"] in exprs:
                cell.value = "=" + S.to_excel(exprs[c["key"]], lambda k, row=row: f"{letters[k]}{row}")
            else:
                cell.value = _value(r.get(c["key"]), c["type"])
            cell.border = BOX
            if c["type"] == "money":
                cell.number_format = fmt_money
            elif c["type"] == "number":
                cell.number_format = "#,##0.####"
            elif c["type"] == "percent":
                cell.number_format = "0.0%"
            elif c["type"] == "date":
                cell.number_format = "dd/mm/yyyy"
        if src_col and r.get("_src"):
            sc = ws.cell(row=row, column=src_col, value=", ".join(r["_src"]) if isinstance(r["_src"], list) else r["_src"])
            sc.hyperlink = "#'Nguồn dữ liệu'!A1"
            sc.font = Font(color="2563EB", underline="single")
            sc.border = BOX
    total_row = None
    if sh["totals"] and sh["rows"]:
        total_row = last + 1
        label_col = next((i for i, c in enumerate(cols, start=1) if c["type"] == "text" and c["key"] not in sh["totals"]), 1)
        ws.cell(row=total_row, column=label_col, value="Tổng cộng").font = Font(bold=True)
        for ci, c in enumerate(cols, start=1):
            cell = ws.cell(row=total_row, column=ci)
            cell.fill, cell.border = TOTAL_FILL, BOX
            if c["key"] in sh["totals"]:
                L = letters[c["key"]]
                cell.value = f"=SUBTOTAL(9,{L}{FIRST}:{L}{last})"
                cell.font = Font(bold=True)
                cell.number_format = fmt_money if c["type"] == "money" else "#,##0.####"
    # Định dạng trạng thái cần chú ý
    for ci, c in enumerate(cols, start=1):
        if c["key"] in ("status", "trang_thai", "match_status") and sh["rows"]:
            L = get_column_letter(ci)
            rng = f"{L}{FIRST}:{L}{last}"
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'OR(ISNUMBER(SEARCH("CONFLICT",{L}{FIRST})),ISNUMBER(SEARCH("UNMATCHED",{L}{FIRST})))'], fill=BAD_FILL))
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'OR(ISNUMBER(SEARCH("NEEDS",{L}{FIRST})),ISNUMBER(SEARCH("AMBIGUOUS",{L}{FIRST})),ISNUMBER(SEARCH("POTENTIAL",{L}{FIRST})))'], fill=WARN_FILL))
    ws.freeze_panes = ws.cell(row=FIRST, column=1)
    if sh["rows"]:
        ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(max(ncol, 1))}{last}"
    for i, c in enumerate(cols, start=1):
        width = max([len(str(c["label"]))] + [len(str(r.get(c["key"]) or "")) for r in sh["rows"][:500]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 3), 60)
    if src_col:
        ws.column_dimensions[get_column_letter(src_col)].width = 12
    note_row = (total_row or last) + 2
    for n in sh.get("notes") or []:
        ws.cell(row=note_row, column=1, value=n).font = Font(italic=True, color="6B7280")
        note_row += 1
    for ch in sh.get("charts") or []:
        _chart(ws, sh, ch, letters, last, note_row)
        note_row += 18
    return {"sheet": sh["name"], "first": FIRST, "last": last, "total_row": total_row, "letters": letters}


def _chart(ws, sh, ch, letters, last, anchor_row):
    n = len(sh["rows"])
    if not n:
        return
    from openpyxl.chart.series import SeriesLabel

    start = FIRST if not ch.get("last_n") else max(FIRST, last - int(ch["last_n"]) + 1)
    chart = LineChart() if ch["type"] == "line" else BarChart()
    chart.title = ch["title"]
    chart.height, chart.width = 8, 18
    order = list(letters)
    labels = {c["key"]: c["label"] for c in sh["columns"]}
    for k in ch["values"]:
        chart.add_data(Reference(ws, min_col=order.index(k) + 1, min_row=start, max_row=last), titles_from_data=False)
        chart.series[-1].tx = SeriesLabel(v=labels[k])
    cat_col = order.index(ch["category"]) + 1
    chart.set_categories(Reference(ws, min_col=cat_col, min_row=start, max_row=last))
    ws.add_chart(chart, f"A{anchor_row}")


def _warnings(wb, spec):
    ws = wb.create_sheet("Cảnh báo")
    ws["A1"] = "Cảnh báo chất lượng dữ liệu"
    ws["A1"].font = Font(bold=True, size=13, color=ACCENT)
    ws.append([])
    ws.append(["#", "Mức", "Nội dung"])
    for c in ws[3]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), HEAD_FILL
    for i, w in enumerate(spec.get("warnings") or [], start=1):
        level, text = (w.get("level", "warning"), w.get("message", "")) if isinstance(w, dict) else ("warning", str(w))
        ws.append([i, level, text])
    if not spec.get("warnings"):
        ws.append(["", "", "Không có cảnh báo"])
    ws.column_dimensions["C"].width = 120
    ws.freeze_panes = "A4"


def _sources(wb, spec):
    ws = wb.create_sheet("Nguồn dữ liệu")
    ws["A1"] = "Nguồn dữ liệu (truy vết chứng từ gốc)"
    ws["A1"].font = Font(bold=True, size=13, color=ACCENT)
    ws.append([])
    ws.append(["Mã", "File", "Vị trí", "Phương pháp trích xuất", "SHA-256", "File ID"])
    for c in ws[3]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), HEAD_FILL
    for s in spec.get("sources") or []:
        ws.append([s["id"], s["file"], s.get("location") or "", s.get("method") or "", s.get("sha256") or "", s.get("file_id") or ""])
    for col, w in zip("ABCDEF", (8, 40, 30, 22, 66, 38)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"


def verify(data, spec, layout):
    """
    Xác minh độc lập file vừa ghi: mở lại, kiểm tra từng công thức tổng/cột tính đúng phạm vi,
    giá trị ô dữ liệu đúng spec, và tổng Decimal tính từ dữ liệu. Không dùng LLM.
    """
    wb = load_workbook(io.BytesIO(data), data_only=False)
    checks, ok = [], True

    def fail(msg):
        nonlocal ok
        ok = False
        checks.append({"ok": False, "check": msg})

    for sh in spec["sheets"]:
        lay = layout[sh["name"]]
        if sh["name"] not in wb.sheetnames:
            fail(f"Thiếu sheet {sh['name']}")
            continue
        ws = wb[sh["name"]]
        L = lay["letters"]
        exprs = {c["key"]: S.parse_expr(c["expr"], [x for x in sh["columns"] if x is not c]) for c in sh["columns"] if c.get("expr")}
        bad_cells = 0
        for ri, r in enumerate(sh["rows"]):
            row = lay["first"] + ri
            for c in sh["columns"]:
                v = ws[f"{L[c['key']]}{row}"].value
                if c["key"] in exprs:
                    expect = "=" + S.to_excel(exprs[c["key"]], lambda k, row=row: f"{L[k]}{row}")
                    if v != expect:
                        bad_cells += 1
                elif c["type"] in ("money", "number", "percent") and r.get(c["key"]) not in (None, ""):
                    try:
                        want = money.D(r[c["key"]]) if isinstance(r[c["key"]], str) else money.to_decimal(r[c["key"]])
                        if v is None or isinstance(v, str) or money.to_decimal(v) != want:
                            bad_cells += 1
                    except Exception:
                        bad_cells += 1
        if bad_cells:
            fail(f"{sh['name']}: {bad_cells} ô không khớp spec")
        else:
            checks.append({"ok": True, "check": f"{sh['name']}: {len(sh['rows'])} dòng × {len(sh['columns'])} cột khớp spec"})
        tot = S.totals(sh)
        for k in sh["totals"]:
            if not lay["total_row"]:
                continue
            cell = f"{L[k]}{lay['total_row']}"
            expect = f"=SUBTOTAL(9,{L[k]}{lay['first']}:{L[k]}{lay['last']})"
            if ws[cell].value != expect:
                fail(f"{sh['name']}!{cell}: công thức tổng sai ({ws[cell].value} ≠ {expect})")
            else:
                checks.append({"ok": True, "check": f"{sh['name']}!{cell} = SUBTOTAL phủ đủ {len(sh['rows'])} dòng; tổng tính độc lập (Decimal) = {tot[k]}",
                               "cell": cell, "decimal_total": tot[k]})
    return {"ok": ok, "checks": checks, "recalculated_by_excel_engine": False,
            "note": "Công thức được kiểm tra cấu trúc và phạm vi; giá trị được tính độc lập bằng Decimal. "
                    "File chưa được một trình bảng tính tính lại (không có LibreOffice/Excel trên máy chủ)."}
