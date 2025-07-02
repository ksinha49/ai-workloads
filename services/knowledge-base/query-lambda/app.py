"""Query the knowledge base and enqueue a summarization request.

The request payload is forwarded to the SQS queue defined by the
``SUMMARY_QUEUE_URL`` environment variable.
"""

from __future__ import annotations

import json
import os
import logging
from common_utils import configure_logger
import boto3
from botocore.exceptions import ClientError

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

sqs_client = boto3.client("sqs")


def lambda_handler(event: dict, context: object) -> dict:
    """Triggered by API queries against the knowledge base.

    1. Forwards the request payload to the SQS queue specified by
       ``SUMMARY_QUEUE_URL``.

    Returns whether the request was queued successfully.
    """

    queue_url = os.environ.get("SUMMARY_QUEUE_URL")
    if not queue_url:
        logger.error("SUMMARY_QUEUE_URL not configured")
        return {"error": "SUMMARY_QUEUE_URL not configured"}

    try:
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(event),
        )
    except ClientError as exc:
        logger.error("Failed to queue summary request: %s", exc)
        return {"error": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected send error
        logger.exception("Unexpected error queueing summary request")
        return {"error": str(exc)}
    return {"queued": True}
