"""Anonymize text by masking, pseudonymizing or tokenizing entities."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import httpx
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass
from faker import Faker
from common_utils import configure_logger
from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

MODE = (get_config("ANON_MODE") or os.environ.get("ANON_MODE", "mask")).lower()
TOKEN_API_URL = get_config("TOKEN_API_URL") or os.environ.get("TOKEN_API_URL", "")
TIMEOUT = float(get_config("ANON_TIMEOUT") or os.environ.get("ANON_TIMEOUT", "3"))

_fake = Faker()


def _mask(ent: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    text = ent.get("text", "")
    replacement = "*" * len(text)
    return replacement, {"replacement": replacement, **ent}


_FAKE_MAP = {
    "PERSON": _fake.name,
    "NAME": _fake.name,
    "ORG": _fake.company,
    "GPE": _fake.city,
    "LOCATION": _fake.city,
    "ADDRESS": _fake.address,
    "PHONE": _fake.phone_number,
    "EMAIL": _fake.email,
}


def _pseudonymize(ent: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    gen = _FAKE_MAP.get(ent.get("type"), _fake.word)
    try:
        replacement = gen()
    except (ValueError, RuntimeError):  # pragma: no cover - faker failure
        logger.exception("Faker generation failed")
        replacement = "[REMOVED]"
    return replacement, {"replacement": replacement, **ent}


def _tokenize(ent: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    if not TOKEN_API_URL:
        logger.error("TOKEN_API_URL not configured")
        return "[REMOVED]", {"replacement": "[REMOVED]", **ent}
    payload = {"entity": ent.get("text"), "entity_type": ent.get("type")}
    try:
        resp = httpx.post(TOKEN_API_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        token = resp.json().get("token", "[REMOVED]")
    except HTTPError:  # pragma: no cover - network failure
        logger.exception("Tokenization request failed")
        token = "[REMOVED]"
    return token, {"replacement": token, **ent}


_REPLACERS = {
    "mask": _mask,
    "pseudo": _pseudonymize,
    "token": _tokenize,
}


def _apply(text: str, entities: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    parts: List[str] = []
    replacements: List[Dict[str, Any]] = []
    last = 0
    for ent in sorted(entities, key=lambda e: e.get("start", 0)):
        start = int(ent.get("start", 0))
        end = int(ent.get("end", start))
        parts.append(text[last:start])
        repl, meta = _REPLACERS.get(MODE, _mask)(ent)
        parts.append(repl)
        replacements.append(meta)
        last = end
    parts.append(text[last:])
    return "".join(parts), replacements


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the anonymization Lambda."""

    text = event.get("text", "")
    entities = event.get("entities", [])
    if not text or not entities:
        return {"text": text}

    anon_text, replacements = _apply(text, entities)
    body: Dict[str, Any] = {"text": anon_text}
    if MODE in {"pseudo", "token"}:
        body["replacements"] = replacements
    return body
