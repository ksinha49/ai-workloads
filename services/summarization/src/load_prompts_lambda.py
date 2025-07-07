"""Fetch workflow prompts from the prompt engine."""
from __future__ import annotations

import os
import logging
import httpx
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass
from common_utils import configure_logger

logger = configure_logger(__name__)

PROMPT_ENGINE_ENDPOINT = os.environ.get("PROMPT_ENGINE_ENDPOINT")
SYSTEM_WORKFLOW_ID = os.environ.get("SYSTEM_WORKFLOW_ID")


def lambda_handler(event: dict, context: object) -> dict:
    workflow_id = event.get("workflow_id")
    if not PROMPT_ENGINE_ENDPOINT or not workflow_id:
        return {"prompts": [], "llm_params": {}}

    try:
        resp = httpx.post(PROMPT_ENGINE_ENDPOINT, json={"workflow_id": workflow_id})
        resp.raise_for_status()
    except HTTPError as exc:
        logger.exception("Failed to fetch workflow prompts")
        return {"prompts": [], "error": str(exc)}
    prompts = resp.json()

    sys_prompt = None
    if SYSTEM_WORKFLOW_ID:
        try:
            sresp = httpx.post(
                PROMPT_ENGINE_ENDPOINT, json={"workflow_id": SYSTEM_WORKFLOW_ID}
            )
            sresp.raise_for_status()
        except HTTPError as exc:
            logger.exception("Failed to fetch system prompt")
            return {"prompts": [], "error": str(exc)}
        data = sresp.json()
        if data:
            sys_prompt = data[0].get("template")

    return {"prompts": prompts, "llm_params": {"system_prompt": sys_prompt}}
