"""Worker Lambda invoked by the summarization state machine."""
from __future__ import annotations

import json
import os
import logging
from typing import Any, Dict

import boto3
import httpx
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass
from common_utils import configure_logger
from common_utils.get_ssm import get_config
try:
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - allow missing botocore
    BotoCoreError = ClientError = Exception  # type: ignore

logger = configure_logger(__name__)

lambda_client = boto3.client("lambda")
sf_client = boto3.client("stepfunctions")

SUMMARY_FUNCTION_ARN = (
    get_config("RAG_SUMMARY_FUNCTION_ARN")
    or os.environ.get("RAG_SUMMARY_FUNCTION_ARN")
)
PROMPT_ENGINE_ENDPOINT = (
    get_config("PROMPT_ENGINE_ENDPOINT") or os.environ.get("PROMPT_ENGINE_ENDPOINT")
)


def _invoke_summary(body: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "collection_name": body.get("collection_name"),
        "query": body.get("query"),
        "file_guid": body.get("file_guid"),
        "document_id": body.get("document_id"),
    }
    try:
        resp = lambda_client.invoke(
            FunctionName=SUMMARY_FUNCTION_ARN,
            Payload=json.dumps(payload).encode(),
        )
        data = json.load(resp["Payload"])
    except (ClientError, BotoCoreError, json.JSONDecodeError) as exc:
        logger.exception("Failed to invoke summary function")
        return {"error": str(exc)}
    if "error" in data:
        return {"error": data.get("error")}

    summary = data.get("result")
    if summary is None:
        try:
            summary = data["summary"]["choices"][0]["message"]["content"]
        except Exception:
            summary = ""
    return {"summary": summary}


def _process_record(record: Dict[str, Any]) -> Dict[str, Any]:
    body = json.loads(record.get("body", record.get("Body", "{}")))
    token = body.get("token")
    if body.get("prompt_id") and PROMPT_ENGINE_ENDPOINT:
        try:
            resp = httpx.post(
                PROMPT_ENGINE_ENDPOINT,
                json={"prompt_id": body.get("prompt_id"), "variables": body.get("variables")},
            )
            resp.raise_for_status()
        except HTTPError:  # pragma: no cover - log and continue
            logger.exception("Failed to render prompt")

    result = _invoke_summary(body)
    result.update({"file_guid": body.get("file_guid"), "document_id": body.get("document_id")})
    if token:
        try:
            sf_client.send_task_success(taskToken=token, output=json.dumps(result))
        except ClientError:
            logger.exception("Failed to send task success")
            result.setdefault("error", "Failed to send task success")
    return result


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records")
    if not records:
        _process_record(event)
    else:
        for rec in records:
            _process_record(rec)
    return {"statusCode": 200}
