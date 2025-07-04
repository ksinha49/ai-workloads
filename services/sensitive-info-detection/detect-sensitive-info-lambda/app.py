# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""
Module: app.py
Description:
  Detect PII entities in text using ML models and regex fallbacks.


Version: 1.0.0
Created: 2025-05-05
Last Modified: 2025-06-28
Modified By: Koushik Sinha
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

from common_utils import configure_logger
from common_utils.get_ssm import get_config
from common_utils.ner_models import load_ner_model

# ─── Logging Configuration ────────────────────────────────────────────────────
logger = configure_logger(__name__)

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

_MODEL: Tuple[str, Any] | None = None
_MEDICAL_MODEL: Tuple[str, Any] | None = None
_LEGAL_MODEL: Tuple[str, Any] | None = None


def _load_model() -> Tuple[str, Any] | None:
    """Return the default NER model."""

    global _MODEL
    if _MODEL is None:
        _MODEL = load_ner_model("SPACY_MODEL", "HF_MODEL")
    return _MODEL


def _load_medical_model() -> Tuple[str, Any] | None:
    """Return the NER model for the Medical domain."""

    global _MEDICAL_MODEL
    if _MEDICAL_MODEL is None:
        _MEDICAL_MODEL = load_ner_model("MEDICAL_MODEL", "MEDICAL_MODEL")
    return _MEDICAL_MODEL


def _load_legal_model() -> Tuple[str, Any] | None:
    """Return the NER model for the Legal domain."""

    global _LEGAL_MODEL
    if _LEGAL_MODEL is None:
        _LEGAL_MODEL = load_ner_model("LEGAL_MODEL", "LEGAL_MODEL")
    return _LEGAL_MODEL


_DEFAULT_REGEX_PATTERNS = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
}

_DEFAULT_LEGAL_REGEX_PATTERNS = {
    "CASE_NUMBER": r"\b\d{2}-\d{5}\b",
}

_REGEX_PATTERNS: Dict[str, str] = {}
_LEGAL_REGEX_PATTERNS: Dict[str, str] = {}


def _load_regex_patterns() -> None:
    """Load regex patterns from environment variables."""

    global _REGEX_PATTERNS, _LEGAL_REGEX_PATTERNS
    _REGEX_PATTERNS = dict(_DEFAULT_REGEX_PATTERNS)
    _LEGAL_REGEX_PATTERNS = dict(_DEFAULT_LEGAL_REGEX_PATTERNS)

    env_patterns = get_config("REGEX_PATTERNS") or os.environ.get("REGEX_PATTERNS")
    if env_patterns:
        try:
            _REGEX_PATTERNS.update(json.loads(env_patterns))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Invalid REGEX_PATTERNS: %s", exc)

    env_legal = get_config("LEGAL_REGEX_PATTERNS") or os.environ.get("LEGAL_REGEX_PATTERNS")
    if env_legal:
        try:
            _LEGAL_REGEX_PATTERNS.update(json.loads(env_legal))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Invalid LEGAL_REGEX_PATTERNS: %s", exc)


_load_regex_patterns()


def _regex_entities(text: str, patterns: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
    """Return regex-based PII matches."""

    if patterns is None:
        patterns = _REGEX_PATTERNS

    matches: List[Dict[str, Any]] = []
    for typ, pattern in patterns.items():
        try:
            for match in re.finditer(pattern, text):
                matches.append(
                    {
                        "text": match.group(0),
                        "type": typ,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        except re.error as exc:  # pragma: no cover - runtime safety
            logger.exception("Invalid regex pattern for %s: %s", typ, exc)
    return matches


def _ml_entities(text: str, model_info: Tuple[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Extract entities using the configured ML model."""

    if model_info is None:
        model_info = _load_model()
    if model_info is None:
        return []

    kind, model = model_info
    entities: List[Dict[str, Any]] = []
    try:
        if kind == "spacy":
            doc = model(text)
            for ent in doc.ents:
                entities.append(
                    {
                        "text": ent.text,
                        "type": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                )
        else:
            results = model(text)
            for ent in results:
                entities.append(
                    {
                        "text": ent.get("word"),
                        "type": ent.get("entity_group"),
                        "start": ent.get("start"),
                        "end": ent.get("end"),
                    }
                )
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("ML entity extraction failed: %s", exc)
        return []
    return entities


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Return detected PII entities from the input text."""
    try:
        text = event.get("text", "")
        if not isinstance(text, str):
            logger.error("Invalid text input: %r", text)
            return {"entities": []}

        domain = (event.get("domain") or event.get("classification") or "").title()

        regex_patterns = _REGEX_PATTERNS
        model_info: Tuple[str, Any] | None = None

        if domain == "Medical":
            model_info = _load_medical_model()
        elif domain == "Legal":
            model_info = _load_legal_model()
            regex_patterns = {**_REGEX_PATTERNS, **_LEGAL_REGEX_PATTERNS}
        else:
            model_info = _load_model()

        entities = _regex_entities(text, regex_patterns) + _ml_entities(text, model_info)
        return {"entities": entities}
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("lambda_handler failed: %s", exc)
        return {"entities": []}
