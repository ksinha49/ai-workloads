# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------

"""PDF page splitting Lambda.

This function is triggered by S3 events for objects uploaded under
``PDF_RAW_PREFIX``. Each PDF is downloaded, split into individual page
files named ``page_NNN.pdf`` under ``PDF_PAGE_PREFIX/{documentId}``, and a
``manifest.json`` describing the total page count is written alongside the
pages.

Environment variables
---------------------
``BUCKET_NAME``
    Name of the S3 bucket used for both input and output. **Required.**
``PDF_RAW_PREFIX``
    Prefix within the bucket where raw PDFs are stored.
``PDF_PAGE_PREFIX``
    Prefix for the output pages. Defaults to ``"pdf-pages/"``.
"""

from __future__ import annotations

import io
import json
import os
from typing import Iterable
from models import S3Event, LambdaResponse

import boto3
from common_utils import get_config, configure_logger, iter_s3_records
from PyPDF2 import PdfReader, PdfWriter

__author__ = "Koushik Sinha"
__version__ = "1.0.0"


logger = configure_logger(__name__)

s3_client = boto3.client("s3")
try:  # pragma: no cover - boto3 may be stubbed
    dynamo = boto3.resource("dynamodb")
except AttributeError:
    dynamo = None
try:
    _audit_table_name = get_config("DOCUMENT_AUDIT_TABLE")
except Exception:  # pragma: no cover - SSM unavailable
    _audit_table_name = None
_audit_table_name = _audit_table_name or os.environ.get("DOCUMENT_AUDIT_TABLE")
_audit_table = dynamo.Table(_audit_table_name) if dynamo and _audit_table_name else None





def _split_pdf(
    bucket_name: str, pdf_page_prefix: str, key: str, document_id: str | None = None
) -> None:
    """Split the PDF stored at *key* into per-page files."""
    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    pdf_bytes = obj["Body"].read()
    doc = PdfReader(io.BytesIO(pdf_bytes))
    doc_id = document_id or os.path.splitext(os.path.basename(key))[0]
    for idx, page in enumerate(doc.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        dest_key = f"{pdf_page_prefix}{doc_id}/page_{idx:03d}.pdf"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=dest_key,
            Body=buf.getvalue(),
            ContentType="application/pdf",
        )
        logger.info("Wrote %s", dest_key)

    manifest_key = f"{pdf_page_prefix}{doc_id}/manifest.json"
    manifest = {
        "documentId": doc_id,
        "pages": len(doc.pages),
    }
    s3_client.put_object(
        Bucket=bucket_name,
        Key=manifest_key,
        Body=json.dumps(manifest).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Wrote %s", manifest_key)
    if _audit_table:
        try:
            _audit_table.update_item(
                Key={"document_id": doc_id},
                UpdateExpression="SET #s = :s, page_count = :c",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "SPLIT", ":c": len(doc.pages)},
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to update audit record: %s", exc)


def _handle_record(record: dict, document_id: str | None = None) -> None:
    """Process a single S3 event record."""
    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    pdf_raw_prefix = get_config("PDF_RAW_PREFIX", bucket, key) or os.environ.get("PDF_RAW_PREFIX", "")
    pdf_page_prefix = get_config("PDF_PAGE_PREFIX", bucket, key) or os.environ.get("PDF_PAGE_PREFIX")
    if pdf_raw_prefix and not pdf_raw_prefix.endswith("/"):
        pdf_raw_prefix += "/"
    if pdf_page_prefix and not pdf_page_prefix.endswith("/"):
        pdf_page_prefix += "/"
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(pdf_raw_prefix):
        logger.info("Key %s outside prefix %s - skipping", key, pdf_raw_prefix)
        return
    if not key.lower().endswith(".pdf"):
        logger.info("Key %s is not a PDF - skipping", key)
        return
    logger.info("Splitting %s", key)
    _split_pdf(bucket_name, pdf_page_prefix, key, document_id)

def lambda_handler(event: S3Event, context: dict) -> LambdaResponse:
    """Triggered by PDFs uploaded to ``PDF_RAW_PREFIX``.

    Parameters
    ----------
    event : :class:`models.S3Event`
        S3 event referencing the uploaded PDF files.

    1. For each S3 record, splits the PDF into page files under
       ``PDF_PAGE_PREFIX`` and writes a ``manifest.json``.
    2. Errors per record are logged and processing continues.

    Returns
    -------
    :class:`models.LambdaResponse`
        200 status once splitting is complete.
    """
    logger.info("Received event for 3-pdf-split: %s", event)
    doc_id = getattr(event, "document_id", None)
    if isinstance(event, dict):
        doc_id = event.get("document_id", doc_id)
    for rec in iter_s3_records(event):
        try:
            _handle_record(rec, doc_id)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Error processing record %s: %s", rec, exc)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "3-pdf-split executed"})
    }
