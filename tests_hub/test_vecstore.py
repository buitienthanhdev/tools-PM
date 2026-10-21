import os

import numpy as np
import pytest

from modules.legal_rag import vecstore


def _docs(n=3):
    return [{"id": f"d{i}", "chunks": [f"doc{i}-c{j}" for j in range(i + 1)]} for i in range(n)]


def _texts(d):
    return d["chunks"]


class Embedder:
    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return np.array([[len(t), hash(t) % 7, 1.0] for t in texts], dtype="float32")


def test_build_then_reuse_without_embedding(tmp_path):
    emb = Embedder()
    m1 = vecstore.load_or_build(_docs(), _texts, str(tmp_path), emb, "m")
    assert m1.shape == (6, 3) and len(emb.calls) == 3
    emb2 = Embedder()
    m2 = vecstore.load_or_build(_docs(), _texts, str(tmp_path), emb2, "m")
    assert emb2.calls == [] and np.array_equal(m1, m2)
    assert sorted(os.listdir(tmp_path)) == ["vectors.json", "vectors.npy"]


def test_only_changed_doc_is_reembedded(tmp_path):
    vecstore.load_or_build(_docs(), _texts, str(tmp_path), Embedder(), "m")
    docs = _docs()
    docs[1]["chunks"][0] = "changed"
    emb = Embedder()
    m = vecstore.load_or_build(docs, _texts, str(tmp_path), emb, "m")
    assert emb.calls == [["changed", "doc1-c1"]] and m.shape == (6, 3)


def test_model_change_reembeds_everything(tmp_path):
    vecstore.load_or_build(_docs(), _texts, str(tmp_path), Embedder(), "a")
    emb = Embedder()
    vecstore.load_or_build(_docs(), _texts, str(tmp_path), emb, "b")
    assert len(emb.calls) == 3


def test_legacy_files_are_migrated(tmp_path):
    docs = _docs()
    ref = []
    for d in docs:
        texts = _texts(d)
        v = Embedder()(texts)
        ref.append(v)
        np.save(tmp_path / f"vec_{d['id']}_{vecstore.doc_key('m', texts)}.npy", v)
    emb = Embedder()
    m = vecstore.load_or_build(docs, _texts, str(tmp_path), emb, "m")
    assert emb.calls == [] and np.array_equal(m, np.vstack(ref))
    assert sorted(os.listdir(tmp_path)) == ["vectors.json", "vectors.npy"]


def test_failure_keeps_partial_progress(tmp_path):
    good = Embedder()

    def flaky(texts):
        if texts[0].startswith("doc2"):
            raise RuntimeError("ollama down")
        return good(texts)

    with pytest.raises(RuntimeError):
        vecstore.load_or_build(_docs(), _texts, str(tmp_path), flaky, "m")
    emb = Embedder()
    vecstore.load_or_build(_docs(), _texts, str(tmp_path), emb, "m")
    assert emb.calls == [["doc2-c0", "doc2-c1", "doc2-c2"]]
