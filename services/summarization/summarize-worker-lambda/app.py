"""Worker Lambda processing queued summarization requests."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import boto3
from common_utils import configure_logger

logger = configure_logger(__name__)

lambda_client = boto3.client("lambda")
sf_client = boto3.client("stepfunctions")

SUMMARY_FUNCTION_ARN = os.environ.get("RAG_SUMMARY_FUNCTION_ARN")


def _process_record(record: Dict[str, Any]) -> None:
    body = json.loads(record.get("body", "{}"))
    token = body.get("token")
    payload = {
        "query": body.get("query"),
        "retrieve_params": body.get("retrieve_params"),
        "router_params": body.get("router_params"),
        "llm_params": body.get("llm_params"),
    }
    if body.get("collection_name") is None:
        logger.error("collection_name missing from message")
        if token:
            sf_client.send_task_failure(
                taskToken=token,
                error="WorkerError",
                cause="collection_name missing",
            )
        return
    payload["collection_name"] = body.get("collection_name")
    try:
        resp = lambda_client.invoke(
            FunctionName=SUMMARY_FUNCTION_ARN,
            Payload=json.dumps(payload).encode("utf-8"),
        )
        summary = json.loads(resp["Payload"].read()).get(
            "summary", {}
        ).get("choices", [{}])[0].get("message", {}).get("content", "")
        sf_client.send_task_success(
            taskToken=token,
            output=json.dumps({"summary": summary, "Title": body.get("Title")}),
        )
    except Exception as exc:  # pragma: no cover - runtime issues
        logger.exception("Error processing summarization request")
        if token:
            sf_client.send_task_failure(
                taskToken=token,
                error="WorkerError",
                cause=str(exc),
            )


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    for record in event.get("Records", []):
        _process_record(record)
    return {"statusCode": 200}
