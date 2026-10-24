"""
Phân tích bảng dữ liệu bất kỳ đã trích xuất (danh sách, bảng kê, bảng lương…): lọc, nhóm, tổng, trung bình,
nhỏ/lớn nhất, top N, liệt kê — tính bằng Decimal, mỗi kết quả giữ dòng nguồn.

Tên cột do người dùng/AI gọi ("giới tính", "điểm trung bình", "doanh thu") được ánh xạ sang cột thật qua:
khớp chính xác → chứa nhau → nhóm từ đồng nghĩa → so khớp gần đúng (RapidFuzz) → theo giá trị trong cột
(ví dụ lọc "Nữ" mà không có cột tên "Giới tính" thì dùng cột chứa giá trị "Nữ"). Không đoán được → hỏi lại,
kèm danh sách cột thật.
Cột ảo "Tháng" / "Quý" / "Năm" được suy ra từ cột ngày khi bảng không có cột đó.
"""

import re

from rapidfuzz import fuzz

from .. import money
from ..extract.base import fold, parse_date
from .analysis import _docs, _num

SYNONYMS = {
    "gender": ["gioi tinh", "phai", "gioi", "sex", "gender", "nam nu"],
    "score": ["diem", "diem tb", "diem trung binh", "dtb", "tbc", "tbctk", "tbctk 10", "tbc tl", "gpa", "diem tich luy",
              "diem tong ket", "trung binh chung", "tbcht"],
    "rank": ["xep loai", "hoc luc", "loai", "xep hang", "rank"],
    "name": ["ho ten", "ho va ten", "ten", "ho dem", "full name", "name", "ten nhan vien", "ten sinh vien"],
    "revenue": ["doanh thu", "doanh so", "tien ban", "ban duoc", "thanh tien", "tong tien", "so tien", "gia tri", "tien hang", "amount", "revenue", "sales",
                "tong thanh toan", "tong cong"],
    "quantity": ["so luong", "sl", "qty", "quantity", "khoi luong"],
    "price": ["don gia", "gia", "unit price", "price", "gia ban"],
    "customer": ["khach hang", "ten khach hang", "nguoi mua", "doi tuong", "customer", "client", "don vi mua", "ten kh"],
    "supplier": ["nha cung cap", "ncc", "nguoi ban", "supplier", "vendor", "ten ncc"],
    "product": ["mat hang", "hang hoa", "ten hang", "ten hang hoa", "san pham", "ten san pham", "item", "product", "ma hang",
                "hang"],
    "salary": ["luong", "thuc linh", "thuc nhan", "luong co ban", "tong luong", "net"],
    "department": ["phong ban", "bo phan", "phong", "department", "khoa", "lop", "lop hoc", "nganh"],
    "date": ["ngay", "ngay giao dich", "ngay gd", "ngay ct", "ngay chung tu", "ngay hd", "ngay ban", "ngay lap", "date",
             "ngay hach toan", "ngay hoa don"],
    "birth": ["ngay sinh", "dob", "sinh ngay"],
    "place": ["noi sinh", "que quan", "dia chi", "tinh thanh"],
    "id": ["ma", "ma so", "id", "code", "ma sv", "msv", "mssv", "ma nv", "ma kh", "ma hang", "so chung tu", "so hd", "so ct"],
}
VIRTUAL = {"month": ("thang", "month", "ky", "theo thang"), "quarter": ("quy", "quarter"), "year": ("nam", "year")}
OPS = ("count", "sum", "avg", "min", "max", "top", "bottom", "list")
FILTER_OPS = ("eq", "ne", "contains", "gt", "gte", "lt", "lte")


class ColumnNotFound(Exception):
    def __init__(self, want, tables):
        self.want = want
        cols = []
        for t in tables[:3]:
            cols += [h for h in t["header"] if str(h).strip()]
        super().__init__(f"Không thấy cột '{want}'. Các cột hiện có: " + ", ".join(dict.fromkeys(cols))[:600])


def _words_in(a, b):
    """a xuất hiện trong b theo nguyên từ ("hang" ∈ "mat hang" nhưng ∉ "thang")."""
    return f" {a} " in f" {b} "


def _groups_of(fw):
    return [g for g, syns in SYNONYMS.items() if any(fw == s or (len(s) >= 3 and (_words_in(s, fw) or _words_in(fw, s))) for s in syns)]


