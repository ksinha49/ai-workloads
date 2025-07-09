"""Anonymize text by masking, pseudonymizing or tokenizing entities."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Tuple

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
CONF_THRESHOLD = float(
    get_config("PRESIDIO_CONFIDENCE")
    or get_config("ANON_CONFIDENCE")
    or os.environ.get("PRESIDIO_CONFIDENCE")
    or os.environ.get("ANON_CONFIDENCE", "0")
)

USE_PRESIDIO = (
    (get_config("USE_PRESIDIO_ANON") or os.environ.get("USE_PRESIDIO_ANON"))
    in {"1", "true", "True"}
)

try:  # pragma: no cover - optional dependency
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig, RecognizerResult
    _PRESIDIO_ENGINE = AnonymizerEngine()
except Exception:  # pragma: no cover - allow import without dependency
    USE_PRESIDIO = False
    _PRESIDIO_ENGINE = None

_fake = Faker()


def _normalize_entities(text: str, entities: Iterable[Any]) -> List[Dict[str, Any]]:
    """Return a normalized list of entity dictionaries."""

    norm: List[Dict[str, Any]] = []
    for ent in entities:
        if hasattr(ent, "to_dict"):
            ent = ent.to_dict()
        elif not isinstance(ent, dict):
            ent = {
                "start": getattr(ent, "start", 0),
                "end": getattr(ent, "end", 0),
                "score": getattr(ent, "score", None),
                "type": getattr(ent, "entity_type", getattr(ent, "type", "")),
            }

        start = int(ent.get("start", 0))
        end = int(ent.get("end", start))
        typ = ent.get("type") or ent.get("entity_type", "")
        score = ent.get("score")
        chunk = text[start:end] if not ent.get("text") else ent.get("text")
        norm.append({"text": chunk, "type": typ, "start": start, "end": end, "score": score})

    return norm


def _mask(ent: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    typ = ent.get("type", "ENTITY")
    replacement = f"[{typ}]"
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


def _presidio_apply(text: str, entities: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Mask text using the presidio anonymizer."""

    if not _PRESIDIO_ENGINE:
        return text, []

    results = [
        RecognizerResult(ent["type"], ent["start"], ent["end"], ent.get("score", 1.0))
        for ent in entities
    ]

    ops: Dict[str, OperatorConfig] = {}
    for ent in entities:
        if ent["type"] not in ops:
            ops[ent["type"]] = OperatorConfig("replace", {"new_value": f"[{ent['type']}]"})

    try:
        res = _PRESIDIO_ENGINE.anonymize(text=text, analyzer_results=results, operators=ops)
    except Exception:  # pragma: no cover - optional dependency failure
        logger.exception("Presidio anonymization failed")
        return text, []

    repls = [
        {
            "type": item["entity_type"],
            "start": item["start"],
            "end": item["end"],
            "replacement": item["text"],
        }
        for item in res.items
    ]
    return res.text, repls


def _apply(text: str, entities: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    def _conf(ent: Dict[str, Any]) -> float:
        score = ent.get("score")
        if score is None:
            return 1.0
        return float(score)

    filtered = [e for e in entities if _conf(e) >= CONF_THRESHOLD]
    if not filtered:
        return text, []

    if MODE == "mask" and USE_PRESIDIO:
        anon_text, replacements = _presidio_apply(text, filtered)
        if replacements:
            return anon_text, replacements

    parts: List[str] = []
    replacements: List[Dict[str, Any]] = []
    last = 0
    for ent in sorted(filtered, key=lambda e: e.get("start", 0)):
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
    entities = _normalize_entities(text, event.get("entities", []))
    if not text or not entities:
        return {"text": text}

    anon_text, replacements = _apply(text, entities)
    body: Dict[str, Any] = {"text": anon_text}
    if MODE in {"pseudo", "token"}:
        body["replacements"] = replacements
    return body
