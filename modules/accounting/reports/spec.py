"""
Đặc tả báo cáo (report spec) — nguồn duy nhất để dựng Excel/PDF và để sửa báo cáo theo hội thoại.

Một spec gồm các sheet bảng; mỗi cột có kiểu (text|money|number|date|percent) và có thể là cột tính
từ biểu thức (+ − × ÷ giữa các cột và hằng số). Tiền trong spec là chuỗi Decimal.
Sửa báo cáo = áp danh sách phép biến đổi (ops) có kiểm tra lên spec cũ → spec mới (phiên bản mới).
"""

import ast
import copy
from decimal import Decimal, InvalidOperation

from .. import money
from ..extract.base import fold

TYPES = ("text", "money", "number", "date", "percent")


class OpError(Exception):
    def __init__(self, code, msg, details=None):
        super().__init__(msg)
        self.code = code
        self.details = details or {}


def new_spec(title, org_name, period, currency="VND"):
    return {"title": title, "org_name": org_name, "period": period, "currency": currency,
            "sheets": [], "warnings": [], "sources": [], "notes": []}


def table(name, columns, rows, title=None, totals=(), charts=(), notes=()):
    names = []
    for c in columns:
        c.setdefault("type", "text")
        if c["type"] not in TYPES:
            raise OpError("bad_type", f"Kiểu cột không hợp lệ: {c['type']}")
        names.append(c["key"])
    return {"name": name[:31], "title": title or name, "columns": columns, "rows": rows,
            "totals": [t for t in totals if t in names], "charts": list(charts), "notes": list(notes)}


def add_source(spec, file_name, file_id=None, sha256=None, location=None, method=None):
    sid = f"S{len(spec['sources']) + 1}"
    spec["sources"].append({"id": sid, "file": file_name, "file_id": file_id, "sha256": sha256,
                            "location": location, "method": method})
    return sid


# ── Biểu thức cột tính toán ──────────────────────────────────────
_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