def resolve(header, want, rows=None, numeric=False):
    """→ (chỉ số cột | 'month'/'quarter'/'year', ghi chú) hoặc (None, None)."""
    fw = fold(want)
    if not fw:
        return None, None
    labels = [(ci, fold(h)) for ci, h in enumerate(header) if fold(h)]

    def ok(ci):
        return not numeric or rows is None or _numeric_share(rows, ci) >= 0.8

    for ci, h in labels:
        if h == fw and ok(ci):
            return ci, None
    # "lương" chung chung = lương thực nhận (không phải lương cơ bản) nếu bảng có cột đó
    if "luong" in fw.split() and "co ban" not in fw:
        net = [ci for ci, h in labels if ok(ci) and h in ("thuc linh", "thuc nhan", "luong thuc nhan", "luong thuc linh", "tong luong")]
        if net:
            return net[0], f"'{want}' được hiểu là cột '{header[net[0]]}' (lương thực nhận; hỏi rõ 'lương cơ bản' nếu cần cột đó)"
    cands = [ci for ci, h in labels if ok(ci) and len(h) >= 2 and (fw in h.split() or h in fw.split() or (len(fw) >= 4 and fw in h)
                                                                    or (len(h) >= 4 and h in fw))]
    if cands:
        return _pick(header, cands, want)
    for v, words in VIRTUAL.items():
        if fw in words:
            return v, None
    for g in _groups_of(fw):
        scored = []
        for ci, h in labels:
            best = max((3 if h == s else 2 if h.startswith(s + " ") else 1 if len(s) >= 3 and _words_in(s, h) else 0)
                       for s in SYNONYMS[g])
            if best and ok(ci):
                scored.append((-best, ci))
        if scored:
            scored.sort()
            top = [ci for sc, ci in scored if sc == scored[0][0]]
            return _pick(header, top, want, g)
    scored = sorted(((fuzz.token_set_ratio(fw, h), ci) for ci, h in labels if ok(ci)), reverse=True)
    if scored and scored[0][0] >= 85:
        return scored[0][1], f"'{want}' được hiểu là cột '{header[scored[0][1]]}' (gần đúng)"
    return None, None


def _pick(header, cands, want, group=None):
    ci = cands[0]
    if fold(header[ci]) == fold(want) or len(cands) == 1:
        return ci, (f"'{want}' được hiểu là cột '{header[ci]}'" if group and fold(header[ci]) != fold(want) else None)
    others = ", ".join(f"'{header[c]}'" for c in cands[1:4])
    return ci, f"'{want}' được hiểu là cột '{header[ci]}' (còn có {others} — hãy nói rõ nếu cần cột khác)"


def _numeric_share(rows, ci):
    vals = [r[ci] for r in rows if ci < len(r) and r[ci] not in (None, "")]
    if not vals:
        return 0
    return sum(1 for v in vals if _num(v) is not None) / len(vals)


def _value_column(header, rows, value):
    """Cột (ít giá trị khác nhau) có chứa đúng giá trị cần lọc — dùng khi tên cột không khớp."""
    fv = fold(value)
    for ci, h in enumerate(header):
        vals = {fold(r[ci]) for r in rows if ci < len(r) and r[ci] not in (None, "")}
        if 1 < len(vals) <= 50 and fv in vals:
            return ci
    return None


def _date_col(t):
    idx = t["col_index"]
    if "date" in idx:
        return idx["date"]
    ci, _ = resolve(t["header"], "ngày")
    return ci if isinstance(ci, int) else None


def _virtual(row, t, kind):
    dc = _date_col(t)
    if dc is None or dc >= len(row):
        return None
    iso, _ = parse_date(row[dc])
    if not iso:
        return None
    if kind == "month":
        return iso[:7]
    if kind == "year":
        return iso[:4]
    return f"{iso[:4]}-Q{(int(iso[5:7]) - 1) // 3 + 1}"


def _cell(row, t, col):
    if isinstance(col, str):
        return _virtual(row, t, col)
    return row[col] if col < len(row) else None


