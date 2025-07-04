"""Worker Lambda processing queued summarization requests."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import boto3
from common_utils import configure_logger
from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

lambda_client = boto3.client("lambda")
sf_client = boto3.client("stepfunctions")

SUMMARY_FUNCTION_ARN = (
    get_config("RAG_SUMMARY_FUNCTION_ARN") or os.environ.get("RAG_SUMMARY_FUNCTION_ARN")
)
PROMPT_ENGINE_ENDPOINT = get_config("PROMPT_ENGINE_ENDPOINT") or os.environ.get(
    "PROMPT_ENGINE_ENDPOINT"
)


def _process_record(record: Dict[str, Any]) -> None:
    body = json.loads(record.get("body", "{}"))
    token = body.get("token")
    payload = {
        "query": body.get("query"),
        "retrieve_params": body.get("retrieve_params"),
        "router_params": body.get("router_params"),
        "llm_params": body.get("llm_params"),
    }
    if PROMPT_ENGINE_ENDPOINT and body.get("prompt_id"):
        engine_payload = {"prompt_id": body.get("prompt_id")}
        if "variables" in body:
            engine_payload["variables"] = body.get("variables")
        try:
            import httpx

            # The prompt engine renders the template and forwards it to the
            # router service.  The response is ignored here because
            # `body["query"]` is passed unchanged to ``RAG_SUMMARY_FUNCTION_ARN``
            # below.
            httpx.post(PROMPT_ENGINE_ENDPOINT, json=engine_payload).raise_for_status()
        except Exception:  # pragma: no cover - network failure
            logger.exception("Prompt engine request failed")
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
