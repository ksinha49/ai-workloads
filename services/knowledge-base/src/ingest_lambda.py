"""Start the ingestion workflow for a knowledge base document."""

from __future__ import annotations

import json
import os
import logging
from common_utils import configure_logger
from common_utils.get_ssm import get_config
import boto3
from botocore.exceptions import ClientError

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

STATE_MACHINE_ARN = get_config("STATE_MACHINE_ARN") or os.environ.get(
    "STATE_MACHINE_ARN"
)
if not STATE_MACHINE_ARN:
    raise RuntimeError("STATE_MACHINE_ARN not configured")

FILE_INGESTION_STATE_MACHINE_ARN = (
    get_config("FILE_INGESTION_STATE_MACHINE_ARN")
    or os.environ.get("FILE_INGESTION_STATE_MACHINE_ARN")
)
if not FILE_INGESTION_STATE_MACHINE_ARN:
    raise RuntimeError("FILE_INGESTION_STATE_MACHINE_ARN not configured")

KB_VECTOR_DB_BACKEND = (
    get_config("KB_VECTOR_DB_BACKEND")
    or os.environ.get("KB_VECTOR_DB_BACKEND", "persistent")
)

sfn = boto3.client("stepfunctions")


def lambda_handler(event: dict, context: object) -> dict:
    """Triggered by API requests to ingest a document.

    1. Builds a payload from ``event`` and starts the ingestion state machine.
    2. Optional metadata fields are forwarded to the workflow.

    Returns ``{"started": True}`` if the workflow was invoked.
    """

    text = event.get("text")
    if not text:
        return {"started": False}

    collection_name = event.get("collection_name")
    if not collection_name:
        logger.error("collection_name missing from request")
        return {"started": False}
    if not collection_name.startswith("kb_"):
        logger.error("collection_name must start with kb_")
        return {"started": False}

    try:
        sfn.start_execution(
            stateMachineArn=FILE_INGESTION_STATE_MACHINE_ARN,
            input=json.dumps(event),
        )
    except ClientError as exc:
        logger.error("Failed to start file ingestion state machine: %s", exc)
        return {"started": False, "error": str(exc)}

    payload = {
        "text": text,
        "collection_name": collection_name,
        "storage_mode": KB_VECTOR_DB_BACKEND,
    }
    file_guid = event.get("file_guid")
    if file_guid:
        payload["file_guid"] = file_guid
    file_name = event.get("file_name")
    if file_name:
        payload["file_name"] = file_name
    doc_type = event.get("docType") or event.get("type")
    metadata = {}
    if doc_type:
        payload["docType"] = doc_type
        metadata["docType"] = doc_type

    for key in ("department", "team", "user"):
        value = event.get(key)
        if value:
            metadata[key] = value

    if metadata:
        payload["metadata"] = metadata
    try:
        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(payload),
        )
    except ClientError as exc:
        logger.error("Failed to start state machine: %s", exc)
        return {"started": False, "error": str(exc)}
    return {"started": True}
