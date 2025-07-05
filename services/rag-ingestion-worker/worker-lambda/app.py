"""Worker Lambda triggering the RAG ingestion workflow from SQS messages."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import boto3
from common_utils import configure_logger
from common_utils.get_ssm import get_config

try:
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - allow missing botocore
    BotoCoreError = ClientError = Exception  # type: ignore

logger = configure_logger(__name__)

sqs_client = boto3.client("sqs")
sf_client = boto3.client("stepfunctions")

STATE_MACHINE_ARN = get_config("STATE_MACHINE_ARN") or os.environ.get("STATE_MACHINE_ARN")
QUEUE_URL = get_config("QUEUE_URL") or os.environ.get("QUEUE_URL")


def _process_record(record: Dict[str, Any]) -> None:
    body = json.loads(record.get("body", record.get("Body", "{}")))
    try:
        sf_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(body),
        )
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - runtime issues
        logger.exception("Failed to start ingestion state machine")
        raise exc


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records")
    triggered_by_sqs = records is not None
    if not records and QUEUE_URL:
        resp = sqs_client.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=10)
        records = resp.get("Messages", [])

    failures = []
    for record in records or []:
        try:
            _process_record(record)
            if "ReceiptHandle" in record and QUEUE_URL:
                sqs_client.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=record["ReceiptHandle"])
        except Exception:  # pragma: no cover - runtime issues
            logger.exception("Error processing record")
            if triggered_by_sqs:
                mid = record.get("messageId") or record.get("MessageId")
                if mid:
                    failures.append({"itemIdentifier": mid})
            else:
                raise

    response = {"statusCode": 200}
    if triggered_by_sqs:
        response["batchItemFailures"] = failures
    return response
