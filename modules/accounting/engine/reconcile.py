"""
Đối soát xác định (không dùng LLM): sao kê ngân hàng ↔ sổ kế toán / chứng từ thanh toán / hoá đơn.

Tầng so khớp (theo thứ tự, mỗi giao dịch chỉ dùng một lần):
1. CONFLICTED        — cùng tham chiếu nhưng khác số tiền.
2. MATCHED_EXACT     — cùng số tiền, tham chiếu khớp, ngày trong dung sai, ứng viên duy nhất.
3. MATCHED_VERIFIED  — cùng số tiền, ngày trong dung sai, đối tượng/diễn giải khớp, duy nhất cả hai chiều.
4. POTENTIAL_MATCH   — cùng số tiền, ngày trong dung sai, duy nhất cả hai chiều, không có bằng chứng thêm;
                       hoặc nhiều-một / một-nhiều có đúng một tổ hợp cộng khớp.
5. AMBIGUOUS         — nhiều ứng viên có cùng mức bằng chứng → không tự chọn, liệt kê tất cả.
6. UNMATCHED         — còn lại.
Hoà giữa các ứng viên chỉ được phân xử bằng bằng chứng (tham chiếu, đối tượng, diễn giải),
không bằng thứ tự dòng hay ngày gần hơn. Chênh lệch chỉ báo cáo; không tạo bút toán cân bằng.
"""

import itertools
import re
from datetime import date

from .. import money
from ..extract.base import fold

MAX_COMBO = 3
MAX_COMBO_CANDIDATES = 25


def norm_ref(s):
    return re.sub(r"[^0-9A-Z]", "", fold(s).upper())


def _tokens(s):
    return {t for t in fold(s).split() if len(t) >= 3}