def parse_expr(expr, columns):
    """Trả về AST đã kiểm tra; tên trong biểu thức phải là key cột (hoặc nhãn cột, so khớp không dấu)."""
    by_label = {fold(c["label"]).replace(" ", "_"): c["key"] for c in columns}
    by_key = {c["key"]: c["key"] for c in columns}
    src = str(expr)
    for c in sorted(columns, key=lambda c: -len(c["label"])):
        src = src.replace(c["label"], fold(c["label"]).replace(" ", "_"))
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise OpError("bad_expr", f"Biểu thức không hợp lệ: {expr}") from e

    def check(n):
        if isinstance(n, ast.Expression):
            return ast.Expression(check(n.body))
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return ast.BinOp(check(n.left), n.op, check(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return ast.UnaryOp(n.op, check(n.operand))
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return ast.Constant(str(n.value))
        if isinstance(n, ast.Name):
            key = by_key.get(n.id) or by_label.get(n.id) or by_label.get(fold(n.id).replace(" ", "_"))
            if not key:
                raise OpError("unknown_column", f"Không có cột '{n.id}'",
                              {"available": [c["label"] for c in columns]})
            return ast.Name(key, ast.Load())
        raise OpError("bad_expr", "Biểu thức chỉ được dùng cột, số và + - * /")

    return check(tree)


def eval_expr(tree, row, cur="VND"):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return Decimal(n.value)
        if isinstance(n, ast.Name):
            v = row.get(n.id)
            if v in (None, ""):
                return None
            try:
                return money.to_decimal(v)
            except (InvalidOperation, TypeError):
                return None
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            return None if v is None else -v
        a, b = ev(n.left), ev(n.right)
        if a is None or b is None:
            return None
        if isinstance(n.op, ast.Div):
            return None if b == 0 else a / b
        return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b}[type(n.op)]

    v = ev(tree)
    return v


def to_excel(tree, cell_of):
    """AST → công thức Excel; cell_of(key) trả về địa chỉ ô cùng dòng."""
    def go(n, parent_prec=0):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return cell_of(n.id)
        if isinstance(n, ast.UnaryOp):
            return f"-{go(n.operand, 3)}"
        prec = 1 if isinstance(n.op, (ast.Add, ast.Sub)) else 2
        s = f"{go(n.left, prec)}{_OPS[type(n.op)]}{go(n.right, prec + (1 if isinstance(n.op, (ast.Sub, ast.Div)) else 0))}"
        return f"({s})" if prec < parent_prec else s

    return go(tree)


def compute(spec):
    """Tính lại mọi cột biểu thức (Decimal) — giá trị dùng cho PDF, xác minh và hiển thị."""
    cur = spec.get("currency", "VND")
    for sh in spec["sheets"]:
        for c in sh["columns"]:
            if c.get("expr"):
                tree = parse_expr(c["expr"], [x for x in sh["columns"] if not x.get("expr") or x is not c])
                for r in sh["rows"]:
                    v = eval_expr(tree, r, cur)
                    if v is not None and c["type"] == "money":
                        v = money.q(v, cur)
                    r[c["key"]] = money.fmt(v) if v is not None else None
    return spec


def totals(sheet):
    out = {}
    for k in sheet["totals"]:
        out[k] = money.fmt(money.sum_(money.D(r.get(k)) if isinstance(r.get(k), str) else r.get(k)
                                      for r in sheet["rows"] if r.get(k) not in (None, "")))
    return out


# ── Phép sửa báo cáo ─────────────────────────────────────────────
def _sheet(spec, name):
    if name is None and len(spec["sheets"]) == 1:
        return spec["sheets"][0]
    for s in spec["sheets"]:
        if name and fold(s["name"]) == fold(name):
            return s
    raise OpError("unknown_sheet", f"Không có sheet '{name}'", {"available": [s["name"] for s in spec["sheets"]]})


def _col(sheet, name):
    for c in sheet["columns"]:
        if name and (c["key"] == name or fold(c["label"]) == fold(name)):
            return c
    raise OpError("unknown_column", f"Không có cột '{name}' trong sheet '{sheet['name']}'",
                  {"available": [c["label"] for c in sheet["columns"]]})


def _key(sheet, label):
    base = fold(label).replace(" ", "_")[:30] or "col"
    k, i = base, 2
    keys = {c["key"] for c in sheet["columns"]}
    while k in keys:
        k, i = f"{base}_{i}", i + 1
    return k


def apply_ops(spec, ops):
    new = copy.deepcopy(spec)
    log = []
    for op in ops:
        kind = op.get("op")
        if kind == "add_computed_column":
            sh = _sheet(new, op.get("sheet"))
            parse_expr(op["expr"], sh["columns"])
            label = str(op.get("label") or op["expr"])[:60]
            col = {"key": _key(sh, label), "label": label, "type": op.get("type") or "money", "expr": op["expr"]}
            sh["columns"].append(col)
            if op.get("total", col["type"] == "money"):
                sh["totals"].append(col["key"])
            log.append(f"Thêm cột tính '{label}' = {op['expr']} vào sheet '{sh['name']}'")
        elif kind == "add_chart":
            sh = _sheet(new, op.get("sheet"))
            cat = _col(sh, op.get("category"))
            vals = [_col(sh, v)["key"] for v in op.get("values") or []]
            if not vals:
                raise OpError("bad_op", "Biểu đồ cần ít nhất một cột giá trị")
            ctype = op.get("type") if op.get("type") in ("bar", "line") else "bar"
            sh["charts"].append({"type": ctype, "title": str(op.get("title") or "Biểu đồ")[:80],
                                 "category": cat["key"], "values": vals, "last_n": op.get("last_n")})
            log.append(f"Thêm biểu đồ {ctype} '{op.get('title') or ''}' vào sheet '{sh['name']}'")
        elif kind == "split_sheet":
            sh = _sheet(new, op.get("sheet"))
            c = _col(sh, op.get("column"))
            needle = fold(op.get("contains") or op.get("equals") or "")
            if not needle:
                raise OpError("bad_op", "Cần giá trị để tách sheet")
            exact = "equals" in op
            match = [r for r in sh["rows"] if (fold(r.get(c["key"])) == needle if exact else needle in fold(r.get(c["key"])))]
            if not match:
                raise OpError("no_rows", f"Không có dòng nào có '{op.get('contains') or op.get('equals')}' ở cột '{c['label']}'")
            name = str(op.get("new_sheet") or (op.get("contains") or op.get("equals")))[:31]
            new["sheets"].append({**copy.deepcopy({k: v for k, v in sh.items() if k != "rows"}),
                                  "name": name, "title": f"{sh['title']} — {name}", "rows": copy.deepcopy(match), "charts": []})
            if op.get("remove_from_source"):
                ids = {id(r) for r in match}
                sh["rows"] = [r for r in sh["rows"] if id(r) not in ids]
            log.append(f"Tách {len(match)} dòng sang sheet '{name}'")
        elif kind == "rename_column":
            sh = _sheet(new, op.get("sheet"))
            c = _col(sh, op.get("column"))
            old = c["label"]
            c["label"] = str(op["label"])[:60]
            log.append(f"Đổi tên cột '{old}' → '{c['label']}'")
        elif kind == "remove_column":
            sh = _sheet(new, op.get("sheet"))
            c = _col(sh, op.get("column"))
            deps = [x["label"] for x in sh["columns"] if x.get("expr") and c["key"] in ast.dump(parse_expr(x["expr"], sh["columns"]))]
            if deps:
                raise OpError("in_use", f"Cột '{c['label']}' đang được dùng bởi cột tính: {', '.join(deps)}")
            sh["columns"] = [x for x in sh["columns"] if x is not c]
            sh["totals"] = [t for t in sh["totals"] if t != c["key"]]
            sh["charts"] = [ch for ch in sh["charts"] if c["key"] not in ch["values"] and ch["category"] != c["key"]]
            log.append(f"Bỏ cột '{c['label']}'")
        elif kind == "sort":
            sh = _sheet(new, op.get("sheet"))
            c = _col(sh, op.get("column"))

            def keyf(r, c=c):
                v = r.get(c["key"])
                if c["type"] in ("money", "number", "percent"):
                    return (v is None, money.D(v) if isinstance(v, str) else (v or 0))
                return (v is None, str(v or ""))

            sh["rows"].sort(key=keyf, reverse=bool(op.get("desc")))
            log.append(f"Sắp xếp theo '{c['label']}'{' giảm dần' if op.get('desc') else ''}")
        elif kind == "filter_rows":
            sh = _sheet(new, op.get("sheet"))
            c = _col(sh, op.get("column"))
            before = len(sh["rows"])
            sh["rows"] = [r for r in sh["rows"] if _keep(r.get(c["key"]), op.get("cmp", "contains"), op.get("value"), c["type"])]
            log.append(f"Lọc '{c['label']}' {op.get('cmp')} {op.get('value')}: {before} → {len(sh['rows'])} dòng")
        elif kind == "convert_currency":
            sh = _sheet(new, op.get("sheet"))
            c = _col(sh, op.get("column"))
            if not op.get("rate") or not op.get("rate_source"):
                raise OpError("needs_rate", "Cần tỷ giá và nguồn tỷ giá hợp lệ để quy đổi — hệ thống không tự chọn tỷ giá")
            rate = money.to_decimal(str(op["rate"]))
            to = (op.get("to") or "VND").upper()
            label = f"{c['label']} ({to})"
            col = {"key": _key(sh, label), "label": label, "type": "money",
                   "note": f"tỷ giá {money.fmt(rate)} — nguồn: {op['rate_source']}"}
            for r in sh["rows"]:
                v = r.get(c["key"])
                r[col["key"]] = money.fmt(money.q(money.D(v) * rate, to)) if v not in (None, "") else None
            sh["columns"].append(col)
            if c["key"] in sh["totals"]:
                sh["totals"].append(col["key"])
            log.append(f"Quy đổi '{c['label']}' sang {to} theo tỷ giá {money.fmt(rate)} ({op['rate_source']})")
        elif kind == "rename_sheet":
            sh = _sheet(new, op.get("sheet"))
            old, sh["name"] = sh["name"], str(op["name"])[:31]
            log.append(f"Đổi tên sheet '{old}' → '{sh['name']}'")
        else:
            raise OpError("unknown_op", f"Thao tác không hỗ trợ: {kind}")
    compute(new)
    return new, log


def _keep(v, cmp, value, typ):
    if cmp == "contains":
        return fold(value) in fold(v)
    if cmp == "eq":
        return fold(v) == fold(value)
    if v in (None, ""):
        return False
    try:
        a = money.D(v) if isinstance(v, str) else money.to_decimal(v)
        b = money.to_decimal(str(value))
    except (InvalidOperation, TypeError):
        return False
    return {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b}.get(cmp, False)