def _match(cell, op, value, col):
    if op in ("eq", "ne") and isinstance(col, str):  # cột ảo: "5" / "05/2026" / "2026-05" / "tháng 5"
        eq = _period_eq(cell, value, col)
        return eq if op == "eq" else not eq
    if op in ("gt", "gte", "lt", "lte"):
        a, b = _num(cell), _num(value)
        if a is None or b is None:
            ia, _ = parse_date(cell)
            ib, _ = parse_date(value)
            if not ia or not ib:
                return False
            a, b = ia, ib
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    fc, fv = fold(cell), fold(value)
    if op == "contains":
        return fv in fc
    a, b = _num(cell), _num(value)
    eq = (a == b) if a is not None and b is not None else fc == fv
    return eq if op == "eq" else not eq


def _period_eq(cell, value, col):
    if not cell:
        return False
    nums = [int(x) for x in re.findall(r"\d+", str(value))]
    if not nums:
        return False
    if col == "month":
        y, m = int(cell[:4]), int(cell[5:7])
        if len(nums) == 1:
            return nums[0] == m if nums[0] <= 12 else nums[0] == y
        a, b = nums[0], nums[1]
        return (a == m and b == y) or (a == y and b == m)
    if col == "year":
        return nums[0] == int(cell[:4])
    return str(value).upper().replace(" ", "") in cell.replace("-", "")  # "Q2" trong "2026Q2"


def tables(org_id, file_ids):
    out = []
    for d in _docs(org_id, file_ids, ("table", "ledger", "bank_statement")):
        data = d["data"]
        header = [str(h).strip() if h is not None else "" for h in data.get("header") or []]
        if not header or not data.get("rows"):
            continue
        out.append({"file": d["file_name"], "file_id": d["file_id"], "sheet": data.get("sheet"), "header": header,
                    "rows": data.get("rows") or [], "row_numbers": data.get("row_numbers") or [],
                    "col_index": data.get("col_index") or {}})
    return out


def _label_cols(t, exclude):
    """Cột dùng để gọi tên một dòng: mã định danh + họ tên (tối đa 3 cột)."""
    out = []
    for ci, h in enumerate(t["header"]):
        f = fold(h)
        if ci in exclude or not f or f == "stt":
            continue
        if "id" in _groups_of(f) or "name" in _groups_of(f) or f in ("ho dem", "ten"):
            vals = {fold(r[ci]) for r in t["rows"][:200] if ci < len(r) and r[ci] not in (None, "")}
            if len(vals) > 1:
                out.append(ci)
        if len(out) >= 3:
            break
    if not out:  # bảng kê: dùng cột chữ đầu tiên
        out = [ci for ci, h in enumerate(t["header"]) if h and ci not in exclude and _numeric_share(t["rows"], ci) < 0.5][:1]
    return out


