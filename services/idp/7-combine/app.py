# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""Combine per-page text outputs into a single document JSON.

Triggered whenever a page-level text object is written.  Once all page
outputs exist for a document (as indicated by the ``manifest.json`` from
``PDF_PAGE_PREFIX``), the individual page results are merged in page order
and written to ``TEXT_DOC_PREFIX/{documentId}.json``.  The payload stores
the Markdown for each page under the ``pages`` key and includes the total
``pageCount``.

Environment variables
---------------------
``BUCKET_NAME``
    Name of the S3 bucket used for input and output. **Required.**
``PDF_PAGE_PREFIX``
    Prefix where PDF pages and the ``manifest.json`` are stored. Defaults to
    ``"pdf-pages/"``.
``TEXT_PAGE_PREFIX``
    Prefix containing per-page text outputs. Defaults to ``"text-pages/"``.
``TEXT_DOC_PREFIX``
    Destination prefix for the combined document JSON. Defaults to
    ``"text-docs/"``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import boto3
from common_utils import get_config

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


def _load_manifest(bucket_name: str, pdf_page_prefix: str, doc_id: str) -> dict | None:
    """Return the manifest dictionary for *doc_id* or ``None`` if missing."""

    key = f"{pdf_page_prefix}{doc_id}/manifest.json"
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    except s3_client.exceptions.NoSuchKey:  # pragma: no cover - defensive
        logger.info("Manifest %s not found", key)
        return None
    return json.loads(obj["Body"].read())


def _page_key(bucket_name: str, text_page_prefix: str, doc_id: str, page_num: int) -> str | None:
    """Return the Markdown S3 key for page ``page_num`` of ``doc_id`` if it exists."""

    key = f"{text_page_prefix}{doc_id}/page_{page_num:03d}.md"
    try:
        s3_client.head_object(Bucket=bucket_name, Key=key)
    except s3_client.exceptions.ClientError as exc:  # pragma: no cover - defensive
        if exc.response.get("Error", {}).get("Code") == "404":
            return None
        raise
    return key


def _read_page(bucket_name: str, key: str) -> str:
    """Return the Markdown text for page ``key``."""

    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = obj["Body"].read()
    return body.decode("utf-8")


def _combine_document(bucket_name: str, pdf_page_prefix: str, text_page_prefix: str, text_doc_prefix: str, doc_id: str) -> None:
    """If all page outputs for ``doc_id`` exist, merge them and upload."""

    manifest = _load_manifest(bucket_name, pdf_page_prefix, doc_id)
    if not manifest:
        return

    page_count = int(manifest.get("pages", 0))

    page_keys: list[str] = []
    for idx in range(1, page_count + 1):
        key = _page_key(bucket_name, text_page_prefix, doc_id, idx)
        if not key:
            logger.info("Waiting for page %03d of %s", idx, doc_id)
            return
        page_keys.append(key)

    pages = [_read_page(bucket_name, k) for k in page_keys]
    payload = {
        "documentId": doc_id,
        "type": "pdf",
        "pageCount": page_count,
        "pages": pages,
    }

    dest_key = f"{text_doc_prefix}{doc_id}.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=dest_key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Wrote %s", dest_key)


def _handle_record(record: dict) -> None:
    """Process a single S3 event record."""

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    pdf_page_prefix = get_config("PDF_PAGE_PREFIX", bucket, key) or "pdf-pages/"
    text_page_prefix = get_config("TEXT_PAGE_PREFIX", bucket, key) or "text-pages/"
    text_doc_prefix = get_config("TEXT_DOC_PREFIX", bucket, key) or "text-docs/"
    if pdf_page_prefix and not pdf_page_prefix.endswith("/"):
        pdf_page_prefix += "/"
    if text_page_prefix and not text_page_prefix.endswith("/"):
        text_page_prefix += "/"
    if text_doc_prefix and not text_doc_prefix.endswith("/"):
        text_doc_prefix += "/"
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(text_page_prefix):
        logger.info("Key %s outside prefix %s - skipping", key, text_page_prefix)
        return

    rel = key[len(text_page_prefix):]
    parts = rel.split("/", 1)
    if not parts:
        logger.info("Unexpected key structure: %s", key)
        return
    doc_id = parts[0]
    _combine_document(bucket_name, pdf_page_prefix, text_page_prefix, text_doc_prefix, doc_id)


def lambda_handler(event: dict, context: dict) -> dict:
    """Triggered when page-level text outputs are written.

    1. Checks if all pages for a document exist based on ``manifest.json`` and
       combines them into a single JSON under ``TEXT_DOC_PREFIX``.
    2. Continues processing remaining records even if errors occur.

    Returns a 200 response upon completion.
    """

    logger.info("Received event for 7-combine: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Error processing record %s: %s", rec, exc)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "7-combine executed"})
    }
