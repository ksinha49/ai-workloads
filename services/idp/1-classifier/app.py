"""
Classifier Lambda function.

This function routes newly uploaded objects from the RAW_PREFIX into
either OFFICE_PREFIX or PDF_RAW_PREFIX based on file type.  PDFs are
inspected with PyMuPDF to determine whether they contain embedded text.
"""

from __future__ import annotations

import json
import os
from typing import Iterable
from models import S3Event, LambdaResponse

import boto3
from common_utils import get_config, configure_logger
import fitz  # PyMuPDF
try:
    from botocore.exceptions import ClientError, BotoCoreError
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal env
    class ClientError(Exception):
        pass

    class BotoCoreError(Exception):
        pass

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

s3_client = boto3.client("s3")


def _pdf_has_text(pdf_bytes: bytes) -> bool:
    """Return True if any page in the PDF has text."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            if page.get_text().strip():
                return True
    except (fitz.FileDataError, ValueError) as exc:  # pragma: no cover - expected
        logger.error("Failed to inspect PDF: %s", exc)
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected error inspecting PDF")
    return False

def _copy_to_prefix(
    bucket_name: str,
    raw_prefix: str,
    key: str,
    body: bytes,
    dest_prefix: str,
    content_type: str | None = None,
) -> None:
    """Copy an object to ``dest_prefix`` preserving its relative path.

    Parameters
    ----------
    bucket_name:
        Name of the bucket where the object will be written.
    raw_prefix:
        Prefix of the source object.  This portion of ``key`` is removed
        when constructing the destination key.
    key:
        Full S3 key of the source object.
    body:
        Bytes of the object to upload.
    dest_prefix:
        Target prefix for the copy operation.
    content_type:
        Optional content type to set on the new object.
    """

    dest_key = dest_prefix + key[len(raw_prefix):]
    logger.info("Copying %s to %s", key, dest_key)
    put_kwargs = {"Bucket": bucket_name, "Key": dest_key, "Body": body}
    if content_type:
        put_kwargs["ContentType"] = content_type
    s3_client.put_object(**put_kwargs)

def _handle_record(record: dict) -> None:
    """Classify and copy a single object referenced in an S3 record.

    The record's bucket and key are validated against configuration
    settings.  Office documents and PDFs with embedded text are copied
    to ``OFFICE_PREFIX`` while image-only PDFs are copied to
    ``PDF_RAW_PREFIX``.
    """

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    raw_prefix = get_config("RAW_PREFIX", bucket, key) or ""
    office_prefix = get_config("OFFICE_PREFIX", bucket, key) or "office-docs/"
    pdf_raw_prefix = get_config("PDF_RAW_PREFIX", bucket, key) or "pdf-raw/"
    if raw_prefix and not raw_prefix.endswith("/"):
        raw_prefix += "/"
    if office_prefix and not office_prefix.endswith("/"):
        office_prefix += "/"
    if pdf_raw_prefix and not pdf_raw_prefix.endswith("/"):
        pdf_raw_prefix += "/"
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(raw_prefix):
        logger.info("Key %s outside prefix %s - skipping", key, raw_prefix)
        return

    logger.info("Processing %s", key)
    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = obj["Body"].read()
    content_type = obj.get("ContentType")

    ext = os.path.splitext(key)[1].lower()
    if ext == ".pdf":
        has_text = _pdf_has_text(body)
        logger.info("PDF %s has embedded text: %s", key, has_text)
        prefix = office_prefix if has_text else pdf_raw_prefix
    else:
        prefix = office_prefix
    _copy_to_prefix(bucket_name, raw_prefix, key, body, prefix, content_type)

def _iter_records(event: S3Event) -> Iterable[dict]:
    """Yield each S3 record contained in ``event``."""

    records = event.Records if hasattr(event, "Records") else event.get("Records", [])
    for record in records:
        yield record

def lambda_handler(event: S3Event, context) -> LambdaResponse:
    """Triggered by new files in ``RAW_PREFIX``.

    Parameters
    ----------
    event : :class:`models.S3Event`
        Standard S3 event object for the newly uploaded files.

    The function iterates over ``event.Records`` and classifies each object into
    Office or PDF storage locations. Any errors are logged but do not stop
    processing.

    Returns
    -------
    :class:`models.LambdaResponse`
        200 response indicating completion.
    """

    logger.info("Received event: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except (ClientError, BotoCoreError, fitz.FileDataError, ValueError) as exc:
            logger.error("Error processing record %s: %s", rec, exc)
        except Exception as exc:  # pragma: no cover - unexpected
            logger.exception("Unexpected error processing record %s", rec)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "1-classifier executed"}),
    }
