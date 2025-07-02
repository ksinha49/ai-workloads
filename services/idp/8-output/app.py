# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  Basic Lambda handler for 8-output.
Version: 1.0.0
"""

from __future__ import annotations
import json
import logging
import os
import urllib.error
import urllib.request

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



def _iter_records(event: dict):
    """Yield S3 event records from *event*."""

    for record in event.get("Records", []):
        yield record


def _post_to_api(payload: dict, url: str, api_key: str | None) -> bool:
    """Send *payload* to the external API and return ``True`` on success."""

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("x-api-key", api_key)

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.getcode()
            if 200 <= status < 300:
                return True
            logger.error("API returned status %s for %s", status, payload.get("documentId"))
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode()
        logger.error(
            "HTTP error posting %s: %s %s",
            payload.get("documentId"),
            exc.code,
            msg,
        )
    except Exception as exc:
        logger.error("Failed to post %s: %s", payload.get("documentId"), exc)
    return False


def _handle_record(record: dict) -> None:
    """Process a single S3 event record."""

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    text_doc_prefix = get_config("TEXT_DOC_PREFIX", bucket, key) or "text-docs/"
    api_url = get_config("EDI_SEARCH_API_URL", bucket, key)
    api_key = get_config("EDI_SEARCH_API_KEY", bucket, key)
    if text_doc_prefix and not text_doc_prefix.endswith("/"):
        text_doc_prefix += "/"
    if not bucket_name or not api_url:
        logger.error("Missing configuration")
        return
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(text_doc_prefix) or not key.lower().endswith(".json"):
        logger.info("Key %s outside prefix %s - skipping", key, text_doc_prefix)
        return

    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=key)
        body = obj["Body"].read()
        payload = json.loads(body)
    except Exception as exc:
        logger.error("Failed to read %s: %s", key, exc)
        return

    if _post_to_api(payload, api_url, api_key):
        logger.info("Successfully posted %s", key)
    else:
        logger.error("Failed to post %s", key)

def lambda_handler(event: dict, context: dict) -> dict:
    """Triggered when final outputs appear in S3.

    1. Reads each record and posts the payload to an external API endpoint.
    2. Logs success or failure for each upload attempt.

    Returns a 200 status to signal completion to the workflow.
    """

    logger.info("Received event for 8-output: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Error processing record %s: %s", rec, exc)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "8-output executed"})
    }
