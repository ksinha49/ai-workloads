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
import os
import re
from dataclasses import asdict
from typing import Any, Dict, List

from common_utils import configure_logger
from common_utils.get_ssm import get_config
from models import DetectedEntity, DetectPiiResponse

# Configuration values for Presidio
LANGUAGE = (
    get_config("PRESIDIO_LANGUAGE")
    or os.environ.get("PRESIDIO_LANGUAGE", "en")
)

# ─── Logging Configuration ────────────────────────────────────────────────────
logger = configure_logger(__name__)

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

_ENGINE: "AnalyzerEngine" | None = None
_MEDICAL_ENGINE: "AnalyzerEngine" | None = None
_LEGAL_ENGINE: "AnalyzerEngine" | None = None


def _build_engine(spacy_env: str, hf_env: str) -> "AnalyzerEngine" | None:
    """Return an AnalyzerEngine using spaCy or HF based on configuration."""

    library = (
        get_config("NER_LIBRARY") or os.environ.get("NER_LIBRARY", "spacy")
    ).lower()
    if library.startswith("hf"):
        model_name = (
            get_config(hf_env)
            or os.environ.get(hf_env)
            or get_config("HF_MODEL")
            or os.environ.get("HF_MODEL", "dslim/bert-base-NER")
        )
        conf = {
            "nlp_engine_name": "transformers",
            "models": [{"lang_code": LANGUAGE, "model_name": model_name}],
        }
    else:
        model_name = (
            get_config(spacy_env)
            or os.environ.get(spacy_env)
            or get_config("SPACY_MODEL")
            or os.environ.get("SPACY_MODEL", "en_core_web_sm")
        )
        conf = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": LANGUAGE, "model_name": model_name}],
        }

    try:  # pragma: no cover - runtime safety
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        provider = NlpEngineProvider(nlp_configuration=conf)
        nlp_engine = provider.create_engine()
        return AnalyzerEngine(
            nlp_engine=nlp_engine, supported_languages=[LANGUAGE]
        )
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Failed to load AnalyzerEngine: %s", exc)
        return None


def _load_model() -> "AnalyzerEngine" | None:
    """Return the default AnalyzerEngine."""

    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _build_engine("SPACY_MODEL", "HF_MODEL")
    return _ENGINE


def _load_medical_model() -> "AnalyzerEngine" | None:
    """Return the AnalyzerEngine for the Medical domain."""

    global _MEDICAL_ENGINE
    if _MEDICAL_ENGINE is None:
        _MEDICAL_ENGINE = _build_engine("MEDICAL_MODEL", "MEDICAL_MODEL")
    return _MEDICAL_ENGINE


def _load_legal_model() -> "AnalyzerEngine" | None:
    """Return the AnalyzerEngine for the Legal domain."""

    global _LEGAL_ENGINE
    if _LEGAL_ENGINE is None:
        _LEGAL_ENGINE = _build_engine("LEGAL_MODEL", "LEGAL_MODEL")
    return _LEGAL_ENGINE


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


def _ml_entities(text: str, engine: "AnalyzerEngine" | None = None) -> List[Dict[str, Any]]:
    """Extract entities using the configured AnalyzerEngine."""

    if engine is None:
        engine = _load_model()
    if engine is None:
        return []

    try:
        results = engine.analyze(text=text, language=LANGUAGE)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("ML entity extraction failed: %s", exc)
        return []

    entities: List[Dict[str, Any]] = []
    for res in results:
        entities.append(
            {
                "text": text[res.start : res.end],
                "type": res.entity_type,
                "start": res.start,
                "end": res.end,
            }
        )
    return entities


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Return detected PII entities from the input text."""
    try:
        text = event.get("text", "")
        if not isinstance(text, str):
            logger.error("Invalid text input: %r", text)
            return asdict(DetectPiiResponse(entities=[]))

        domain = (event.get("domain") or event.get("classification") or "").title()

        regex_patterns = _REGEX_PATTERNS
        engine: "AnalyzerEngine" | None = None

        if domain == "Medical":
            engine = _load_medical_model()
        elif domain == "Legal":
            engine = _load_legal_model()
            regex_patterns = {**_REGEX_PATTERNS, **_LEGAL_REGEX_PATTERNS}
        else:
            engine = _load_model()

        entities = _regex_entities(text, regex_patterns) + _ml_entities(text, engine)
        ent_objs = [
            DetectedEntity(
                text=e.get("text", ""),
                type=e.get("type", ""),
                start=int(e.get("start", 0)),
                end=int(e.get("end", 0)),
                score=(lambda s: float(s) if s is not None else None)(e.get("score")),
            )
            for e in entities
        ]
        return asdict(DetectPiiResponse(entities=ent_objs))
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("lambda_handler failed: %s", exc)
        return asdict(DetectPiiResponse(entities=[]))
