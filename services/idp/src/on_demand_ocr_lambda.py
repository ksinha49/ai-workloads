# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""SQS-triggered Lambda for on-demand OCR of entire documents.

The function accepts an SQS message containing the source S3 bucket and object
key. Each document is processed page by page using the same OCR helpers as the
standard pipeline. The combined Markdown output is written to
``TEXT_DOC_PREFIX/{documentId}.json`` and the optional hOCR JSON to
``HOCR_PREFIX/{documentId}.json`` when ``ocrmypdf`` is the selected engine.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import boto3
import fitz  # type: ignore
import cv2  # type: ignore
import numpy as np  # type: ignore

from common_utils import configure_logger, get_config
from ocr_module import (
    easyocr,
    _perform_ocr,
    _ocrmypdf_hocr,
    post_process_text,
    convert_to_markdown,
)

logger = configure_logger(__name__)

s3_client = boto3.client("s3")


def _rasterize(pdf_bytes: bytes, dpi: int) -> List[np.ndarray]:
    """Return a list of images for each page of *pdf_bytes*."""
    pages: List[np.ndarray] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            matrix = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=matrix)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.alpha:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            pages.append(img)
    return pages


def _ocr_document(
    pdf_bytes: bytes,
    engine: str,
    dpi: int,
    trocr_endpoint: str | None,
    docling_endpoint: str | None,
) -> tuple[List[str], List[Dict[str, Any]]]:
    """Return Markdown for each page and optional hOCR data."""

    texts: List[str] = []
    hocr_pages: List[Dict[str, Any]] = []
    images = _rasterize(pdf_bytes, dpi) if engine != "ocrmypdf" else []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page_count = doc.page_count
        for i in range(page_count):
            if engine == "ocrmypdf":
                single = fitz.open()
                single.insert_pdf(doc, from_page=i, to_page=i)
                page_bytes = single.tobytes()
                text, _, hocr = _ocrmypdf_hocr(page_bytes)
                words = _hocr_to_words(hocr.decode("utf-8"))
                hocr_pages.append({"pageNumber": i + 1, "words": words})
            else:
                img = images[i]
                ok, encoded = cv2.imencode(".png", img)
                if not ok:
                    raise ValueError("Failed to encode image for OCR")
                if engine == "paddleocr":
                    reader = easyocr.Reader(["en"], gpu=False)
                    ctx = reader
                    engine_name = "paddleocr"
                elif engine == "trocr":
                    ctx = trocr_endpoint
                    engine_name = "trocr"
                elif engine == "docling":
                    ctx = docling_endpoint
                    engine_name = "docling"
                else:
                    reader = easyocr.Reader(["en"], gpu=False)
                    ctx = reader
                    engine_name = "easyocr"
                text, _ = _perform_ocr(ctx, engine_name, bytes(encoded))
            text = post_process_text(text)
            texts.append(convert_to_markdown(text, i + 1))
    return texts, hocr_pages


def _hocr_to_words(hocr_html: str) -> List[Dict[str, Any]]:
    import re
    from html import unescape

    pattern = re.compile(
        r"<span[^>]*class=['\"]ocrx_word['\"][^>]*title=['\"][^'\"]*bbox (\d+) (\d+) (\d+) (\d+)[^'\"]*['\"][^>]*>(.*?)</span>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    words: List[Dict[str, Any]] = []
    for x1, y1, x2, y2, text in pattern.findall(hocr_html):
        words.append(
            {"bbox": [int(x1), int(y1), int(x2), int(y2)], "text": unescape(text).strip()}
        )
    return words


def _process_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    bucket = payload.get("bucket")
    key = payload.get("key")
    if not bucket or not key:
        return {"statusCode": 400, "body": json.dumps({"message": "Missing bucket or key"})}

    bucket_name = get_config("BUCKET_NAME", bucket, key)
    text_doc_prefix = get_config("TEXT_DOC_PREFIX", bucket, key) or os.environ.get("TEXT_DOC_PREFIX")
    hocr_prefix = get_config("HOCR_PREFIX", bucket, key) or os.environ.get("HOCR_PREFIX")
    dpi = int(get_config("DPI", bucket, key) or "300")
    engine = (get_config("OCR_ENGINE", bucket, key) or os.environ.get("OCR_ENGINE", "easyocr")).lower()
    trocr_endpoint = get_config("TROCR_ENDPOINT", bucket, key)
    docling_endpoint = get_config("DOCLING_ENDPOINT", bucket, key)
    if text_doc_prefix and not text_doc_prefix.endswith("/"):
        text_doc_prefix += "/"
    if hocr_prefix and not hocr_prefix.endswith("/"):
        hocr_prefix += "/"
    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = obj["Body"].read()
    texts, hocr_pages = _ocr_document(body, engine, dpi, trocr_endpoint, docling_endpoint)
    doc_id = os.path.splitext(os.path.basename(key))[0]
    text_doc = {
        "documentId": doc_id,
        "type": "pdf",
        "pageCount": len(texts),
        "pages": texts,
    }
    text_key = f"{text_doc_prefix}{doc_id}.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=text_key,
        Body=json.dumps(text_doc).encode("utf-8"),
        ContentType="application/json",
    )
    result = {"text_doc_key": text_key}
    if hocr_pages:
        hocr_key = f"{hocr_prefix}{doc_id}.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=hocr_key,
            Body=json.dumps({"documentId": doc_id, "pages": hocr_pages}).encode("utf-8"),
            ContentType="application/json",
        )
        result["hocr_key"] = hocr_key
    return result


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    """Entry point compatible with SQS events."""
    logger.info("Received event for on-demand OCR: %s", event)
    if isinstance(event, dict) and "Records" in event:
        return [_process_payload(json.loads(r.get("body", "{}"))) for r in event["Records"]]
    return _process_payload(event)

