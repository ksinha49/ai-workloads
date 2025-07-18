import io
from statistics import median
import tempfile
from pathlib import Path
import re
from html import unescape

import fitz  # PyMuPDF
import easyocr
from paddleocr import PaddleOCR
import cv2
import numpy as np
import httpx
try:  # pragma: no cover - optional dependency
    import ocrmypdf
except Exception:  # pragma: no cover - allow import without ocrmypdf
    ocrmypdf = None
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass

from common_utils import configure_logger

logger = configure_logger(__name__)

__all__ = [
    "extract_text_from_pdf",
    "preprocess_image_cv2",
    "_perform_ocr",
    "_ocrmypdf_sidecar",
    "_ocrmypdf_hocr",
    "post_process_text",
    "convert_to_markdown",
]


def extract_text_from_pdf(pdf_bytes: bytes, languages: list[str] | None = None) -> str:
    """Extract text from *pdf_bytes* preserving basic layout."""

    languages = languages or ["en"]
    reader = easyocr.Reader(languages, gpu=False)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    extracted: list[str] = []
    for page_number, page in enumerate(doc, start=1):
        pix = page.get_pixmap()
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.alpha:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        ok, encoded = cv2.imencode(".png", img)
        if not ok:
            raise ValueError("Failed to encode image for OCR")
        text, _ = _perform_ocr(reader, "easyocr", bytes(encoded))
        text = convert_to_markdown(text, page_number)
        extracted.append(text)
    return "\n".join(extracted)


def preprocess_image_cv2(img_bytes: bytes) -> np.ndarray:
    """Decode *img_bytes* into an OpenCV image array.

    The image is loaded in colour mode using ``cv2.imdecode``.  Any
    decoding errors will propagate to the caller.
    """

    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unable to decode image bytes")
    return img


def _results_to_layout_text(results: list[tuple[list[list[int]], str, float]]) -> str:
    """Return text arranged using OCR *results* bounding boxes."""

    if not results:
        return ""

    boxes = []
    for box, text, _ in results:
        top = min(pt[1] for pt in box)
        bottom = max(pt[1] for pt in box)
        left = min(pt[0] for pt in box)
        boxes.append({"top": top, "bottom": bottom, "left": left, "text": text})

    boxes.sort(key=lambda b: (b["top"], b["left"]))

    heights = [b["bottom"] - b["top"] for b in boxes]
    line_height = median(heights) if heights else 1
    group_thresh = line_height * 0.6

    lines: list[list[dict]] = []
    current = [boxes[0]]
    for b in boxes[1:]:
        if b["top"] - current[-1]["top"] > group_thresh:
            lines.append(current)
            current = [b]
        else:
            current.append(b)
    lines.append(current)

    para_thresh = line_height * 1.5
    output_lines: list[str] = []
    table_buffer: list[list[str]] = []
    prev_bottom = lines[0][0]["bottom"]

    def flush_table() -> None:
        nonlocal table_buffer
        if not table_buffer:
            return
        header = table_buffer[0]
        md = ["| " + " | ".join(header) + " |"]
        md.append("| " + " | ".join(["---"] * len(header)) + " |")
        for row in table_buffer[1:]:
            md.append("| " + " | ".join(row) + " |")
        output_lines.extend(md)
        table_buffer = []

    for line in lines:
        line.sort(key=lambda item: item["left"])
        cells = [item["text"] for item in line]
        top = line[0]["top"]
        bottom = max(item["bottom"] for item in line)
        if len(cells) > 1:
            table_buffer.append(cells)
        else:
            flush_table()
            if top - prev_bottom > para_thresh:
                output_lines.append("")
            output_lines.append(" ".join(cells))
        prev_bottom = bottom

    flush_table()
    return "\n".join(output_lines)


def _remote_trocr(img_bytes: bytes, url: str) -> tuple[str, float]:
    """Send *img_bytes* to a remote TrOCR service at *url*."""

    try:
        response = httpx.post(url, files={"file": ("image.png", img_bytes, "image/png")})
        response.raise_for_status()
    except HTTPError as exc:
        logger.exception("TrOCR request failed")
        return "", 0.0
    data = response.json()
    text = data.get("text", "")
    confidence = float(data.get("confidence", 0.0))
    return text, confidence


def _remote_docling(img_bytes: bytes, url: str) -> tuple[str, float]:
    """Send *img_bytes* to a remote Docling service at *url*."""

    try:
        response = httpx.post(url, files={"file": ("image.png", img_bytes, "image/png")})
        response.raise_for_status()
    except HTTPError as exc:
        logger.exception("Docling request failed")
        return "", 0.0
    data = response.json()
    text = data.get("text", "")
    confidence = float(data.get("confidence", 0.0))
    return text, confidence


