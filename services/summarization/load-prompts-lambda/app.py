from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict

import httpx
from common_utils import configure_logger

logger = configure_logger(__name__)

PROMPT_ENGINE_ENDPOINT = os.environ.get("PROMPT_ENGINE_ENDPOINT")

SYSTEM_WORKFLOW_ID = os.environ.get("SYSTEM_WORKFLOW_ID", "sys")


def _process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    workflow_id = event.get("workflow_id")
    if not workflow_id:
        return {"error": "workflow_id missing"}
    try:
        resp = httpx.post(PROMPT_ENGINE_ENDPOINT, json={"workflow_id": workflow_id})
        resp.raise_for_status()

        prompts = resp.json()

        sys_resp = httpx.post(PROMPT_ENGINE_ENDPOINT, json={"workflow_id": SYSTEM_WORKFLOW_ID})
        sys_resp.raise_for_status()
        sys_items = sys_resp.json()
        system_prompt = ""
        if sys_items:
            system_prompt = sys_items[0].get("template", sys_items[0].get("system_prompt", ""))

        return {"prompts": prompts, "llm_params": {"system_prompt": system_prompt}}

    except Exception as exc:  # pragma: no cover - network failure
        logger.exception("Prompt engine request failed")
        return {"error": str(exc)}


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    if isinstance(event, dict) and "Records" in event:
        return [_process_event(json.loads(r.get("body", "{}"))) for r in event["Records"]]
    return _process_event(event)
