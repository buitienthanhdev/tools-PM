"""
AI Tư vấn pháp luật — RAG.

Nạp văn bản → làm sạch + tách theo Chương/Mục/Điều/Khoản → chỉ mục lai (BM25 + vector Ollama, hợp nhất RRF)
→ (câu hỏi nối tiếp được viết lại thành câu độc lập) → AI local trả lời có đánh số căn cứ [n]
→ kiểm chứng: có trích dẫn không, có nhắc Điều nào ngoài các căn cứ đã truy xuất không.
Dưới ngưỡng tương đồng thì nói thẳng "chưa có căn cứ" thay vì để AI đoán.
"""

import hashlib
import json
import os
import re
import threading
import time
import uuid

from core import config as hubcfg
from core import llm

from . import index as ix
from . import parse as ps

KB_DIR = os.path.join(hubcfg.DATA_DIR, "legal")  # PM_DATA_DIR đổi được khi thử nghiệm
KB_PATH = os.path.join(KB_DIR, "kb.json")

_lock = threading.RLock()
_kb = {"docs": []}
_index = None
parse_law = ps.parse_law  # giữ tên cũ cho nơi khác import


# ── Lưu trữ ──────────────────────────────────────────────────
def _doc_hash(d):
    return hashlib.sha1("\n".join(c["text"] for c in d["chunks"]).encode()).hexdigest()


def load():
    global _kb, _index
    with _lock:
        if os.path.exists(KB_PATH):
            with open(KB_PATH, encoding="utf-8") as f:
                _kb = json.load(f)
        seen, kept = set(), []
        for d in _kb["docs"]:  # bỏ văn bản trùng nội dung
            h = _doc_hash(d)
            if h not in seen:
                seen.add(h)
                kept.append(d)
        if len(kept) != len(_kb["docs"]):
            print(f"[legal_rag] bỏ {len(_kb['docs']) - len(kept)} văn bản trùng nội dung")
            _kb["docs"] = kept
            _save()
        _index = None


def _save():
    os.makedirs(KB_DIR, exist_ok=True)
    tmp = KB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_kb, f, ensure_ascii=False)
    os.replace(tmp, KB_PATH)


def _reset():
    global _index
    _index = None


# ── Đọc file ─────────────────────────────────────────────────
_ocr_reader = None


def _ocr_pdf(data: bytes, progress=None) -> str:
    """OCR cho PDF scan (easyocr vi+en, GPU nếu có)."""
    global _ocr_reader
    import numpy as np
    import pymupdf

    if _ocr_reader is None:
        import easyocr

        _ocr_reader = easyocr.Reader(["vi", "en"], gpu=True, verbose=False)
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200, colorspace=pymupdf.csGRAY)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        pages.append("\n".join(_ocr_reader.readtext(img, detail=0, paragraph=False)))
        if progress:
            progress(i + 1, len(doc))
    return "\n".join(pages)