def _parse_hocr_text(hocr: str) -> tuple[str, float]:
    """Return plain text and average confidence from *hocr* HTML."""

    words = re.findall(
        r"<span[^>]*class=['\"]ocrx_word['\"][^>]*title=['\"][^\"]*x_wconf (\d+)"
        r"[^\"]*['\"][^>]*>(.*?)</span>",
        hocr,
        flags=re.IGNORECASE | re.DOTALL,
    )
    texts: list[str] = []
    confs: list[float] = []
    for conf, txt in words:
        texts.append(unescape(txt))
        confs.append(float(conf))
    text = " ".join(texts).strip()
    avg_conf = float(sum(confs) / len(confs)) if confs else 0.0
    return text, avg_conf


def _ocrmypdf_hocr(pdf_bytes: bytes) -> tuple[str, float, bytes]:
    """Run ``ocrmypdf`` with ``--pdf-renderer hocr`` and return text, confidence,
    and hOCR bytes."""

    if ocrmypdf is None:  # pragma: no cover - optional dependency
        raise RuntimeError("ocrmypdf is not installed")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_pdf = Path(tmpdir) / "input.pdf"
        out_dir = Path(tmpdir)
        input_pdf.write_bytes(pdf_bytes)
        ocrmypdf.api._pdf_to_hocr(input_pdf, out_dir, progress_bar=False)
        hocr_files = sorted(out_dir.glob("*_ocr_hocr.hocr"))
        if not hocr_files:
            return "", 0.0, b""
        hocr_html = hocr_files[0].read_text("utf-8")
        text, conf = _parse_hocr_text(hocr_html)
        return text, conf, hocr_html.encode("utf-8")


def _ocrmypdf_sidecar(pdf_bytes: bytes) -> tuple[str, float]:
    """Run ``ocrmypdf`` with ``--sidecar`` and return text."""

    if ocrmypdf is None:  # pragma: no cover - optional dependency
        raise RuntimeError("ocrmypdf is not installed")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_pdf = Path(tmpdir) / "input.pdf"
        output_pdf = Path(tmpdir) / "out.pdf"
        sidecar = Path(tmpdir) / "out.txt"
        input_pdf.write_bytes(pdf_bytes)
        ocrmypdf.ocr(input_pdf, output_pdf, sidecar=sidecar, progress_bar=False)
        text = sidecar.read_text("utf-8")
        return text, 0.0


def _perform_ocr(ctx, engine: str, img_bytes: bytes) -> tuple[str, float]:
    """Run OCR on *img_bytes* using the specified *engine*."""

    if engine.lower() == "ocrmypdf":
        text, conf, _ = _ocrmypdf_hocr(img_bytes)
        return text, conf

    img = preprocess_image_cv2(img_bytes)

    if engine.lower() == "easyocr":
        if not isinstance(ctx, easyocr.Reader):
            raise TypeError("ctx must be an easyocr.Reader for engine 'easyocr'")
        results = ctx.readtext(img, detail=1)
        if not results:
            return "", 0.0
        text = _results_to_layout_text(results)
        confidences = [float(r[2]) for r in results]
        return text, float(np.mean(confidences))

    if engine.lower() == "paddleocr":
        if not isinstance(ctx, PaddleOCR):
            raise TypeError("ctx must be a PaddleOCR for engine 'paddleocr'")
        results = ctx.ocr(img)
        if not results:
            return "", 0.0
        converted = []
        for box, (text, conf) in results:
            converted.append((box, text, float(conf)))
        text = _results_to_layout_text(converted)
        confidences = [float(conf) for _, (_, conf) in results]
        return text, float(np.mean(confidences))

    if engine.lower() == "trocr":
        import os
        from common_utils.get_ssm import get_config
        url = get_config("TROCR_ENDPOINT") or os.environ.get("TROCR_ENDPOINT")
        if ctx and isinstance(ctx, str):
            url = ctx
        if not url:
            raise ValueError("TROCR_ENDPOINT not configured")
        return _remote_trocr(img_bytes, url)

    if engine.lower() == "docling":
        import os
        from common_utils.get_ssm import get_config
        url = get_config("DOCLING_ENDPOINT") or os.environ.get("DOCLING_ENDPOINT")
        if ctx and isinstance(ctx, str):
            url = ctx
        if not url:
            raise ValueError("DOCLING_ENDPOINT not configured")
        return _remote_docling(img_bytes, url)

    raise ValueError(f"Unsupported OCR engine: {engine}")


def post_process_text(text: str) -> str:
    """Clean up raw OCR output while preserving line breaks."""

    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("-\n", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(lines).strip()


def convert_to_markdown(text: str, page_number: int) -> str:
    """Wrap *text* for *page_number* in simple Markdown."""

    header = f"## Page {page_number}"
    body = text.strip()
    return f"{header}\n\n{body}\n"
