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
``HOCR_PREFIX``
    Destination prefix for hOCR outputs when ``OCR_ENGINE`` is ``"ocrmypdf"``.
    Defaults to ``"hocr/"``.
"""

from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Iterable
from models import S3Event, LambdaResponse

import boto3
from common_utils import get_config, configure_logger, iter_s3_records
import fitz  # PyMuPDF
try:
    from botocore.exceptions import ClientError, BotoCoreError
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal env
    class ClientError(Exception):
        pass

    class BotoCoreError(Exception):
        pass
import cv2
import numpy as np
from paddleocr import PaddleOCR

from ocr_module import (
    easyocr,
    _perform_ocr,
    _ocrmypdf_hocr,
    post_process_text,
    convert_to_markdown,
)

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

s3_client = boto3.client("s3")





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


def _hocr_to_words(hocr_html: str) -> list[dict[str, object]]:
    """Return a list of word dictionaries extracted from *hocr_html*."""

    pattern = re.compile(
        r"<span[^>]*class=['\"]ocrx_word['\"][^>]*title=['\"][^'\"]*bbox (\d+) (\d+) (\d+) (\d+)[^'\"]*['\"][^>]*>(.*?)</span>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    words: list[dict[str, object]] = []
    for x1, y1, x2, y2, text in pattern.findall(hocr_html):
        words.append({"bbox": [int(x1), int(y1), int(x2), int(y2)], "text": unescape(text).strip()})
    return words


def _handle_record(record: dict) -> None:
    """Process a single S3 event record."""

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    pdf_scan_page_prefix = get_config("PDF_SCAN_PAGE_PREFIX", bucket, key) or os.environ.get("PDF_SCAN_PAGE_PREFIX")
    text_page_prefix = get_config("TEXT_PAGE_PREFIX", bucket, key) or os.environ.get("TEXT_PAGE_PREFIX")
    hocr_prefix = get_config("HOCR_PREFIX", bucket, key) or os.environ.get("HOCR_PREFIX")
    dpi = int(get_config("DPI", bucket, key) or "300")
    engine = (get_config("OCR_ENGINE", bucket, key) or "easyocr").lower()
    trocr_endpoint = get_config("TROCR_ENDPOINT", bucket, key)
    docling_endpoint = get_config("DOCLING_ENDPOINT", bucket, key)
    if pdf_scan_page_prefix and not pdf_scan_page_prefix.endswith("/"):
        pdf_scan_page_prefix += "/"
    if text_page_prefix and not text_page_prefix.endswith("/"):
        text_page_prefix += "/"
    if hocr_prefix and not hocr_prefix.endswith("/"):
        hocr_prefix += "/"
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
        if engine == "ocrmypdf":
            text, _, hocr_data = _ocrmypdf_hocr(body)
        else:
            img = _rasterize_page(body, dpi)
            if img is None:
                logger.info("No pages in %s", key)
                return
            text = _ocr_image(img, engine, trocr_endpoint, docling_endpoint)
    except (fitz.FileDataError, ValueError, TypeError) as exc:  # pragma: no cover - expected
        logger.error("Failed to OCR %s: %s", key, exc)
        return
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected OCR error for %s", key)
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
    if engine == "ocrmypdf":
        words = _hocr_to_words(hocr_data.decode("utf-8"))
        hocr_key = hocr_prefix + os.path.splitext(rel_key)[0] + ".json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=hocr_key,
            Body=json.dumps({"words": words}).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Wrote %s", hocr_key)

def lambda_handler(event: S3Event, context: dict) -> LambdaResponse:
    """Triggered by scanned pages in ``PDF_SCAN_PAGE_PREFIX``.

    Parameters
    ----------
    event : :class:`models.S3Event`
        S3 event referencing the scanned page PDFs.

    1. Rasterises each page and performs OCR using the configured engine.
    2. Stores the recognised text as Markdown under ``TEXT_PAGE_PREFIX``.

    Returns
    -------
    :class:`models.LambdaResponse`
        200 response after all records are handled.
    """

    logger.info("Received event for 6-pdf-ocr-extractor: %s", event)
    for rec in iter_s3_records(event):
        try:
            _handle_record(rec)
        except (ClientError, BotoCoreError, fitz.FileDataError, ValueError, TypeError) as exc:
            logger.error("Error processing record %s: %s", rec, exc)
        except Exception as exc:  # pragma: no cover - unexpected
            logger.exception("Unexpected error processing record %s", rec)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "6-pdf-ocr-extractor executed"})
    }
