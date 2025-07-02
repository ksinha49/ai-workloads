# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""OCR extraction Lambda for scanned PDF pages.

Triggered for each single-page PDF under ``PDF_SCAN_PAGE_PREFIX``. The
page is rasterised using :mod:`fitz` at ``DPI`` resolution and passed to
the configured OCR engine via helpers from :mod:`ocr_module`.  The
recognised text is stored as Markdown under ``TEXT_PAGE_PREFIX`` using
the same relative path as the source page.

Environment variables
---------------------
``BUCKET_NAME``
    Name of the S3 bucket used for input and output. **Required.**
``PDF_SCAN_PAGE_PREFIX``
    Prefix where scanned single-page PDFs are stored. Defaults to
    ``"scan-pages/"``.
``TEXT_PAGE_PREFIX``
    Destination prefix for the extracted Markdown. Defaults to
    ``"text-pages/"``.
``DPI``
    Rasterisation resolution for PyMuPDF. Defaults to ``300``.
``OCR_ENGINE``
    OCR engine to use, ``"easyocr"``, ``"paddleocr"`` or ``"trocr"``. Defaults to
    ``"easyocr"``.
``TROCR_ENDPOINT``
    HTTP endpoint for the TrOCR engine when ``OCR_ENGINE`` is ``"trocr"``.
``DOCLING_ENDPOINT``
    HTTP endpoint for the Docling engine when ``OCR_ENGINE`` is ``"docling"``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import boto3
from common_utils import get_config
import fitz  # PyMuPDF
import cv2
import numpy as np
from paddleocr import PaddleOCR

from ocr_module import (
    easyocr,
    _perform_ocr,
    post_process_text,
    convert_to_markdown,
)

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%dT%H:%M:%S%z")
)
if not logger.handlers:
    logger.addHandler(_handler)

s3_client = boto3.client("s3")



def _iter_records(event: dict) -> Iterable[dict]:
    """Yield S3 event records from *event*."""

    for record in event.get("Records", []):
        yield record


def _rasterize_page(pdf_bytes: bytes, dpi: int) -> np.ndarray | None:
    """Return an image array for the first page of *pdf_bytes*."""

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if not doc.page_count:
            return None
        page = doc[0]
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=matrix)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        if pix.alpha:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img


def _ocr_image(img: np.ndarray, engine: str, trocr_endpoint: str | None, docling_endpoint: str | None) -> str:
    """Run OCR on *img* and return Markdown text."""

    # Encode the image to bytes for the OCR helper
    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("Failed to encode image for OCR")

    if engine == "paddleocr":
        reader = PaddleOCR()
        ctx = reader
    elif engine == "trocr":
        ctx = trocr_endpoint
    elif engine == "docling":
        ctx = docling_endpoint
    else:
        reader = easyocr.Reader(["en"], gpu=False)
        ctx = reader
        engine = "easyocr"
    text, _ = _perform_ocr(ctx, engine, bytes(encoded))
    text = post_process_text(text)
    return convert_to_markdown(text, 1)


def _handle_record(record: dict) -> None:
    """Process a single S3 event record."""

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    pdf_scan_page_prefix = get_config("PDF_SCAN_PAGE_PREFIX", bucket, key) or "scan-pages/"
    text_page_prefix = get_config("TEXT_PAGE_PREFIX", bucket, key) or "text-pages/"
    dpi = int(get_config("DPI", bucket, key) or "300")
    engine = (get_config("OCR_ENGINE", bucket, key) or "easyocr").lower()
    trocr_endpoint = get_config("TROCR_ENDPOINT", bucket, key)
    docling_endpoint = get_config("DOCLING_ENDPOINT", bucket, key)
    if pdf_scan_page_prefix and not pdf_scan_page_prefix.endswith("/"):
        pdf_scan_page_prefix += "/"
    if text_page_prefix and not text_page_prefix.endswith("/"):
        text_page_prefix += "/"
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(pdf_scan_page_prefix):
        logger.info("Key %s outside prefix %s - skipping", key, pdf_scan_page_prefix)
        return
    if not key.lower().endswith(".pdf"):
        logger.info("Key %s is not a PDF - skipping", key)
        return

    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = obj["Body"].read()
    try:
        img = _rasterize_page(body, dpi)
        if img is None:
            logger.info("No pages in %s", key)
            return
        text = _ocr_image(img, engine, trocr_endpoint, docling_endpoint)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.error("Failed to OCR %s: %s", key, exc)
        return

    rel_key = key[len(pdf_scan_page_prefix):]
    dest_key = text_page_prefix + os.path.splitext(rel_key)[0] + ".md"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=dest_key,
        Body=text.encode("utf-8"),
        ContentType="text/markdown",
    )
    logger.info("Wrote %s", dest_key)

def lambda_handler(event: dict, context: dict) -> dict:
    """Triggered by scanned pages in ``PDF_SCAN_PAGE_PREFIX``.

    1. Rasterises each page and performs OCR using the configured engine.
    2. Stores the recognised text as Markdown under ``TEXT_PAGE_PREFIX``.

    Returns a 200 response after all records are handled.
    """

    logger.info("Received event for 6-pdf-ocr-extractor: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Error processing record %s: %s", rec, exc)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "6-pdf-ocr-extractor executed"})
    }
