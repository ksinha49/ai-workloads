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
import os
import urllib.error
import urllib.request

import boto3
from common_utils import get_config, configure_logger
from models import S3Event, LambdaResponse
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



def _iter_records(event: S3Event):
    """Yield S3 event records from *event*."""

    records = event.Records if hasattr(event, "Records") else event.get("Records", [])
    for record in records:
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
    except urllib.error.URLError as exc:
        logger.error("Connection error posting %s: %s", payload.get("documentId"), exc)
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected failure posting %s", payload.get("documentId"))
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
    except (ClientError, BotoCoreError, json.JSONDecodeError) as exc:
        logger.error("Failed to read %s: %s", key, exc)
        return
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected error reading %s", key)
        return

    if _post_to_api(payload, api_url, api_key):
        logger.info("Successfully posted %s", key)
    else:
        logger.error("Failed to post %s", key)

def lambda_handler(event: S3Event, context: dict) -> LambdaResponse:
    """Triggered when final outputs appear in S3.

    Parameters
    ----------
    event : :class:`models.S3Event`
        S3 event containing the final JSON files.

    1. Reads each record and posts the payload to an external API endpoint.
    2. Logs success or failure for each upload attempt.

    Returns
    -------
    :class:`models.LambdaResponse`
        200 status to signal completion to the workflow.
    """

    logger.info("Received event for 8-output: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except (ClientError, BotoCoreError, json.JSONDecodeError, urllib.error.URLError) as exc:
            logger.error("Error processing record %s: %s", rec, exc)
        except Exception as exc:  # pragma: no cover - unexpected
            logger.exception("Unexpected error processing record %s", rec)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "8-output executed"})
    }
