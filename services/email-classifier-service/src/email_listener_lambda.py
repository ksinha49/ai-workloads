"""Email Listener Lambda

Fetches new messages from the configured mailbox and forwards them to the
rules engine for classification. Filtering is delegated entirely to the
rules engine.
"""

from __future__ import annotations

import os
import boto3
from botocore.exceptions import ClientError
from common_utils import configure_logger, lambda_response

logger = configure_logger(__name__)
_sqs = boto3.client("sqs")

INBOX_QUEUE_URL = os.environ.get("INBOX_QUEUE_URL", "")
RULES_QUEUE_URL = os.environ.get("RULES_QUEUE_URL", "")


def lambda_handler(event, context):  # pragma: no cover - simple pass-through
    """Receive an email event and forward it to the rules queue."""
    logger.info("Received email event", extra={"event": event})
    if not RULES_QUEUE_URL:
        logger.error("RULES_QUEUE_URL not configured")
        return lambda_response(500, "Rules queue not configured")
    try:
        _sqs.send_message(QueueUrl=RULES_QUEUE_URL, MessageBody=event["body"])
    except ClientError as exc:
        logger.exception("Failed to forward email", exc_info=exc)
        return lambda_response(500, "forward failed")
    return lambda_response(200, "queued")
