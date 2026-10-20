"""Làm sạch và tách văn bản luật theo cấu trúc Phần / Chương / Mục / Điều / Khoản."""

import re
import unicodedata
from collections import Counter

PART_RE = re.compile(r"^\s*(Phần\s+(?:thứ\s+\w+|[IVXLCDM]+)\b.*)$", re.I)
CHAPTER_RE = re.compile(r"^\s*(Chương\s+[IVXLCDM\d]+\b.*)$", re.I)
SECTION_RE = re.compile(r"^\s*(Mục\s+\d+\b.*)$", re.I)
ARTICLE_RE = re.compile(r"^\s*Điều\s+(\d+[a-zA-Z]?)\s*[\.:]?\s*(.*)$")
CLAUSE_RE = re.compile(r"^\s*(\d+)\.\s+\S")
STRUCT_RE = re.compile(
    r"^\s*(Phần\s|Chương\s|Mục\s|Điều\s+\d|\d+\.\s|[a-zđ]\)\s|[-•–]\s)", re.I
)
PAGE_NO_RE = re.compile(r"^\s*(Trang\s*)?\d{1,4}\s*(/\s*\d{1,4})?\s*$", re.I)

MAX_ARTICLE_CHARS = 1600  # Điều dài hơn thì tách theo Khoản
MAX_CHUNK_CHARS = 1400


def clean_text(text: str) -> str:
    """Chuẩn hoá chữ, bỏ số trang / đầu trang lặp, nối dòng bị xuống hàng giữa câu."""
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace("\x0c", "\n").replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if not PAGE_NO_RE.match(ln)]
    # dòng ngắn lặp ≥4 lần = đầu/chân trang
    counts = Counter(ln for ln in lines if 0 < len(ln) < 70)
    repeated = {ln for ln, c in counts.items() if c >= 4 and not STRUCT_RE.match(ln)}
    lines = [ln for ln in lines if ln not in repeated]

    out = []
    for ln in lines:
        if not ln:
            if out and out[-1] != "":
                out.append("")
            continue
        if (
            out
            and out[-1]
            and not STRUCT_RE.match(ln)
            and not re.search(r"[.;:!?…]$", out[-1])
            and not out[-1].isupper()
        ):
            out[-1] = f"{out[-1]} {ln}"  # câu bị ngắt dòng: nối lại
        else:
            out.append(ln)
    return "\n".join(out).strip()


def quality_report(text: str, chunks) -> dict:
    """Ước lượng văn bản có đọc tốt không (OCR hỏng thường ra nhiều mảnh chữ rất ngắn)."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    short = sum(1 for ln in lines if len(ln.split()) <= 3 and not STRUCT_RE.match(ln))
    avg = sum(len(c["text"]) for c in chunks) / max(1, len(chunks))
    words = re.findall(r"\w+", text.lower())
    vi_marks = sum(1 for w in words if re.search(r"[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]", w))
    short_ratio = short / max(1, len(lines))
    warn = []
    if short_ratio > 0.35:
        warn.append("Nhiều dòng chỉ vài chữ — văn bản có thể bị OCR vỡ hoặc cắt dòng sai")
    if avg < 250:
        warn.append("Các đoạn quá ngắn — có thể tách Điều chưa đúng")
    if len(words) > 200 and vi_marks / len(words) < 0.15:
        warn.append("Ít dấu tiếng Việt — có thể mất dấu khi trích văn bản")
    return {"short_line_ratio": round(short_ratio, 2), "avg_chunk_chars": int(avg), "warnings": warn}


def _title_after(lines, i):
    """Dòng tiêu đề thường nằm ngay sau 'Chương I' (viết hoa)."""
    if i + 1 < len(lines):
        nxt = lines[i + 1].strip()
        if nxt and len(nxt) < 140 and not STRUCT_RE.match(nxt) and nxt.upper() == nxt:
            return nxt
    return ""


def _split_article(art_no, title, body_lines):
    """Điều ngắn = 1 đoạn; Điều dài tách theo Khoản (mỗi đoạn lặp lại tiêu đề Điều)."""
    header = f"Điều {art_no}. {title}".strip(" .")
    full = "\n".join(body_lines).strip()
    if len(full) <= MAX_ARTICLE_CHARS:
        return [{"clause": "", "body": full}]
    groups, cur, cur_len, first, last = [], [], 0, None, None
    clauses, buf = [], []
    del header  # chỉ dùng khi ghép đoạn ở parse_law
    for ln in body_lines:
        m = CLAUSE_RE.match(ln)
        if m and buf:
            clauses.append(buf)
            buf = []
        buf.append(ln)
    if buf:
        clauses.append(buf)
    for cl in clauses:
        txt = "\n".join(cl).strip()
        m = CLAUSE_RE.match(cl[0])
        num = m.group(1) if m else None
        if cur and cur_len + len(txt) > MAX_CHUNK_CHARS:
            groups.append((first, last, "\n".join(cur)))
            cur, cur_len, first = [], 0, None
        cur.append(txt)
        cur_len += len(txt)
        if num:
            first = first or num
            last = num
    if cur:
        groups.append((first, last, "\n".join(cur)))
    out = []
    for f, l, body in groups:
        label = "" if not f else (f if f == l else f"{f}-{l}")
        out.append({"clause": label, "body": body})
    return out or [{"clause": "", "body": full}]


def parse_law(text: str):
    """Trả về danh sách đoạn: part/chapter/section/article/title/clause/body/text."""
    lines = text.split("\n")
    part = chapter = section = ""
    chunks = []
    cur = None  # (art_no, title, [lines], part, chapter, section)

    def flush():
        nonlocal cur
        if not cur:
            return
        art_no, title, body, p, c, s = cur
        for piece in _split_article(art_no, title, [ln for ln in body]):
            head = f"Điều {art_no}. {title}".strip(" .")
            if piece["clause"]:
                head += f" (khoản {piece['clause']})"
            chunks.append(
                {
                    "article": art_no,
                    "title": title,
                    "clause": piece["clause"],
                    "part": p,
                    "chapter": c,
                    "section": s,
                    "body": piece["body"],
                    "text": f"{head}\n{piece['body']}".strip(),
                }
            )
        cur = None

    for i, ln in enumerate(lines):
        if not ln.strip():
            if cur:
                cur[2].append("")
            continue
        m = ARTICLE_RE.match(ln)
        if m and (len(m.group(2)) < 200 or m.group(2)[:1].isupper()):
            flush()
            cur = (m.group(1), m.group(2).strip(), [], part, chapter, section)
            continue
        if PART_RE.match(ln):
            flush()
            part, section = ln.strip(), ""
            continue
        if CHAPTER_RE.match(ln):
            flush()
            chapter = ln.strip()
            t = _title_after(lines, i)
            if t:
                chapter = f"{chapter} {t}"
            section = ""
            continue
        if SECTION_RE.match(ln):
            flush()
            section = ln.strip()
            continue
        if cur:
            if ln.strip() and chapter and ln.strip() in chapter:
                continue  # dòng tiêu đề chương đã gộp ở trên
            cur[2].append(ln.strip())
    flush()

    if not chunks:  # văn bản không có "Điều": chia theo đoạn ~900 ký tự
        buf = ""
        for para in re.split(r"\n\s*\n", text):
            if len(buf) + len(para) > 900 and buf:
                chunks.append(_plain(buf))
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            chunks.append(_plain(buf))
    return chunks


def _plain(buf):
    t = buf.strip()
    return {
        "article": "", "title": "", "clause": "", "part": "", "chapter": "",
        "section": "", "body": t, "text": t,
    }
