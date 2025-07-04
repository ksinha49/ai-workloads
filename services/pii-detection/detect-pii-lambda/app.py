# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Detect PII entities in text using ML models and regex fallbacks."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

from common_utils import configure_logger

logger = configure_logger(__name__)

_MODEL: Tuple[str, Any] | None = None
_MEDICAL_MODEL: Tuple[str, Any] | None = None


def _load_model() -> Tuple[str, Any] | None:
    """Load either a spaCy or HuggingFace NER model based on env vars."""

    global _MODEL
    if _MODEL is not None:
        return _MODEL

    library = os.environ.get("NER_LIBRARY", "spacy").lower()
    if library == "spacy":
        try:  # pragma: no cover - optional dependency
            import spacy  # type: ignore

            model_name = os.environ.get("SPACY_MODEL", "en_core_web_sm")
            _MODEL = ("spacy", spacy.load(model_name))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to load spaCy model: %s", exc)
            _MODEL = None
    else:
        try:  # pragma: no cover - optional dependency
            from transformers import pipeline  # type: ignore

            model_name = os.environ.get("HF_MODEL", "dslim/bert-base-NER")
            _MODEL = (
                "hf",
                pipeline(
                    "ner",
                    model=model_name,
                    aggregation_strategy="simple",
                ),
            )
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to load HuggingFace model: %s", exc)
            _MODEL = None
    return _MODEL


def _load_medical_model() -> Tuple[str, Any] | None:
    """Load a PHI-specific model based on environment variables."""

    global _MEDICAL_MODEL
    if _MEDICAL_MODEL is not None:
        return _MEDICAL_MODEL

    library = os.environ.get("NER_LIBRARY", "spacy").lower()
    if library == "spacy":
        try:  # pragma: no cover - optional dependency
            import spacy  # type: ignore

            model_name = os.environ.get(
                "MEDICAL_MODEL", os.environ.get("SPACY_MODEL", "en_core_web_sm")
            )
            _MEDICAL_MODEL = ("spacy", spacy.load(model_name))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to load medical spaCy model: %s", exc)
            _MEDICAL_MODEL = None
    else:
        try:  # pragma: no cover - optional dependency
            from transformers import pipeline  # type: ignore

            model_name = os.environ.get(
                "MEDICAL_MODEL", os.environ.get("HF_MODEL", "dslim/bert-base-NER")
            )
            _MEDICAL_MODEL = (
                "hf",
                pipeline(
                    "ner",
                    model=model_name,
                    aggregation_strategy="simple",
                ),
            )
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to load medical HF model: %s", exc)
            _MEDICAL_MODEL = None
    return _MEDICAL_MODEL


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

    env_patterns = os.environ.get("REGEX_PATTERNS")
    if env_patterns:
        try:
            _REGEX_PATTERNS.update(json.loads(env_patterns))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Invalid REGEX_PATTERNS: %s", exc)

    env_legal = os.environ.get("LEGAL_REGEX_PATTERNS")
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
        for match in re.finditer(pattern, text):
            matches.append(
                {
                    "text": match.group(0),
                    "type": typ,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return matches


def _ml_entities(text: str, model_info: Tuple[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Extract entities using the configured ML model."""

    if model_info is None:
        model_info = _load_model()
    if model_info is None:
        return []

    kind, model = model_info
    entities: List[Dict[str, Any]] = []
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
    return entities


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Return detected PII entities from the input text."""

    text = event.get("text", "")
    domain = (event.get("domain") or event.get("classification") or "").title()

    regex_patterns = _REGEX_PATTERNS
    model_info: Tuple[str, Any] | None = None

    if domain == "Medical":
        model_info = _load_medical_model()
    else:
        model_info = _load_model()
        if domain == "Legal":
            regex_patterns = {**_REGEX_PATTERNS, **_LEGAL_REGEX_PATTERNS}

    entities = _regex_entities(text, regex_patterns) + _ml_entities(text, model_info)
    return {"entities": entities}
