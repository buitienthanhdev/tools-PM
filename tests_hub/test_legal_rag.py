"""Kiểm thử RAG pháp luật bằng văn bản hư cấu: phân tích cấu trúc, truy xuất lai, kiểm chứng trích dẫn."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import legal_fixture as fx  # noqa: E402


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    from modules.legal_rag import engine as e

    d = tmp_path_factory.mktemp("legalkb")
    e.KB_DIR, e.KB_PATH = str(d), str(d / "kb.json")
    e._kb = {"docs": []}
    e._reset()
    e.add_law(fx.LAW_NAME, fx.LAW_TEXT)
    return e


def has_embed():
    from core import config, llm

    return llm.status(config.model("embed"))["ok"]


# ── Phân tích cấu trúc ───────────────────────────────────────
def test_parse_structure(engine):
    chunks = engine._kb["docs"][0]["chunks"]
    arts = [c["article"] for c in chunks]
    assert arts[:3] == ["1", "2", "3"] and "12" in arts
    c6 = next(c for c in chunks if c["article"] == "6")
    assert c6["chapter"].startswith("Chương III")
    assert "MƯỢN VÀ TRẢ TÀI LIỆU" in c6["chapter"]  # tiêu đề chương được gộp vào
    assert c6["title"] == "Xử lý trả tài liệu muộn"
    assert "2.000 đồng" in c6["text"] and c6["text"].startswith("Điều 6.")


def test_long_article_splits_by_clause():
    from modules.legal_rag import parse

    clauses = "\n".join(f"{i}. " + ("Nội dung khoản số %d của điều luật. " % i) * 12 for i in range(1, 9))
    chunks = parse.parse_law(f"Điều 50. Điều rất dài\n{clauses}")
    assert len(chunks) > 1
    assert all(c["article"] == "50" and c["text"].startswith("Điều 50. Điều rất dài") for c in chunks)
    assert chunks[0]["clause"].startswith("1")


def test_clean_text_removes_page_noise_and_joins_lines():
    from modules.legal_rag import parse

    raw = "Điều 1. Thử\nNgười lao động được nghỉ\nmỗi tuần một ngày.\nTrang 3\n12\nĐiều 2. Khác\nNội dung."
    out = parse.clean_text(raw)
    assert "Trang 3" not in out and "\n12\n" not in out
    assert "được nghỉ mỗi tuần một ngày." in out  # dòng bị ngắt giữa câu được nối lại
    assert "Điều 2. Khác" in out


def test_duplicate_content_rejected(engine):
    with pytest.raises(ValueError):
        engine.add_law("Bản sao tên khác", fx.LAW_TEXT)


def test_quality_report_flags_garbled_text():
    from modules.legal_rag import parse

    garbled = "\n".join(["Xem xét;,", "qua", "thảo luật", "của", "d", "1", "hội xem xét,"] * 40)
    rep = parse.quality_report(garbled, [{"text": "ngắn"}])
    assert rep["warnings"]


# ── Truy xuất ────────────────────────────────────────────────
def top_articles(engine, q, mode):
    r = engine.retrieve(q, k=3, mode=mode)
    return [h["article"] for h in r["hits"]]


def recall(engine, mode, k=3):
    ok = sum(1 for q, art in fx.QUERIES if art in top_articles(engine, q, mode)[:k])
    return ok / len(fx.QUERIES)


def top1(engine, mode):
    return recall(engine, mode, k=1)


def test_bm25_baseline_works_without_embeddings(engine):
    assert recall(engine, "bm25") >= 0.5


@pytest.mark.skipif(not has_embed(), reason="Ollama chưa có model embedding")
def test_hybrid_beats_bm25_and_is_good(engine):
    engine.get_index(rebuild=True)
    assert engine.get_index().vecs is not None
    bm25, hybrid = recall(engine, "bm25"), recall(engine, "auto")
    print(f"\nrecall@3: bm25={bm25:.2f} hybrid={hybrid:.2f}")
    b1, h1 = top1(engine, "bm25"), top1(engine, "auto")
    print(f"top1: bm25={b1:.2f} hybrid={h1:.2f}")
    assert hybrid >= 0.9  # gồm cả câu hỏi không dấu
    assert h1 > b1, "tìm kiếm lai phải đặt đúng Điều lên đầu nhiều hơn BM25"


@pytest.mark.skipif(not has_embed(), reason="Ollama chưa có model embedding")
def test_off_topic_below_threshold_and_on_topic_above(engine):
    from core import config

    engine.get_index(rebuild=True)
    thr = config.get()["legal_min_similarity"]
    from modules.legal_rag import index as ix

    on = [engine.retrieve(q, k=3)["confidence"] for q, _ in fx.QUERIES if ix.has_diacritics(q)]
    off = [engine.retrieve(q, k=3)["confidence"] for q in fx.OFF_TOPIC]
    print(f"\nđúng chủ đề: min={min(on):.3f}  ngoài phạm vi: max={max(off):.3f}  ngưỡng={thr}")
    assert min(on) >= thr, "ngưỡng đang loại nhầm câu hỏi đúng chủ đề"
    assert max(off) < thr, "ngưỡng đang để lọt câu hỏi ngoài phạm vi"


@pytest.mark.skipif(not has_embed(), reason="Ollama chưa có model embedding")
def test_answer_off_topic_says_no_basis_without_calling_llm(engine, monkeypatch):
    engine.get_index(rebuild=True)
    monkeypatch.setattr(engine, "_call_llm", lambda *a, **k: pytest.fail("không được gọi AI"))
    out = engine.answer(fx.OFF_TOPIC[0])
    assert out["grounded"] is False and out["sources"] == []
    assert "chưa có căn cứ" in out["answer"]


# ── Kiểm chứng câu trả lời ──────────────────────────────────
def test_verify_answer_detects_missing_citation_and_invented_article(engine):
    hits = [{"article": "6"}, {"article": "7"}]
    ok = engine.verify_answer("Phạt 2.000 đồng mỗi ngày [1]. Mất sách phải đền [2].", hits)
    assert ok["grounded"] and ok["cited"] == [1, 2]
    no_cite = engine.verify_answer("Phạt 2.000 đồng mỗi ngày.", hits)
    assert not no_cite["grounded"]
    invented = engine.verify_answer("Theo Điều 99 thì phạt nặng [1].", hits)
    assert invented["unverified_articles"] == ["99"] and not invented["grounded"]
    out_of_range = engine.verify_answer("Căn cứ [5].", hits)
    assert out_of_range["cited"] == []
