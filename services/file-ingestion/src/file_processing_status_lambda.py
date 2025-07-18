# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  Poll S3 for the text document produced by the IDP pipeline.  When the
  ``TEXT_DOC_PREFIX`` JSON exists in the ``IDP_BUCKET`` the status is
  updated to ``"COMPLETE"``.

Version: 1.0.2
Created: 2025-05-05
Last Modified: 2025-06-28
Modified By: Koushik Sinha
"""
from __future__ import annotations
import boto3
import logging
from common_utils import configure_logger, lambda_response
import os
from models import ProcessingStatusEvent
from common_utils.get_ssm import (
    get_values_from_ssm,
    get_environment_prefix,
)

# Module Metadata
__author__ = "Koushik Sinha"  # Author name (please fill this in)
__version__ = "1.0.2"  # Version number of the module
__modified_by__ = "Koushik Sinha"

# ─── Logging Configuration ─────────────────────────────────────────────────────
logger = configure_logger(__name__)



# No proxy configuration is required for SSM access when running within AWS.

s3_client = boto3.client("s3")
try:  # pragma: no cover - boto3 may be stubbed
    dynamo = boto3.resource("dynamodb")
except AttributeError:
    dynamo = None
try:
    _audit_table_name = get_values_from_ssm(
        f"{get_environment_prefix()}/DOCUMENT_AUDIT_TABLE"
    )
except Exception:  # pragma: no cover - SSM unavailable
    _audit_table_name = None
_audit_table_name = _audit_table_name or os.getenv("DOCUMENT_AUDIT_TABLE")
audit_table = dynamo.Table(_audit_table_name) if dynamo and _audit_table_name else None

def _get_param(name: str) -> str | None:
    """Return ``name`` from environment or SSM."""
    return os.getenv(name) or get_values_from_ssm(f"{get_environment_prefix()}/{name}")

def check_file_processing_status(event: ProcessingStatusEvent, context) -> dict:
    """Return updated *event* with processing status.

    The function looks for ``TEXT_DOC_PREFIX/{document_id}.json`` in the IDP
    bucket.  If the object exists ``fileupload_status`` is set to
    ``"COMPLETE"``.
    """

    document_id = event.document_id
    event_body = event.to_dict()

    bucket = _get_param("IDP_BUCKET")
    prefix = _get_param("TEXT_DOC_PREFIX") or "text-docs/"
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    key = f"{prefix}{document_id}.json"

    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except s3_client.exceptions.ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "404":
            event_body["fileupload_status"] = "PROCESSING"
            if audit_table:
                try:
                    item = audit_table.get_item(Key={"document_id": document_id}).get("Item")
                    if item:
                        event_body["status"] = item.get("status")
                        if "page_count" in item:
                            event_body["page_count"] = item["page_count"]
                except Exception as exc:  # pragma: no cover - best effort
                    logger.warning("Failed to read audit record: %s", exc)
            return event_body
        raise

    event_body["fileupload_status"] = "COMPLETE"
    event_body["text_doc_key"] = key
    if audit_table:
        try:
            item = audit_table.get_item(Key={"document_id": document_id}).get("Item")
            if item:
                event_body["status"] = item.get("status")
                if "page_count" in item:
                    event_body["page_count"] = item["page_count"]
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to read audit record: %s", exc)
    return event_body




def lambda_handler(event: ProcessingStatusEvent | dict, context) -> dict:
    """Triggered periodically to poll processing status.

    1. Checks S3 for the text output produced by the IDP pipeline.
    2. Updates the event with the current status and collection details.

    Returns an HTTP style response with the status information.
    """

    logger.info("Starting Lambda function...")

    try:
        if isinstance(event, dict):
            try:
                event = ProcessingStatusEvent.from_dict(event)
            except ValueError as exc:
                logger.exception("Invalid request to lambda_handler")
                return lambda_response(400, {"statusMessage": str(exc)})
        body = check_file_processing_status(event, context)
        logger.info("Returning final response: %s", body)
        return lambda_response(200, body)
    except Exception as e:
        logger.exception("lambda_handler failed")
        return lambda_response(500, {"statusMessage": str(e)})
