# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Detect PII entities in text using ML models and regex fallbacks."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Tuple

from common_utils import configure_logger

logger = configure_logger(__name__)

_MODEL: Tuple[str, Any] | None = None


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


_REGEX_PATTERNS = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
}


def _regex_entities(text: str) -> List[Dict[str, Any]]:
    """Return regex-based PII matches."""

    matches: List[Dict[str, Any]] = []
    for typ, pattern in _REGEX_PATTERNS.items():
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


def _ml_entities(text: str) -> List[Dict[str, Any]]:
    """Extract entities using the configured ML model."""

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
    entities = _regex_entities(text) + _ml_entities(text)
    return {"entities": entities}
