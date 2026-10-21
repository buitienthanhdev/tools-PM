"""Kho vector gộp: một file `vectors.npy` + `vectors.json` (manifest), thay cho hàng nghìn file vec_*.npy.

Mỗi tài liệu có khoá nội dung (model + văn bản các đoạn); đổi nội dung hoặc model thì chỉ tài liệu đó
được embed lại. File cũ `vec_<id>_<key>.npy` được đọc và gộp vào kho ở lần chạy đầu tiên.
"""

import hashlib
import json
import os

import numpy as np

MATRIX = "vectors.npy"
MANIFEST = "vectors.json"


def doc_key(model, texts):
    return hashlib.sha1((model + "\n" + "\n".join(texts)).encode()).hexdigest()[:16]


def _read_manifest(cache_dir):
    try:
        with open(os.path.join(cache_dir, MANIFEST), encoding="utf-8") as f:
            man = json.load(f)
        mat = np.load(os.path.join(cache_dir, MATRIX))
        if sum(d["n"] for d in man["docs"]) != len(mat):
            raise ValueError("manifest không khớp ma trận")
        return {d["id"]: (d["key"], d["n"], d["start"]) for d in man["docs"]}, mat
    except (OSError, ValueError, KeyError):
        return {}, None


def _legacy(cache_dir, doc_id, key):
    p = os.path.join(cache_dir, f"vec_{doc_id}_{key}.npy")
    return np.load(p) if os.path.exists(p) else None


def load_or_build(docs, texts_of, cache_dir, embed_fn, model):
    """Trả về ma trận vector theo thứ tự docs. `texts_of(doc)` cho văn bản embed của từng đoạn."""
    os.makedirs(cache_dir, exist_ok=True)
    known, old = _read_manifest(cache_dir)
    parts, entries, changed, start = [], [], False, 0
    try:
        for d in docs:
            texts = texts_of(d)
            key = doc_key(model, texts)
            hit = known.get(d["id"])
            m = None
            if hit and hit[0] == key and old is not None:
                m = old[hit[2] : hit[2] + hit[1]]
            if m is None:
                m = _legacy(cache_dir, d["id"], key)
                changed = True
            if m is None:
                m = embed_fn(texts)
            if len(m) != len(texts):
                raise ValueError(f"embedding của {d['id']} sai số lượng")
            if not hit or hit[2] != start:
                changed = True
            parts.append(np.asarray(m, dtype="float32"))
            entries.append({"id": d["id"], "key": key, "n": len(texts), "start": start})
            start += len(texts)
    except Exception:
        if parts and changed:  # giữ phần đã tính để lần sau không phải embed lại từ đầu
            _save(cache_dir, np.vstack(parts), entries)
        raise
    if len(known) != len(docs):
        changed = True
    mat = np.vstack(parts) if parts else np.zeros((0, 0), dtype="float32")
    if changed:
        _save(cache_dir, mat, entries)
        _drop_legacy(cache_dir)
    return mat


def _save(cache_dir, mat, entries):
    tmp = os.path.join(cache_dir, MATRIX + ".tmp")
    with open(tmp, "wb") as f:
        np.save(f, mat)
    os.replace(tmp, os.path.join(cache_dir, MATRIX))
    tmp = os.path.join(cache_dir, MANIFEST + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"docs": entries}, f)
    os.replace(tmp, os.path.join(cache_dir, MANIFEST))


def _drop_legacy(cache_dir):
    for f in os.listdir(cache_dir):
        if f.startswith("vec_") and f.endswith(".npy"):
            os.remove(os.path.join(cache_dir, f))


def clear(cache_dir):
    if not os.path.isdir(cache_dir):
        return
    for f in os.listdir(cache_dir):
        if f in (MATRIX, MANIFEST) or (f.startswith("vec_") and f.endswith(".npy")):
            os.remove(os.path.join(cache_dir, f))
