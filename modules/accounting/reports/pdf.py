"""PDF báo cáo từ cùng report spec (giá trị đã tính bằng Decimal), dựng bằng PyMuPDF Story."""

import html
import io
import os
from pathlib import Path

import pymupdf as fitz

from .. import money
from . import spec as S

FONT_CANDIDATES = [
    (r"C:\Windows\Fonts", "arial.ttf", "arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
]
MAX_ROWS_PER_TABLE = 400


def _font():
    for d, reg, bold in FONT_CANDIDATES:
        if os.path.exists(os.path.join(d, reg)):
            return d, reg, bold if os.path.exists(os.path.join(d, bold)) else reg
    return None


def _fmt(v, typ, cur):
    if v in (None, ""):
        return ""
    if typ == "money":
        try:
            d = money.D(v) if isinstance(v, str) else money.to_decimal(v)
        except Exception:
            return html.escape(str(v))
        sc = money.scale(cur)
        d = money.q(d, cur)  # làm tròn ROUND_HALF_UP trước; format() của Python làm tròn half-even
        s = f"{d:,.{sc}f}"
        return s.replace(",", "_").replace(".", ",").replace("_", ".")  # 1.234.567,89 kiểu VN
    if typ == "date" and isinstance(v, str) and len(v) >= 10 and v[4] == "-":
        return f"{v[8:10]}/{v[5:7]}/{v[0:4]}"
    return html.escape(str(v))


def _html(spec):
    cur = spec.get("currency", "VND")
    e = html.escape
    parts = [f"<h1>{e(spec['title'])}</h1>",
             f"<p class='meta'><b>{e(spec.get('org_name') or '')}</b><br/>Kỳ báo cáo: {e(spec.get('period') or '—')} · Đơn vị tiền tệ: {e(cur)}</p>"]
    for sh in spec["sheets"]:
        parts.append(f"<h2>{e(sh['title'])}</h2>")
        cols = sh["columns"]
        rows = sh["rows"][:MAX_ROWS_PER_TABLE]
        head = "".join(f"<th>{e(c['label'])}</th>" for c in cols)
        body = []
        for r in rows:
            tds = []
            for c in cols:
                cls = " class='num'" if c["type"] in ("money", "number", "percent") else ""
                tds.append(f"<td{cls}>{_fmt(r.get(c['key']), c['type'], cur)}</td>")
            body.append("<tr>" + "".join(tds) + "</tr>")
        if sh["totals"] and sh["rows"]:
            t = S.totals(sh)
            tds = []
            for i, c in enumerate(cols):
                if c["key"] in t:
                    tds.append(f"<td class='num'><b>{_fmt(t[c['key']], c['type'], cur)}</b></td>")
                else:
                    tds.append("<td><b>Tổng cộng</b></td>" if i == 0 else "<td></td>")
            body.append("<tr class='tot'>" + "".join(tds) + "</tr>")
        parts.append(f"<table><tr>{head}</tr>{''.join(body)}</table>")
        if len(sh["rows"]) > MAX_ROWS_PER_TABLE:
            parts.append(f"<p class='note'>Chỉ hiển thị {MAX_ROWS_PER_TABLE}/{len(sh['rows'])} dòng — xem đủ trong file Excel.</p>")
        for n in sh.get("notes") or []:
            parts.append(f"<p class='note'>{e(n)}</p>")
    if spec.get("warnings"):
        parts.append("<h2>Cảnh báo chất lượng dữ liệu</h2><ul>")
        for w in spec["warnings"]:
            parts.append(f"<li>{e(w.get('message') if isinstance(w, dict) else str(w))}</li>")
        parts.append("</ul>")
    if spec.get("sources"):
        parts.append("<h2>Nguồn dữ liệu</h2><table><tr><th>Mã</th><th>File</th><th>Vị trí</th><th>SHA-256</th></tr>")
        for s in spec["sources"][:500]:
            parts.append(f"<tr><td>{e(s['id'])}</td><td>{e(s['file'])}</td><td>{e(str(s.get('location') or ''))}</td>"
                         f"<td class='mono'>{e((s.get('sha256') or '')[:16])}…</td></tr>")
        parts.append("</table>")
    return "".join(parts)


CSS = """
* { font-family: vn, sans-serif; }
body { font-size: 9pt; color: #111827; }
h1 { font-size: 16pt; color: #fd5b38; margin-bottom: 4pt; }
h2 { font-size: 12pt; margin-top: 12pt; margin-bottom: 4pt; color: #1f2937; }
.meta { color: #4b5563; }
table { border-collapse: collapse; width: 100%; }
th { background-color: #1f2937; color: #ffffff; font-weight: bold; padding: 3pt; border: 0.5pt solid #9ca3af; }
td { padding: 2pt 3pt; border: 0.5pt solid #d1d5db; }
td.num { text-align: right; }
tr.tot td { background-color: #f3f4f6; }
.note { color: #6b7280; font-style: italic; }
.mono { font-family: monospace; font-size: 7pt; }
"""


def render(spec):
    S.compute(spec)
    f = _font()
    css = CSS
    archive = None
    if f:
        d, reg, bold = f
        archive = fitz.Archive(d)
        css = (f"@font-face {{font-family: vn; src: url({reg});}}"
               f"@font-face {{font-family: vn; src: url({bold}); font-weight: bold;}}") + CSS
    story = fitz.Story(html=_html(spec), user_css=css, archive=archive)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    mediabox = fitz.paper_rect("a4-l")
    where = mediabox + (36, 36, -36, -36)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    data = buf.getvalue()
    doc = fitz.open(stream=data, filetype="pdf")
    doc.set_metadata({"title": spec["title"], "creator": "PM Tools — Accounting AI"})
    for i, page in enumerate(doc, start=1):
        page.insert_text((36, mediabox.height - 18), f"{spec.get('org_name') or ''} · Trang {i}/{doc.page_count}",
                         fontsize=7, color=(0.42, 0.45, 0.5), fontfile=str(Path(f[0]) / f[1]) if f else None,
                         fontname="vnfoot" if f else "helv")
    doc.subset_fonts()
    return doc.tobytes(garbage=3, deflate=True)


def text_of(data):
    """Dùng trong kiểm thử: lấy lại chữ trong PDF để đối chiếu."""
    return "\n".join(p.get_text() for p in fitz.open(stream=data, filetype="pdf"))
