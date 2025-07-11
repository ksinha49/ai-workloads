from __future__ import annotations

"""Lambda orchestrating redaction of uploaded documents.

The handler can be triggered by an S3 event or direct API call. It copies the
source file to the IDP bucket, waits for OCR results and then invokes the
anonymization and file redaction services.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Iterable

import boto3

from common_utils import configure_logger
from common_utils.error_utils import error_response
from common_utils.get_ssm import get_config, parse_s3_uri

logger = configure_logger(__name__)

s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")
try:  # DynamoDB may be stubbed in tests
    dynamo = boto3.resource("dynamodb")
except Exception:  # pragma: no cover - boto3 missing
    dynamo = None

IDP_BUCKET = get_config("IDP_BUCKET") or os.environ.get("IDP_BUCKET")
RAW_PREFIX = get_config("RAW_PREFIX") or os.environ.get("RAW_PREFIX", "raw/")
TEXT_DOC_PREFIX = get_config("TEXT_DOC_PREFIX") or os.environ.get(
    "TEXT_DOC_PREFIX", "text-docs/"
)
HOCR_PREFIX = get_config("HOCR_PREFIX") or os.environ.get("HOCR_PREFIX", "hocr/")
FILE_REDACTION_FUNCTION_ARN = (
    get_config("FILE_REDACTION_FUNCTION_ARN")
    or os.environ.get("FILE_REDACTION_FUNCTION_ARN")
)
DETECT_PII_FUNCTION_ARN = (
    get_config("DETECT_PII_FUNCTION_ARN") or os.environ.get("DETECT_PII_FUNCTION_ARN")
)
STATUS_TABLE = get_config("REDACTION_STATUS_TABLE") or os.environ.get("REDACTION_STATUS_TABLE")

_status_table = dynamo.Table(STATUS_TABLE) if dynamo and STATUS_TABLE else None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _update_status(doc_id: str, status: str, info: str | None = None) -> None:
    """Update the status record for *doc_id* if a table is configured."""
    if not _status_table:
        return
    try:
        expr = "SET #s = :s"
        names = {"#s": "status"}
        values: Dict[str, Any] = {":s": status}
        if info is not None:
            expr += ", info = :i"
            values[":i"] = info
        _status_table.update_item(
            Key={"document_id": doc_id},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to update status: %s", exc)


def _iter_records(event: Dict[str, Any]) -> Iterable[tuple[str, str]]:
    """Yield ``(bucket, key)`` tuples from *event*."""
    records = event.get("Records")
    if records:
        for record in records:
            bucket = record.get("s3", {}).get("bucket", {}).get("name")
            key = record.get("s3", {}).get("object", {}).get("key")
            if bucket and key:
                yield bucket, key
        return
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = event
    file_uri = body.get("file")
    if file_uri:
        yield parse_s3_uri(file_uri)


def _copy_to_idp(bucket: str, key: str, dest_key: str) -> None:
    """Copy ``bucket/key`` to the IDP bucket under ``dest_key``."""
    s3_client.copy_object(
        Bucket=IDP_BUCKET,
        Key=dest_key,
        CopySource={"Bucket": bucket, "Key": key},
    )


def _wait_for_object(key: str, timeout: int = 300, interval: int = 5) -> bytes | None:
    """Return object bytes once ``key`` exists in the IDP bucket."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            obj = s3_client.get_object(Bucket=IDP_BUCKET, Key=key)
            return obj["Body"].read()
        except s3_client.exceptions.NoSuchKey:
            time.sleep(interval)
        except s3_client.exceptions.ClientError as exc:  # pragma: no cover
            if exc.response.get("Error", {}).get("Code") == "404":
                time.sleep(interval)
            else:
                raise
    return None


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle S3 or API events to start document redaction."""

    logger.info("Received event: %s", event)
    results = []
    for bucket, key in _iter_records(event):
        doc_id = os.path.splitext(os.path.basename(key))[0]
        dest_key = f"{RAW_PREFIX}{os.path.basename(key)}"
        try:
            _copy_to_idp(bucket, key, dest_key)
            _update_status(doc_id, "UPLOADED")
        except Exception as exc:
            logger.exception("Failed to copy %s/%s", bucket, key)
            results.append({"document_id": doc_id, "error": str(exc)})
            continue

        text_key = f"{TEXT_DOC_PREFIX}{doc_id}.json"
        hocr_key = f"{HOCR_PREFIX}{doc_id}.hocr"

        text_bytes = _wait_for_object(text_key)
        if text_bytes is None:
            logger.error("Timed out waiting for %s", text_key)
            _update_status(doc_id, "TIMEOUT")
            results.append({"document_id": doc_id, "error": "timeout"})
            continue

        _update_status(doc_id, "OCR_COMPLETE")

        try:
            payload = json.loads(text_bytes.decode("utf-8"))
            text_content = "\n".join(payload.get("pages", []))
        except Exception as exc:  # pragma: no cover - invalid json
            logger.exception("Invalid text document for %s", doc_id)
            results.append({"document_id": doc_id, "error": str(exc)})
            continue

        try:
            resp = lambda_client.invoke(
                FunctionName=DETECT_PII_FUNCTION_ARN,
                Payload=json.dumps({"text": text_content}).encode("utf-8"),
            )
            pii = json.loads(resp["Payload"].read()).get("entities", [])
        except Exception as exc:  # pragma: no cover - runtime
            logger.exception("PII detection failed for %s", doc_id)
            _update_status(doc_id, "PII_ERROR", str(exc))
            results.append({"document_id": doc_id, "error": str(exc)})
            continue

        _update_status(doc_id, "PII_DETECTED")

        try:
            redaction_payload = {
                "bucket": IDP_BUCKET,
                "key": dest_key,
                "hocr_key": hocr_key,
                "entities": pii,
            }
            lambda_client.invoke(
                FunctionName=FILE_REDACTION_FUNCTION_ARN,
                InvocationType="Event",
                Payload=json.dumps(redaction_payload).encode("utf-8"),
            )
            _update_status(doc_id, "REDACTION_STARTED")
            results.append({"document_id": doc_id, "started": True})
        except Exception as exc:  # pragma: no cover - runtime
            logger.exception("Failed to invoke redaction for %s", doc_id)
            _update_status(doc_id, "REDACTION_ERROR", str(exc))
            results.append({"document_id": doc_id, "error": str(exc)})
    if not results:
        return error_response(logger, 400, "No records in event")
    return {"statusCode": 200, "body": results}
