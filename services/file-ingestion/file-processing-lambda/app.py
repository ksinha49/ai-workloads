# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  1. Retrieves SSM parameters using a proxy configuration.
  2. Copies the uploaded file to the IDP bucket so downstream services can
     automatically process the document.

Version: 1.0.2
Created: 2025-05-05
Last Modified: 2025-06-28
Modified By: Koushik Sinha
"""

from __future__ import annotations
import os
import uuid
import boto3
import logging
import re
try:
    from botocore.exceptions import ClientError
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal env
    class ClientError(Exception):
        pass
from common_utils import configure_logger
from common_utils.get_ssm import (
    get_values_from_ssm,
    get_environment_prefix,
    parse_s3_uri,
)
from models import FileProcessingEvent

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.2"
__modified_by__ = "Koushik Sinha"

# ─── Logging Configuration ─────────────────────────────────────────────────────
logger = configure_logger(__name__)

_s3_client = boto3.client("s3")

# allowed characters for S3 URIs and collection names
S3_URI_PATTERN = re.compile(r"^s3://[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$")
COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_event(event: FileProcessingEvent) -> None:
    """Validate and sanitize incoming ``FileProcessingEvent``."""

    if not isinstance(event.file, str) or not S3_URI_PATTERN.match(event.file):
        raise ValueError("invalid file path")
    if (
        event.collection_name is None
        or not isinstance(event.collection_name, str)
        or not COLLECTION_PATTERN.match(event.collection_name)
    ):
        raise ValueError("invalid collection_name")

def copy_file_to_idp(bucket_name: str, bucket_key: str) -> str:
    """Copy the file to the IDP bucket RAW_PREFIX and return the destination URI."""

    prefix = get_environment_prefix()
    idp_bucket = get_values_from_ssm(f"{prefix}/IDP_BUCKET")
    raw_prefix = get_values_from_ssm(f"{prefix}/RAW_PREFIX") or ""

    if not idp_bucket:
        raise ValueError("IDP_BUCKET not configured")

    if raw_prefix and not raw_prefix.endswith("/"):
        raw_prefix += "/"

    file_name = os.path.basename(bucket_key)
    dest_key = f"{raw_prefix}{file_name}"
    _s3_client.copy_object(
        Bucket=idp_bucket,
        Key=dest_key,
        CopySource={"Bucket": bucket_name, "Key": bucket_key},
    )

    return f"s3://{idp_bucket}/{dest_key}"


def process_files(event: FileProcessingEvent, context) -> dict:
    """Copy the uploaded file to the IDP bucket and return its location."""

    _validate_event(event)

    try:
        bucket_name, bucket_key = parse_s3_uri(event.file)
        logger.info("Copying %s/%s to IDP bucket", bucket_name, bucket_key)
        dest_uri = copy_file_to_idp(bucket_name, bucket_key)

        # Delete the source file now that it has been copied. This prevents the
        # same document from being processed multiple times and more closely
        # mirrors a move operation.
        try:
            _s3_client.delete_object(Bucket=bucket_name, Key=bucket_key)
        except AttributeError:
            logger.warning("S3 client not available for deletion of %s/%s", bucket_name, bucket_key)

        document_id = os.path.splitext(os.path.basename(bucket_key))[0]
        file_name = os.path.basename(bucket_key)
        file_guid = uuid.uuid4().hex

        result = {
            "document_id": document_id,
            "s3_location": dest_uri,
            "file_name": file_name,
            "file_guid": file_guid,
        }
        for key in (
            "ingest_params",
            "retrieve_params",
            "router_params",
            "llm_params",
        ):
            value = getattr(event, key)
            if value is not None:
                result[key] = value
        if event.collection_name is not None:
            result["collection_name"] = event.collection_name
        result.update(event.extra)
        return result
    except (KeyError, ClientError) as exc:
        logger.error("Failed to process file: %s", exc)
        raise

def _response(status: int, body: dict) -> dict:
    """Helper to build a consistent Lambda response."""
    return {"statusCode": status, "body": body}


def lambda_handler(event: FileProcessingEvent | dict, context) -> dict:
    """Triggered after a file upload to start processing.

    1. Copies the file to the IDP bucket so subsequent steps can operate on it.
    2. Returns the destination URI or an error message.

    Returns an HTTP style response with status and body.
    """

    logger.info("Starting Lambda function...")
    try:
        if isinstance(event, dict):
            try:
                event = FileProcessingEvent.from_dict(event)
            except ValueError as exc:
                logger.error("Invalid event: %s", exc)
                return _response(400, {"error": str(exc)})
        try:
            _validate_event(event)
        except ValueError as exc:
            logger.error("Invalid event: %s", exc)
            return _response(400, {"error": str(exc)})
        final_response = process_files(event, context)
        return _response(200, final_response)
    except (KeyError, ValueError) as exc:
        logger.error("Missing key in request: %s", exc)
        return _response(400, {"error": str(exc)})
    except ClientError as exc:
        logger.error("AWS client error: %s", exc)
        return _response(500, {"error": str(exc)})
