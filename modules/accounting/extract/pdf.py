"""PDF: lớp chữ bằng PyMuPDF (có toạ độ để mở đúng vị trí); trang không có chữ → OCR local."""

import pymupdf as fitz

from .. import settings
from . import docai, ocr, pdf_tables, text_invoice
from .base import Doc, ExtractError, Result

PARSER = "pdf"
VERSION = "1.3.0"  # 1.1: tổng tiền bằng chữ; 1.2: bảng pdfplumber; 1.3: PaddleOCR/docling dự phòng
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
    scans = {}  # trang scan → ảnh PNG (để OCR dự phòng bằng PaddleOCR)
    zoom = 2.0
    paddle_ok = docai.available("ocr") and settings.get()["ocr"] != "off"
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if len(text.strip()) >= MIN_TEXT_CHARS:
            lines = [(ln, None, None) for ln in text.splitlines() if ln.strip()]
            pages.append((i, lines))
            texts.append(text)
        elif ocr.available() or paddle_ok:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            scans[i] = pix.tobytes("png")
            lines = []
            if ocr.available():
                import numpy as np

                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                lines = ocr.read_image(img, scale=zoom)
            pages.append((i, lines))
            texts.append("\n".join(t for t, _, _ in lines))
            ocr_pages.append(i)
        else:
            scan_skipped.append(i)
    res.text = "\n\f".join(texts)
    res.stats = {"pages": doc.page_count, "ocr_pages": ocr_pages, "pages_without_text": scan_skipped,
                 "ocr_engine": "easyocr" if ocr_pages and ocr.available() else None}
    if ocr_pages and ocr.available():
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
    if inv is None and scans and paddle_ok:
        # EasyOCR không nhận ra hoá đơn (VD ảnh mờ) hoặc không có EasyOCR → thử PaddleOCR (venv riêng)
        alt, model = {}, None
        for pno, png in scans.items():
            lines, model = docai.ocr_image(png, scale=zoom)
            if lines is None:
                break
            alt[pno] = lines
        if alt and len(alt) == len(scans):
            pages2 = [(p, alt.get(p, ln)) for p, ln in pages]
            text2 = "\n\f".join("\n".join(t for t, _, _ in ln) for _, ln in pages2)
            if text_invoice.looks_like_invoice(text2):
                inv = text_invoice.extract(pages2, file_name, method, base_conf=0.7)
            if inv is not None or not texts or not any(t.strip() for t in texts):
                pages, res.text, res.model_id = pages2, text2, model
                res.stats["ocr_engine"] = "paddleocr"
    tabs = []
    if texts and len(ocr_pages) < len(pages):
        try:
            tabs = pdf_tables.extract(data, file_name)
        except Exception as e:  # bảng là phần bổ sung: lỗi đọc bảng không làm hỏng phần văn bản
            res.stats["table_error"] = type(e).__name__
    if not tabs and inv is None and texts and len(ocr_pages) < len(pages) and docai.available("tables"):
        # Không có bảng kẻ ô: thử docling (bảng căn cột không kẻ, bố cục phức tạp) — chậm, chạy trong venv riêng
        dtabs, model = docai.pdf_tables(data)
        if dtabs:
            tabs = [{"page": t["page"] or 1, "grid": t["grid"], "cell_boxes": [], "bbox": None} for t in dtabs if len(t["grid"]) >= 2]
            res.stats["table_engine"] = model
    res.stats["tables"] = len(tabs)
    if inv:
        lines, lfields, used = pdf_tables.invoice_lines(tabs, inv.invoice.get("currency") or "VND")
        if lines:
            inv.lines = lines
            inv.fields += lfields
            inv.data["lines_extracted"] = True
            inv.warnings = [w for w in inv.warnings if "dòng hàng" not in w]
        res.docs.append(inv)
    elif tabs and (tdocs := pdf_tables.table_docs(tabs, file_name)):
        res.docs += tdocs
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
