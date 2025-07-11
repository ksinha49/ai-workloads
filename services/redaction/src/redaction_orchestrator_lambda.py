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
sns_client = boto3.client("sns")
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
FILE_REDACTION_FUNCTION_ARN = get_config(
    "FILE_REDACTION_FUNCTION_ARN"
) or os.environ.get("FILE_REDACTION_FUNCTION_ARN")
DETECT_PII_FUNCTION_ARN = get_config("DETECT_PII_FUNCTION_ARN") or os.environ.get(
    "DETECT_PII_FUNCTION_ARN"
)
STATUS_TABLE = get_config("REDACTION_STATUS_TABLE") or os.environ.get(
    "REDACTION_STATUS_TABLE"
)
ALERT_TOPIC_ARN = get_config("ALERT_TOPIC_ARN") or os.environ.get("ALERT_TOPIC_ARN")

_status_table = dynamo.Table(STATUS_TABLE) if dynamo and STATUS_TABLE else None

PENDING = "PENDING"
IN_PROGRESS = "IN_PROGRESS"
FAILED = "FAILED"
COMPLETED = "COMPLETED"


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


def _notify_failure(doc_id: str, message: str) -> None:
    """Publish *message* to SNS if a topic is configured."""
    if not ALERT_TOPIC_ARN:
        return
    try:
        sns_client.publish(TopicArn=ALERT_TOPIC_ARN, Message=f"{doc_id}: {message}")
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to publish SNS alert: %s", exc)


def _invoke_lambda(
    function_arn: str, payload: Dict[str, Any], attempts: int = 3
) -> Dict[str, Any]:
    """Invoke Lambda with simple retry."""
    delay = 1
    for i in range(attempts):
        try:
            resp = lambda_client.invoke(
                FunctionName=function_arn,
                Payload=json.dumps(payload).encode("utf-8"),
            )
            body = resp.get("Payload")
            return json.loads(body.read()) if body else {}
        except Exception as exc:
            if i == attempts - 1:
                raise
            logger.warning("Retrying %s due to %s", function_arn, exc)
            time.sleep(delay)
            delay *= 2


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
        _update_status(doc_id, PENDING)
        try:
            _copy_to_idp(bucket, key, dest_key)
            _update_status(doc_id, IN_PROGRESS)
        except Exception as exc:
            logger.exception("Failed to copy %s/%s", bucket, key)
            _update_status(doc_id, FAILED, str(exc))
            _notify_failure(doc_id, "copy failed")
            results.append(
                {"document_id": doc_id, "error": {"step": "copy", "message": str(exc)}}
            )
            continue

        text_key = f"{TEXT_DOC_PREFIX}{doc_id}.json"
        hocr_key = f"{HOCR_PREFIX}{doc_id}.hocr"

        text_bytes = _wait_for_object(text_key)
        if text_bytes is None:
            logger.error("Timed out waiting for %s", text_key)
            _update_status(doc_id, FAILED, "timeout")
            _notify_failure(doc_id, "ocr timeout")
            results.append(
                {"document_id": doc_id, "error": {"step": "ocr", "message": "timeout"}}
            )
            continue

        _update_status(doc_id, IN_PROGRESS)

        try:
            payload = json.loads(text_bytes.decode("utf-8"))
            text_content = "\n".join(payload.get("pages", []))
        except Exception as exc:  # pragma: no cover - invalid json
            logger.exception("Invalid text document for %s", doc_id)
            _update_status(doc_id, FAILED, str(exc))
            _notify_failure(doc_id, "invalid text")
            results.append(
                {"document_id": doc_id, "error": {"step": "parse", "message": str(exc)}}
            )
            continue

        try:
            resp = _invoke_lambda(
                DETECT_PII_FUNCTION_ARN,
                {"text": text_content},
            )
            pii = resp.get("entities", [])
        except Exception as exc:  # pragma: no cover - runtime
            logger.exception("PII detection failed for %s", doc_id)
            _update_status(doc_id, FAILED, str(exc))
            _notify_failure(doc_id, "pii detection failed")
            results.append(
                {"document_id": doc_id, "error": {"step": "pii", "message": str(exc)}}
            )
            continue

        _update_status(doc_id, IN_PROGRESS)

        try:
            redaction_payload = {
                "bucket": IDP_BUCKET,
                "key": dest_key,
                "hocr_key": hocr_key,
                "entities": pii,
            }
            _invoke_lambda(
                FILE_REDACTION_FUNCTION_ARN,
                redaction_payload,
            )
            _update_status(doc_id, COMPLETED)
            results.append({"document_id": doc_id, "started": True})
        except Exception as exc:  # pragma: no cover - runtime
            logger.exception("Failed to invoke redaction for %s", doc_id)
            _update_status(doc_id, FAILED, str(exc))
            _notify_failure(doc_id, "redaction invoke failed")
            results.append(
                {
                    "document_id": doc_id,
                    "error": {"step": "redaction", "message": str(exc)},
                }
            )
    if not results:
        return error_response(logger, 400, "No records in event")
    return {"statusCode": 200, "body": results}