def extract_text(filename: str, data: bytes, progress=None) -> str:
    import io

    ext = os.path.splitext(filename)[1].lower()
    if ext in (".txt", ".md", ""):
        for enc in ("utf-8-sig", "utf-16", "cp1258"):
            try:
                return data.decode(enc)
            except UnicodeError:
                continue
        return data.decode("utf-8", errors="ignore")
    if ext == ".docx":
        import docx  # python-docx

        d = docx.Document(io.BytesIO(data))
        lines = [p.text for p in d.paragraphs]
        for t in d.tables:  # bảng (vd. phụ lục) cũng là nội dung luật
            lines += [" | ".join(c.text.strip() for c in row.cells) for row in t.rows]
        return "\n".join(lines)
    if ext == ".pdf":
        try:  # pymupdf giữ thứ tự đọc và dấu tiếng Việt tốt hơn pypdf
            import pymupdf

            doc = pymupdf.open(stream=data, filetype="pdf")
            text = "\n".join(p.get_text("text") for p in doc)
        except ImportError:
            from pypdf import PdfReader

            text = "\n".join(
                (p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages
            )
        if len(text.strip()) < 200:  # PDF scan → không có lớp chữ
            text = _ocr_pdf(data, progress)
        return text
    raise ValueError(f"Định dạng {ext} chưa được hỗ trợ (dùng .txt .md .docx .pdf)")


# ── Quản lý văn bản ──────────────────────────────────────────
def add_law(name: str, text: str):
    text = ps.clean_text(text)
    chunks = ps.parse_law(text)
    if not chunks:
        raise ValueError("Không tìm thấy nội dung để nạp")
    doc = {
        "id": uuid.uuid4().hex[:10],
        "name": name.strip(),
        "added": int(time.time()),
        "chunks": chunks,
        "quality": ps.quality_report(text, chunks),
    }
    with _lock:
        # cùng tên = cập nhật bản mới
        _kb["docs"] = [
            d for d in _kb["docs"] if d["name"].lower() != doc["name"].lower()
        ]
        h = _doc_hash(doc)
        if any(_doc_hash(d) == h for d in _kb["docs"]):
            raise ValueError("Nội dung này đã có trong hệ thống (trùng với văn bản khác)")
        _kb["docs"].append(doc)
        _save()
        _reset()
    return doc


def delete_law(doc_id: str) -> bool:
    with _lock:
        before = len(_kb["docs"])
        _kb["docs"] = [d for d in _kb["docs"] if d["id"] != doc_id]
        if len(_kb["docs"]) != before:
            _save()
            _reset()
            return True
    return False


def list_laws():
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "added": d["added"],
            "articles": len(d["chunks"]),
            "warnings": (d.get("quality") or {}).get("warnings", []),
        }
        for d in _kb["docs"]
    ]


# ── Chỉ mục ──────────────────────────────────────────────────
def _embed_fn():
    model = hubcfg.model("embed")
    return lambda texts: llm.embed(model, texts, name="legal-embed")


def get_index(rebuild=False):
    """Chỉ mục xây khi cần (vector tính một lần rồi lưu cache theo nội dung)."""
    global _index
    with _lock:
        if _index is None or rebuild:
            _index = ix.Index(
                _kb["docs"], KB_DIR, embed_fn=_embed_fn(), embed_model=hubcfg.model("embed")
            )
        return _index


def reindex():
    """Xoá cache vector và tính lại (dùng khi đổi model embedding)."""
    if os.path.isdir(KB_DIR):
        for f in os.listdir(KB_DIR):
            if f.startswith("vec_"):
                os.remove(os.path.join(KB_DIR, f))
    idx = get_index(rebuild=True)
    return {"chunks": len(idx.entries), "vectors": idx.vecs is not None, "error": idx.embed_error}


def index_status():
    idx = _index
    return {
        "chunks": sum(len(d["chunks"]) for d in _kb["docs"]),
        "vectors": bool(idx and idx.vecs is not None),
        "embed_model": hubcfg.model("embed"),
        "embed_error": idx.embed_error if idx else None,
    }


# ── Truy xuất ────────────────────────────────────────────────
_FOLLOWUP = re.compile(r"\b(nó|vậy|thế|đó|này|còn|trường hợp đó|như trên|thì sao)\b", re.I)


