# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""PDF page classification Lambda.

This function runs for each single-page PDF written by the
``3-pdf-split`` step.  It inspects the page to determine whether any text
is present and then copies the page into one of two prefixes:

``PDF_TEXT_PAGE_PREFIX``
    Prefix for pages which contain embedded text.
``PDF_SCAN_PAGE_PREFIX``
    Prefix for scanned pages that require OCR.

Environment variables
---------------------
``BUCKET_NAME``
    Name of the S3 bucket used for both input and output. **Required.**
``PDF_PAGE_PREFIX``
    Prefix where single-page PDFs are written. Defaults to ``""``.
``PDF_TEXT_PAGE_PREFIX``
    Destination prefix for pages with embedded text. Defaults to
    ``"text-pages/"``.
``PDF_SCAN_PAGE_PREFIX``
    Destination prefix for scanned pages. Defaults to ``"scan-pages/"``.
"""

from __future__ import annotations

import json
import os
from typing import Iterable
from models import S3Event, LambdaResponse

import boto3
from common_utils import get_config, configure_logger
import fitz  # PyMuPDF

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

s3_client = boto3.client("s3")



def _iter_records(event: S3Event) -> Iterable[dict]:
    """Yield S3 event records from *event*."""

    records = event.Records if hasattr(event, "Records") else event.get("Records", [])
    for record in records:
        yield record


def _page_has_text(pdf_bytes: bytes) -> bool:
    """Return ``True`` if the single-page PDF contains any text."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count > 0:
            page = doc[0]
            return bool(page.get_text().strip())
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.error("Failed to inspect PDF page: %s", exc)
    return False


def _copy_page(bucket_name: str, pdf_page_prefix: str, key: str, body: bytes, dest_prefix: str) -> None:
    """Write *body* to S3 under *dest_prefix* preserving the file name."""

    dest_key = dest_prefix + key[len(pdf_page_prefix):]
    logger.info("Copying %s to %s", key, dest_key)
    s3_client.put_object(
        Bucket=bucket_name,
        Key=dest_key,
        Body=body,
        ContentType="application/pdf",
    )


def _handle_record(record: dict) -> None:
    """Inspect the PDF from *record* and copy it to the appropriate prefix."""

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    pdf_page_prefix = get_config("PDF_PAGE_PREFIX", bucket, key) or ""
    pdf_text_page_prefix = get_config("PDF_TEXT_PAGE_PREFIX", bucket, key) or "text-pages/"
    pdf_scan_page_prefix = get_config("PDF_SCAN_PAGE_PREFIX", bucket, key) or "scan-pages/"
    if pdf_page_prefix and not pdf_page_prefix.endswith("/"):
        pdf_page_prefix += "/"
    if pdf_text_page_prefix and not pdf_text_page_prefix.endswith("/"):
        pdf_text_page_prefix += "/"
    if pdf_scan_page_prefix and not pdf_scan_page_prefix.endswith("/"):
        pdf_scan_page_prefix += "/"
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(pdf_page_prefix):
        logger.info("Key %s outside prefix %s - skipping", key, pdf_page_prefix)
        return
    if not key.lower().endswith(".pdf"):
        logger.info("Key %s is not a PDF - skipping", key)
        return

    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = obj["Body"].read()
    has_text = _page_has_text(body)
    prefix = pdf_text_page_prefix if has_text else pdf_scan_page_prefix
    logger.info("Page %s has text: %s", key, has_text)
    _copy_page(bucket_name, pdf_page_prefix, key, body, prefix)

def lambda_handler(event: S3Event, context: dict) -> LambdaResponse:
    """Triggered by pages output from ``3-pdf-split``.

    Parameters
    ----------
    event : :class:`models.S3Event`
        Standard S3 event describing the page objects.

    1. Determines if each page contains embedded text and copies it to either
       ``PDF_TEXT_PAGE_PREFIX`` or ``PDF_SCAN_PAGE_PREFIX``.
    2. Logs any errors but continues processing remaining records.

    Returns
    -------
    :class:`models.LambdaResponse`
        Standard 200 response on completion.
    """

    logger.info("Received event for 4-pdf-page-classifier: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Error processing record %s: %s", rec, exc)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "4-pdf-page-classifier executed"}),
    }
