"""
Tiến trình xử lý tài liệu nặng, chạy bằng Python của venv RIÊNG (D:\\tools PM\\venvs\\docai — xem requirements-docai.txt).
Không import gì từ Hub. Đọc đường dẫn file, in kết quả JSON ra stdout.

    python docai_worker.py ocr <ảnh.png>        → {"lines": [[text, conf, [x0, y0, x1, y1]], ...], "model": ...}
    python docai_worker.py tables <tài_liệu.pdf> → {"tables": [{"page": n, "grid": [[...], ...]}], "model": ...}
"""

import json
import os
import sys


def ocr(path):
    from paddleocr import PaddleOCR

    # oneDNN của paddlepaddle 3.x trên CPU lỗi với mô hình PIR → tắt (đã kiểm chứng trên máy chủ)
    engine = PaddleOCR(lang="vi", enable_mkldnn=False, use_doc_orientation_classify=False,
                       use_doc_unwarping=False, use_textline_orientation=False)
    out = []
    for page in engine.predict(path):
        for text, score, poly in zip(page["rec_texts"], page["rec_scores"], page["rec_polys"]):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            out.append([text, float(score), [min(xs), min(ys), max(xs), max(ys)]])
    return {"lines": out, "model": "paddleocr-3.7:PP-OCRv6:vi"}


def tables(path):
    from docling.document_converter import DocumentConverter

    doc = DocumentConverter().convert(path).document
    out = []
    for t in doc.tables:
        df = t.export_to_dataframe(doc=doc)
        grid = [[str(c) for c in df.columns]] + [["" if v is None else str(v) for v in row] for row in df.values.tolist()]
        page = t.prov[0].page_no if t.prov else None
        out.append({"page": page, "grid": grid})
    return {"tables": out, "model": "docling-2.142"}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    cmd, path = sys.argv[1], sys.argv[2]
    result = ocr(path) if cmd == "ocr" else tables(path)
    sys.stdout.write("\n@@DOCAI@@" + json.dumps(result, ensure_ascii=False))