def rewrite_query(question, history):
    """Câu hỏi nối tiếp ("vậy còn nghỉ thai sản?") → câu hỏi độc lập để tìm kiếm."""
    turns = [
        m for m in (history or [])[-4:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    if not turns or (len(question.split()) > 14 and not _FOLLOWUP.search(question)):
        return question
    convo = "\n".join(f'{m["role"]}: {str(m["content"])[:400]}' for m in turns)
    try:
        out = llm.chat(
            hubcfg.model("legal"),
            [
                {
                    "role": "system",
                    "content": "Viết lại câu hỏi cuối của người dùng thành MỘT câu hỏi đầy đủ, độc lập, "
                    "giữ đủ chủ thể/tình huống nhắc ở các lượt trước. Chỉ trả về câu hỏi, không giải thích.",
                },
                {"role": "user", "content": f"{convo}\nuser: {question}"},
            ],
            num_ctx=4096, num_predict=120, temperature=0.0, timeout=120, name="legal-rewrite",
        )
        out = out.strip().strip('"')
        return out if 5 <= len(out) <= 400 else question
    except Exception as e:
        print(f"[legal_rag] rewrite lỗi: {e}")
        return question


def search(question: str, k=6, history=None):
    """Trả về danh sách đoạn luật đã hợp nhất, có điểm BM25 + cosine."""
    return retrieve(question, k=k, history=history)["hits"]


def retrieve(question: str, k=6, history=None, mode="auto"):
    """mode: auto (lai nếu có vector) | bm25 (ép chỉ BM25, dùng để so sánh chất lượng)."""
    idx = get_index()
    if not idx.entries:
        return {"hits": [], "query": question, "mode": "empty", "confidence": 0.0}
    query = rewrite_query(question, history)
    qvec = None
    if idx.vecs is not None and mode != "bm25":
        try:
            qvec = llm.embed(
                hubcfg.model("embed"), [ix.QUERY_INSTRUCT + query], name="legal-q"
            )[0]
        except Exception as e:
            print(f"[legal_rag] embed câu hỏi lỗi, dùng BM25: {e}")
    accented = ix.has_diacritics(query)
    # không dấu → vector kém tin cậy: giảm trọng số, BM25 (có bản bỏ dấu) gánh chính
    results = idx.search(query, qvec, k=k, dense_weight=1.0 if accented else 0.1)
    hits = [
        {
            "law": e["doc"], "article": e["chunk"].get("article", ""),
            "title": e["chunk"].get("title", ""), "clause": e["chunk"].get("clause", ""),
            "chapter": e["chunk"].get("chapter", ""), "section": e["chunk"].get("section", ""),
            "text": e["chunk"]["text"], **info,
        }
        for e, info in results
    ]
    dense = [h["dense"] for h in hits if h["dense"] is not None]
    return {
        "hits": hits,
        "query": query,
        "mode": "hybrid" if qvec is not None else "bm25",
        "confidence": round(max(dense), 3) if dense and accented else None,
    }


# ── Trả lời ──────────────────────────────────────────────────
SYSTEM_PROMPT = """Bạn là trợ lý AI tư vấn pháp luật Việt Nam, thân thiện, lịch sự và chính xác.

QUY TẮC BẮT BUỘC:
1. CHỈ dùng nội dung trong phần "CĂN CỨ TRUY XUẤT" để kết luận. Tuyệt đối không bịa điều, khoản, mức phạt hay số liệu không có trong đó, và không nhắc tới Điều nào không nằm trong các căn cứ.
2. Mỗi nhận định phải kết thúc bằng số căn cứ trong ngoặc vuông, ví dụ "... không được quá 12 tháng [2]." Có thể ghi nhiều căn cứ: [1][3].
3. Cú pháp trả lời:
   "Cảm ơn câu hỏi của bạn. Căn cứ vào {tên văn bản, Điều, Khoản} thì {tình huống người dùng hỏi} sẽ {kết luận suy ra từ luật} [n]."
   Sau câu mở đầu, giải thích đầy đủ, dễ hiểu: nêu điều kiện, ngoại lệ, mức xử phạt/quyền/nghĩa vụ nếu có. Nhiều căn cứ thì liệt kê từng căn cứ.
4. Nếu các căn cứ KHÔNG đủ để trả lời, nói rõ: "Cảm ơn câu hỏi của bạn. Hiện cơ sở dữ liệu pháp luật của tôi chưa có căn cứ đủ để trả lời chính xác nội dung này", rồi gợi ý hỏi rõ hơn hoặc tham khảo luật sư. Không đoán.
5. Trả lời bằng tiếng Việt, giọng ấm áp, có cấu trúc (gạch đầu dòng khi cần). Kết thúc bằng một dòng nhắc ngắn: thông tin mang tính tham khảo, nên hỏi luật sư với vụ việc cụ thể."""

NO_BASIS = (
    "Cảm ơn câu hỏi của bạn. Hiện cơ sở dữ liệu pháp luật của tôi chưa có căn cứ "
    "phù hợp để trả lời chính xác nội dung này. Bạn thử diễn đạt cụ thể hơn "
    "(nêu rõ hành vi, lĩnh vực) hoặc tham khảo ý kiến luật sư nhé."
)


def _label(h):
    ref = f'Điều {h["article"]}. {h["title"]}'.strip(" .") if h["article"] else "Trích đoạn"
    if h.get("clause"):
        ref += f' (khoản {h["clause"]})'
    return f'{h["law"]} — {ref}'


def _context(hits):
    return "\n\n".join(
        f"[{i}] {_label(h)}"
        + (f' · {h["chapter"]}' if h.get("chapter") else "")
        + f'\n{h["text"][:2500]}'
        for i, h in enumerate(hits, 1)
    )


def _call_llm(question, hits, history):
    """Trả lời bằng AI local (Ollama) dựa trên các căn cứ đã truy xuất."""
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in (history or [])[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            msgs.append({"role": m["role"], "content": str(m["content"])[:3000]})
    msgs.append(
        {"role": "user", "content": f"CĂN CỨ TRUY XUẤT:\n{_context(hits)}\n\nCÂU HỎI: {question}"}
    )
    return llm.chat(
        hubcfg.model("legal"), msgs, num_ctx=12288, num_predict=1800,
        temperature=0.2, name="legal", timeout=600,
    )


def _fallback(hits):
    top = hits[0]
    return (
        f"Cảm ơn câu hỏi của bạn. Căn cứ vào {_label(top)} thì nội dung bạn hỏi "
        f'được quy định như sau:\n\n{top["text"][:1500]}\n\n'
        "_(AI local chưa trả lời được nên hệ thống chỉ trích dẫn điều luật liên quan "
        "nhất, chưa suy luận chi tiết. Thông tin mang tính tham khảo.)_"
    )


def verify_answer(text, hits):
    """Kiểm chứng câu trả lời với căn cứ đã truy xuất."""
    cited = sorted(
        {int(n) for n in re.findall(r"\[(\d{1,2})\]", text) if 1 <= int(n) <= len(hits)}
    )
    known = {h["article"] for h in hits if h["article"]}
    mentioned = set(re.findall(r"Điều\s+(\d+[a-zA-Z]?)", text))
    unverified = sorted(mentioned - known)
    return {
        "cited": cited,
        "unverified_articles": unverified,
        "grounded": bool(cited) and not unverified,
    }


def answer(question: str, history=None):
    history = history or []
    try:
        r = retrieve(question, k=6, history=history)
    except llm.LLMError as e:
        return {"answer": f"Không tìm kiếm được căn cứ: {e}", "sources": [],
                "grounded": False, "ai_error": str(e)}
    hits = r["hits"]
    min_sim = float(hubcfg.get().get("legal_min_similarity", 0.35))
    weak = r["confidence"] is not None and r["confidence"] < min_sim
    if not hits or weak:
        return {
            "answer": NO_BASIS, "sources": [], "grounded": False, "mode": r["mode"],
            "confidence": r["confidence"], "query": r["query"],
        }
    ai_error, text = None, None
    try:
        text = _call_llm(question, hits, history)
    except Exception as e:  # AI lỗi: vẫn trả điều luật, nhưng nói rõ lý do
        print(f"[legal_rag] LLM error: {e}")
        ai_error = str(e)
    check = (
        verify_answer(text, hits)
        if text
        else {"cited": [], "unverified_articles": [], "grounded": False}
    )
    return {
        "ai_error": ai_error,
        "answer": text or _fallback(hits),
        "grounded": check["grounded"] if text else True,
        "unverified_articles": check["unverified_articles"],
        "mode": r["mode"],
        "confidence": r["confidence"],
        "query": r["query"] if r["query"] != question else None,
        "sources": [
            {
                "n": i, "law": h["law"], "article": h["article"], "clause": h["clause"],
                "title": h["title"], "chapter": h["chapter"], "excerpt": h["text"][:420],
                "cited": i in check["cited"], "score": h["score"], "similarity": h["dense"],
            }
            for i, h in enumerate(hits, 1)
        ],
    }


load()
