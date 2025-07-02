"""Start the ingestion workflow for a knowledge base document."""

from __future__ import annotations

import json
import os
import logging
from common_utils import configure_logger
import boto3

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")

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

    payload = {"text": text}
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
    sfn.start_execution(stateMachineArn=STATE_MACHINE_ARN, input=json.dumps(payload))
    return {"started": True}
