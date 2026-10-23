"""PDF: lớp chữ bằng PyMuPDF (có toạ độ để mở đúng vị trí); trang không có chữ → OCR local."""

import pymupdf as fitz

from .. import settings
from . import ocr, text_invoice
from .base import Doc, ExtractError, Result

PARSER = "pdf"
VERSION = "1.0.0"
MIN_TEXT_CHARS = 25


def extract(data, file_name):
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ExtractError("bad_pdf", f"PDF hỏng hoặc không đọc được: {e}") from e
    if doc.needs_pass:
        raise ExtractError("encrypted_pdf", "PDF được bảo vệ bằng mật khẩu")
    max_pages = int(settings.get()["max_pdf_pages"])
    if doc.page_count > max_pages:
        raise ExtractError("too_many_pages", f"PDF có {doc.page_count} trang, vượt giới hạn {max_pages}")
    res = Result(PARSER, VERSION)
    pages, texts, ocr_pages, scan_skipped = [], [], [], []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if len(text.strip()) >= MIN_TEXT_CHARS:
            lines = [(ln, None, None) for ln in text.splitlines() if ln.strip()]
            pages.append((i, lines))
            texts.append(text)
        elif ocr.available():
            zoom = 2.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            import numpy as np

            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            lines = ocr.read_image(img, scale=zoom)
            pages.append((i, lines))
            texts.append("\n".join(t for t, _, _ in lines))
            ocr_pages.append(i)
        else:
            scan_skipped.append(i)
    res.text = "\n\f".join(texts)
    res.stats = {"pages": doc.page_count, "ocr_pages": ocr_pages, "pages_without_text": scan_skipped}
    if ocr_pages:
        res.model_id = ocr.MODEL_ID

    def locate(page_no, value):
        try:
            hits = doc[page_no - 1].search_for(str(value).strip())
            return tuple(hits[0]) if hits else None
        except Exception:
            return None

    method = "ocr_pdf" if ocr_pages and len(ocr_pages) == len(pages) else "pdf_text"
    inv = None
    if text_invoice.looks_like_invoice(res.text):
        inv = text_invoice.extract(pages, file_name, method, locate=None if method.startswith("ocr") else locate,
                                   base_conf=0.75 if method.startswith("ocr") else 0.9)
    if inv:
        res.docs.append(inv)
    else:
        d = Doc(doc_type="text", title=file_name, data={"pages": doc.page_count})
        if scan_skipped:
            d.status = "NEEDS_REVIEW"
            d.warnings.append(f"{len(scan_skipped)} trang là ảnh scan nhưng OCR đang tắt/không khả dụng")
        res.docs.append(d)
    if scan_skipped and not texts:
        res.status = "PARTIAL"
    return res


def render_page(data, page_no, bbox=None, zoom=1.6):
    """Ảnh PNG của một trang, tô vùng bằng chứng (bbox theo toạ độ PDF)."""
    doc = fitz.open(stream=data, filetype="pdf")
    if not 1 <= page_no <= doc.page_count:
        raise ExtractError("bad_page", "Trang không tồn tại")
    page = doc[page_no - 1]
    if bbox:
        r = fitz.Rect(*bbox)
        r = fitz.Rect(r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2)
        annot = page.add_rect_annot(r)
        annot.set_colors(stroke=(0.99, 0.36, 0.22))
        annot.set_border(width=2)
        annot.update()
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
