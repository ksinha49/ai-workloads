# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Render stored prompts and forward them to the router service."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any, Dict

import boto3
from boto3.dynamodb.conditions import Attr
from common_utils import configure_logger

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

PROMPT_LIBRARY_TABLE = os.environ.get("PROMPT_LIBRARY_TABLE")
ROUTER_ENDPOINT = os.environ.get("ROUTER_ENDPOINT")

_dynamo = boto3.resource("dynamodb")
_table = _dynamo.Table(PROMPT_LIBRARY_TABLE)


# ─── Helper Functions ──────────────────────────────────────────────────────

def _substitute_variables(template: str, variables: Dict[str, Any]) -> str:
    """Return ``template`` with ``variables`` substituted using ``str.format``."""
    try:
        return template.format(**variables)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Missing variable: {missing}") from None


def _get_latest_version(prompt_id: str) -> Dict[str, Any]:
    """Return the most recent prompt item for ``prompt_id``."""
    resp = _table.scan(FilterExpression=Attr("prompt_id").eq(prompt_id))
    items = resp.get("Items", [])
    if not items:
        raise KeyError(f"Prompt '{prompt_id}' not found")
    items.sort(key=lambda x: int(x.get("version", 0)), reverse=True)
    return items[0]


def _fetch_prompt(prompt_id: str, version: str | None = None) -> Dict[str, Any]:
    if version:
        key = {"id": f"{prompt_id}:{version}"}
        item = _table.get_item(Key=key).get("Item")
        if item:
            return item
    return _get_latest_version(prompt_id)


def _call_router(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send ``payload`` to the router endpoint and return JSON response."""
    req = urllib.request.Request(
        ROUTER_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"response": body.decode("utf-8")}


def _process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    prompt_id = event.get("prompt_id")
    if not prompt_id:
        return {"error": "prompt_id missing"}

    version = event.get("version")
    try:
        item = _fetch_prompt(prompt_id, version)
    except Exception as exc:  # pragma: no cover - runtime issues
        logger.exception("Error fetching prompt")
        return {"error": str(exc)}

    template = item.get("template", "")
    variables = event.get("variables", {})
    rendered = _substitute_variables(template, variables)

    payload = dict(event)
    payload["prompt"] = rendered
    payload.pop("variables", None)
    payload.pop("prompt_id", None)
    payload.pop("version", None)

    try:
        return _call_router(payload)
    except Exception as exc:  # pragma: no cover - network failure
        logger.exception("Router request failed")
        return {"error": str(exc)}


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    """Entry point supporting SQS events."""
    if isinstance(event, dict) and "Records" in event:
        return [_process_event(json.loads(r.get("body", "{}"))) for r in event["Records"]]
    return _process_event(event)

