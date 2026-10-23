"""
OCR bằng EasyOCR (vi + en) chạy local trên GPU qua hàng đợi GPU dùng chung của Hub.
Không gửi ảnh ra ngoài. Kết quả OCR luôn được coi là chưa kiểm chứng (NEEDS_REVIEW).
"""

import threading

from core import gpu

from .. import settings

MODEL_ID = "easyocr-1.7:vi+en:latin_g2"
_reader = None
_lock = threading.Lock()


def _evict():
    global _reader
    with _lock:
        _reader = None


gpu.register("easyocr", _evict)


def available():
    if settings.get()["ocr"] == "off":
        return False
    try:
        import easyocr  # noqa: F401

        return True
    except Exception:
        return False


def _get_reader():
    global _reader
    with _lock:
        if _reader is None:
            import easyocr
            import torch

            _reader = easyocr.Reader(["vi", "en"], gpu=torch.cuda.is_available(), verbose=False)
        return _reader


def read_image(img, scale=1.0):
    """img: ndarray RGB. Trả về các dòng [(text, conf, bbox theo hệ toạ độ gốc/scale)]."""
    with gpu.task("accounting-ocr", "easyocr"):
        results = _get_reader().readtext(img, detail=1, paragraph=False)
    boxes = []
    for pts, text, conf in results:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append(((min(xs) / scale, min(ys) / scale, max(xs) / scale, max(ys) / scale), text, float(conf)))
    return group_lines(boxes)


def group_lines(boxes):
    """Gộp các mảnh chữ cùng hàng (theo tâm dọc) thành dòng, sắp trái → phải."""
    boxes = sorted(boxes, key=lambda b: ((b[0][1] + b[0][3]) / 2, b[0][0]))
    lines, cur, cur_y, cur_h = [], [], None, None
    for b in boxes:
        y = (b[0][1] + b[0][3]) / 2
        h = b[0][3] - b[0][1]
        if cur and abs(y - cur_y) <= max(cur_h, h) * 0.5:
            cur.append(b)
        else:
            if cur:
                lines.append(cur)
            cur, cur_y, cur_h = [b], y, h
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:
        ln.sort(key=lambda b: b[0][0])
        text = " ".join(b[1] for b in ln)
        conf = min(b[2] for b in ln)
        bbox = (min(b[0][0] for b in ln), min(b[0][1] for b in ln), max(b[0][2] for b in ln), max(b[0][3] for b in ln))
        out.append((text, conf, bbox))
    return out