def _sim(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _days(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return None


def _ref_hit(bank, book):
    """Tham chiếu sổ (số chứng từ/số hoá đơn) trùng tham chiếu sao kê hoặc là một từ trong diễn giải sao kê."""
    br, kr = norm_ref(bank.get("reference")), norm_ref(book.get("reference"))
    if br and kr and br == kr:
        return True
    if len(kr) < 3:
        return False
    words = set(re.findall(r"[0-9A-Z]+", fold(bank.get("description")).upper()))
    if kr in words:
        return True
    if kr.isdigit():
        short = kr.lstrip("0")
        return len(short) >= 3 and any(w.isdigit() and w.lstrip("0") == short for w in words)
    return len(kr) >= 6 and kr in norm_ref(bank.get("description"))


def _strength(bank, book):
    """0: chỉ số tiền + ngày; 1: đối tượng/diễn giải khớp; 2: tham chiếu khớp."""
    if _ref_hit(bank, book):
        return 2
    cs = _sim(bank.get("counterparty") or bank.get("description"), book.get("counterparty"))
    ds = _sim(bank.get("description"), book.get("description"))
    return 1 if (cs >= 0.5 or ds >= 0.4) else 0


def _reasons(bank, book):
    out = [f"số tiền bằng nhau ({bank['amount']})"]
    dd = _days(bank.get("date"), book.get("date"))
    if dd is not None:
        out.append(f"lệch {dd} ngày")
    if _ref_hit(bank, book):
        out.append(f"tham chiếu khớp: {book.get('reference') or bank.get('reference')}")
    cs = _sim(bank.get("counterparty") or bank.get("description"), book.get("counterparty"))
    if cs >= 0.5:
        out.append(f"đối tượng khớp ({cs:.0%})")
    ds = _sim(bank.get("description"), book.get("description"))
    if ds >= 0.4:
        out.append(f"diễn giải giống ({ds:.0%})")
    return out


def reconcile(bank_rows, book_rows, tolerance_days=3):
    """bank_rows/book_rows: dict có id, date, amount (chuỗi Decimal có dấu), reference, description, counterparty."""
    bank = [b for b in bank_rows if b.get("amount") is not None]
    book = [k for k in book_rows if k.get("amount") is not None]
    used_b, used_k = set(), set()
    matches = []

    def in_window(b, k):
        dd = _days(b.get("date"), k.get("date"))
        return dd is not None and dd <= tolerance_days

    def same(b, k):
        return money.D(b["amount"]) == money.D(k["amount"]) and in_window(b, k)

    # 1. Cùng tham chiếu nhưng khác số tiền
    for b in bank:
        br = norm_ref(b.get("reference"))
        if len(br) < 4:
            continue
        for k in book:
            if k["id"] not in used_k and norm_ref(k.get("reference")) == br and money.D(k["amount"]) != money.D(b["amount"]):
                matches.append(_m("CONFLICTED", [b], [k], 0.0,
                                  [f"cùng tham chiếu {b.get('reference')} nhưng sao kê {b['amount']} ≠ sổ {k['amount']}"]))
                used_b.add(b["id"])
                used_k.add(k["id"])

    # 2–5. So khớp một-một theo mức bằng chứng giảm dần
    for level, status, score in ((2, "MATCHED_EXACT", 1.0), (1, "MATCHED_VERIFIED", 0.9), (0, "POTENTIAL_MATCH", 0.6)):
        for b in bank:
            if b["id"] in used_b:
                continue
            cands = [k for k in book if k["id"] not in used_k and same(b, k)]
            if not cands:
                continue
            best = max(_strength(b, k) for k in cands)
            if best != level:
                continue
            top = [k for k in cands if _strength(b, k) == level]
            rivals = [x for x in bank if x["id"] not in used_b and x["id"] != b["id"]
                      and any(same(x, k) and _strength(x, k) >= level for k in top)]
            if len(top) == 1 and not rivals:
                matches.append(_m(status, [b], top, score, _reasons(b, top[0])))
                used_b.add(b["id"])
                used_k.add(top[0]["id"])
            else:
                group_b = [b] + rivals
                matches.append(_m("AMBIGUOUS", group_b, top, 0.3, [
                    f"{len(group_b)} giao dịch sao kê và {len(top)} bút toán cùng số tiền {b['amount']} "
                    "với mức bằng chứng như nhau — không tự chọn"]))
                used_b.update(x["id"] for x in group_b)
                used_k.update(k["id"] for k in top)

    # 6. Nhiều-một và một-nhiều
    _combos(bank, book, used_b, used_k, matches, tolerance_days, many_side="book")
    _combos(book, bank, used_k, used_b, matches, tolerance_days, many_side="bank")

    for b in bank:
        if b["id"] not in used_b:
            matches.append(_m("UNMATCHED", [b], [], 0.0, ["không có bút toán tương ứng trong khoảng ngày cho phép"]))
    for k in book:
        if k["id"] not in used_k:
            matches.append(_m("UNMATCHED", [], [k], 0.0, ["không có giao dịch sao kê tương ứng"]))
    return matches, summary(bank, book, matches)


def _combos(singles, pool, used_single, used_pool, matches, tol, many_side):
    for s in singles:
        if s["id"] in used_single:
            continue
        target = money.D(s["amount"])
        cands = []
        for p in pool:
            pa = money.D(p["amount"])
            dd = _days(s.get("date"), p.get("date"))
            if (p["id"] not in used_pool and (pa > 0) == (target > 0) and abs(pa) < abs(target)
                    and dd is not None and dd <= tol * 3):
                cands.append(p)
        if len(cands) < 2 or len(cands) > MAX_COMBO_CANDIDATES:
            continue
        found = []
        for n in range(2, MAX_COMBO + 1):
            for combo in itertools.combinations(cands, n):
                if money.sum_(money.D(c["amount"]) for c in combo) == target:
                    found.append(combo)
                    if len(found) > 1:
                        break
            if len(found) > 1:
                break
        if not found:
            continue
        what = "bút toán" if many_side == "book" else "giao dịch sao kê"
        if len(found) == 1:
            combo = list(found[0])
            bank_side, book_side = ([s], combo) if many_side == "book" else (combo, [s])
            matches.append(_m("POTENTIAL_MATCH", bank_side, book_side, 0.55,
                              [f"{len(combo)} {what} cộng lại đúng bằng {s['amount']}"]))
            used_single.add(s["id"])
            used_pool.update(c["id"] for c in combo)
        else:
            members = list({c["id"]: c for cmb in found for c in cmb}.values())
            bank_side, book_side = ([s], members) if many_side == "book" else (members, [s])
            matches.append(_m("AMBIGUOUS", bank_side, book_side, 0.2,
                              [f"có nhiều tổ hợp {what} cộng bằng {s['amount']} — không tự chọn"]))
            used_single.add(s["id"])
            used_pool.update(c["id"] for c in members)


def _m(status, bank, book, score, reasons):
    return {"status": status, "bank": [b["id"] for b in bank], "book": [k["id"] for k in book],
            "bank_rows": bank, "book_rows": book, "score": score, "reasons": reasons}


def summary(bank, book, matches):
    by = {}
    for m in matches:
        s = by.setdefault(m["status"], {"count": 0, "bank_amount": money.ZERO, "book_amount": money.ZERO})
        s["count"] += 1
        s["bank_amount"] += money.sum_(money.D(r["amount"]) for r in m["bank_rows"])
        s["book_amount"] += money.sum_(money.D(r["amount"]) for r in m["book_rows"])
    bank_total = money.sum_(money.D(b["amount"]) for b in bank)
    book_total = money.sum_(money.D(k["amount"]) for k in book)
    return {
        "bank_count": len(bank), "book_count": len(book),
        "bank_total": money.fmt(bank_total), "book_total": money.fmt(book_total),
        "difference": money.fmt(bank_total - book_total),
        "by_status": {k: {"count": v["count"], "bank_amount": money.fmt(v["bank_amount"]),
                          "book_amount": money.fmt(v["book_amount"])} for k, v in by.items()},
        "note": "Chênh lệch chỉ được báo cáo, hệ thống không tạo bút toán cân bằng.",
    }