def analyze(org_id, file_ids, operation, value_column=None, group_by=None, filters=(), limit=None, sort="desc"):
    """→ {"results": [...mỗi bảng...], "notes": [...]}; ColumnNotFound nếu không ánh xạ được cột trên bảng nào."""
    if operation not in OPS:
        raise ValueError(f"Phép tính không hợp lệ: {operation}")
    tabs = tables(org_id, file_ids)
    if not tabs:
        return {"results": [], "notes": []}
    results, notes, missing = [], [], None
    for t in tabs:
        header, rows = t["header"], t["rows"]
        r_notes = []
        try:
            flt = []
            for f in filters or ():
                col, note = resolve(header, f.get("column") or "", rows)
                if col is None and f.get("value") not in (None, ""):
                    col = _value_column(header, rows, f["value"])
                    if col is not None:
                        note = f"Lọc '{f['value']}' theo cột '{header[col]}' (cột chứa giá trị này)"
                if col is None:
                    raise ColumnNotFound(f.get("column") or f.get("value"), [t])
                if isinstance(col, str) and _date_col(t) is None:
                    # Bảng không có cột ngày (vd bảng lương tháng 5): điều kiện tháng/năm không áp được → bỏ, nói rõ
                    r_notes.append(f"Bảng '{t['sheet']}' không có cột ngày — bỏ điều kiện '{f.get('column')} = {f.get('value')}', tính trên toàn bảng")
                    continue
                if note:
                    r_notes.append(note)
                flt.append((col, f.get("op") or "eq", f.get("value")))
            vcol = None
            if operation not in ("count", "list"):
                if not value_column:
                    raise ColumnNotFound("(cột cần tính)", [t])
                vcol, note = resolve(header, value_column, rows, numeric=True)
                if vcol is None or isinstance(vcol, str):
                    raise ColumnNotFound(value_column, [t])
                if note:
                    r_notes.append(note)
            gcol = None
            if group_by:
                gcol, note = resolve(header, group_by, rows)
                if gcol is None:
                    raise ColumnNotFound(group_by, [t])
                if isinstance(gcol, str) and _date_col(t) is None:
                    raise ColumnNotFound(group_by, [t])
                if note:
                    r_notes.append(note)
        except ColumnNotFound as e:
            missing = missing or e
            continue
        keep = []
        for i, row in enumerate(rows):
            if all(_match(_cell(row, t, c), op, v, c) for c, op, v in flt):
                keep.append(i)
        res = {"file": t["file"], "file_id": t["file_id"], "sheet": t["sheet"], "total_rows": len(rows), "matched": len(keep),
               "filters": [(_colname(header, c), op, v) for c, op, v in flt], "value_column": _colname(header, vcol),
               "group_by": _colname(header, gcol), "notes": r_notes, "operation": operation}
        vals = {}
        bad = 0
        if vcol is not None:
            for i in keep:
                x = _num(rows[i][vcol]) if vcol < len(rows[i]) else None
                if x is None and vcol < len(rows[i]) and rows[i][vcol] not in (None, ""):
                    bad += 1
                vals[i] = x
        res["non_numeric"] = bad
        if gcol is not None:
            groups = {}
            for i in keep:
                k = _cell(rows[i], t, gcol)
                k = "(trống)" if k in (None, "") else str(k).strip()
                groups.setdefault(k, []).append(i)
            res["groups"] = []
            for k, idx in groups.items():
                nums = [vals[i] for i in idx if vals.get(i) is not None]
                res["groups"].append({"key": k, "count": len(idx), **_agg(nums), "rows": [t["row_numbers"][i] for i in idx][:2000]})
            key = {"count": "count", "sum": "sum", "avg": "avg", "min": "min", "max": "max", "top": "sum", "bottom": "sum"}.get(operation, "count")
            rev = operation != "bottom" and sort != "asc"
            if gcol in ("month", "quarter", "year") and operation in ("count", "sum", "avg", "list"):
                res["groups"].sort(key=lambda g: g["key"])
            else:
                res["groups"].sort(key=lambda g: (g.get(key) is None, -(g.get(key) or 0) if rev else (g.get(key) or 0)))
            if operation in ("top", "bottom") and limit:
                res["groups"] = res["groups"][:limit]
        nums = [vals[i] for i in keep if vals.get(i) is not None]
        res.update(_agg(nums))
        if operation in ("top", "bottom", "list", "min", "max") and gcol is None:
            order = keep
            if vcol is not None:
                rev = operation in ("top", "max") or (operation == "list" and sort == "desc")
                order = sorted((i for i in keep if vals.get(i) is not None), key=lambda i: vals[i], reverse=rev)
            n = limit or {"top": 5, "bottom": 5, "min": 1, "max": 1}.get(operation, 5000)
            if operation in ("min", "max") and order:  # mọi dòng bằng giá trị lớn/nhỏ nhất
                best = vals[order[0]]
                order = [i for i in order if vals[i] == best][:20]
            else:
                order = order[:n]
            lab = _label_cols(t, {vcol} if vcol is not None else set())
            res["label_columns"] = [header[c] for c in lab]
            res["items"] = [{"row": t["row_numbers"][i], "label": " ".join(str(rows[i][c]) for c in lab if c < len(rows[i]) and rows[i][c] not in (None, "")),
                             "value": vals.get(i), "values": rows[i]} for i in order]
            res["header"] = header
        results.append(res)
        notes += r_notes
    if not results and missing:
        raise missing
    return {"results": results, "notes": list(dict.fromkeys(notes))}


def _agg(nums):
    if not nums:
        return {"sum": None, "avg": None, "min": None, "max": None, "n_values": 0}
    s = money.sum_(nums)
    return {"sum": s, "avg": (s / len(nums)), "min": min(nums), "max": max(nums), "n_values": len(nums)}


def _colname(header, c):
    if c is None:
        return None
    if isinstance(c, str):
        return {"month": "Tháng", "quarter": "Quý", "year": "Năm"}[c]
    return header[c]


def describe_filters(filters):
    sym = {"eq": "=", "ne": "≠", "contains": "chứa", "gt": ">", "gte": "≥", "lt": "<", "lte": "≤"}
    return ", ".join(f"{c} {sym.get(op, op)} {v}" for c, op, v in filters)
