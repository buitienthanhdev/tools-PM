"""Chỉ mục tìm kiếm lai: BM25 (từ + cặp từ, có bản bỏ dấu) + vector (Ollama embedding), hợp nhất bằng RRF."""

import math
import re
import unicodedata
from collections import Counter

import numpy as np

from . import vecstore

STOPWORDS = set(
    "và của là có cho các một những được trong khi với này đó thì bị bởi để "
    "theo tại từ như không về đã sẽ nếu hay hoặc thế nào gì ai nào bao nhiêu "
    "tôi bạn mình xin hỏi ạ nhé".split()
)
QUERY_INSTRUCT = (
    "Instruct: Cho một câu hỏi về pháp luật Việt Nam, tìm các điều luật liên quan để trả lời\nQuery: "
)
RRF_K = 60


def fold(s: str) -> str:
    """Bỏ dấu tiếng Việt (để khớp khi người dùng gõ không dấu / sai dấu)."""
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_VI_MARKS = re.compile(r"[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]", re.I)


def has_diacritics(s: str) -> bool:
    """Câu hỏi có gõ dấu tiếng Việt không (vector chỉ đáng tin khi có dấu)."""
    return bool(_VI_MARKS.search(s))


def tokenize(s: str):
    s = unicodedata.normalize("NFC", s.lower())
    words = [w for w in re.findall(r"\w+", s) if w not in STOPWORDS]
    toks = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
    toks += [f"~{fold(w)}" for w in words]  # bản không dấu, trọng số riêng
    return toks


def embed_text(doc_name: str, c: dict) -> str:
    """Văn bản đưa vào embedding: kèm tên luật + chương + tiêu đề để đoạn tự mang ngữ cảnh."""
    ctx = " | ".join(x for x in (doc_name, c.get("chapter"), c.get("section")) if x)
    return f"{ctx}\n{c['text']}"[:1800]


class Index:
    def __init__(self, docs, cache_dir, embed_fn=None, embed_model=""):
        self.entries = []
        for d in docs:
            for i, c in enumerate(d["chunks"]):
                head = f'{c.get("title", "")} {c.get("chapter", "")} {d["name"]}'
                toks = tokenize(head + " " + head + " " + c["text"])
                self.entries.append(
                    {"doc": d["name"], "doc_id": d["id"], "i": i, "chunk": c,
                     "tf": Counter(toks), "len": len(toks)}
                )
        df = Counter()
        for e in self.entries:
            df.update(e["tf"].keys())
        self.df = df
        self.avg = sum(e["len"] for e in self.entries) / max(1, len(self.entries))
        self.vecs = None
        self.embed_error = None
        if embed_fn and self.entries:
            try:
                self.vecs = self._load_vectors(docs, cache_dir, embed_fn, embed_model)
            except Exception as e:  # không có embedding vẫn tìm được bằng BM25
                self.embed_error = str(e)

    # ── vector (kho gộp, lưu theo nội dung để khỏi tính lại) ──
    def _load_vectors(self, docs, cache_dir, embed_fn, model):
        return vecstore.load_or_build(
            docs,
            lambda d: [embed_text(d["name"], c) for c in d["chunks"]],
            cache_dir,
            embed_fn,
            model,
        )

    # ── tìm kiếm ──────────────────────────────────────────────
    def bm25(self, query):
        q = tokenize(query)
        n = len(self.entries)
        scores = np.zeros(n, dtype="float32")
        for ei, e in enumerate(self.entries):
            s = 0.0
            for t in q:
                f = e["tf"].get(t)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                w = 0.5 if t.startswith("~") else 1.0
                s += w * idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * e["len"] / self.avg))
            scores[ei] = s
        return scores

    def dense(self, qvec):
        if self.vecs is None:
            return None
        return self.vecs @ qvec

    def search(self, query, qvec=None, k=6, pool=30, dense_weight=1.0):
        """Trả về [(entry, info)] đã hợp nhất; info có dense (cosine) và bm25 (điểm thô)."""
        b = self.bm25(query)
        d = self.dense(qvec) if qvec is not None else None
        fused = Counter()
        for scores, weight in ((b, 1.0), (d, dense_weight)):
            if scores is None:
                continue
            order = np.argsort(-scores)[:pool]
            for rank, idx in enumerate(order):
                if scores[idx] > 0:
                    fused[int(idx)] += weight / (RRF_K + rank + 1)
        ranked = [i for i, _ in fused.most_common()]
        out, seen_articles = [], Counter()
        for idx in ranked:
            e = self.entries[idx]
            key = (e["doc_id"], e["chunk"].get("article") or f"_{idx}")
            if seen_articles[key] >= 2:  # tối đa 2 đoạn / Điều, nhường chỗ cho Điều khác
                continue
            seen_articles[key] += 1
            out.append(
                (e, {"score": round(fused[idx] * 1000, 2), "bm25": float(b[idx]),
                     "dense": float(d[idx]) if d is not None else None})
            )
            if len(out) >= k:
                break
        return out
