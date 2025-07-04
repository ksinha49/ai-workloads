"""Helpers for loading spaCy or HuggingFace NER models."""

from __future__ import annotations

import os
from typing import Any, Tuple

from common_utils import configure_logger
from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

# Cache keyed by (spacy_env, hf_env)
_MODEL_CACHE: dict[tuple[str, str], Tuple[str, Any] | None] = {}


def load_ner_model(spacy_env: str, hf_env: str, default: str = "en_core_web_sm") -> Tuple[str, Any] | None:
    """Load and cache an NER model specified by environment variables."""

    key = (spacy_env, hf_env)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    library = (get_config("NER_LIBRARY") or os.environ.get("NER_LIBRARY", "spacy")).lower()
    if library == "spacy":
        try:  # pragma: no cover - optional dependency
            import spacy  # type: ignore

            model_name = (
                get_config(spacy_env)
                or os.environ.get(spacy_env)
                or get_config("SPACY_MODEL")
                or os.environ.get("SPACY_MODEL", default)
            )
            _MODEL_CACHE[key] = ("spacy", spacy.load(model_name))
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to load spaCy model: %s", exc)
            _MODEL_CACHE[key] = None
    else:
        try:  # pragma: no cover - optional dependency
            from transformers import pipeline  # type: ignore

            model_name = (
                get_config(hf_env)
                or os.environ.get(hf_env)
                or get_config("HF_MODEL")
                or os.environ.get("HF_MODEL", "dslim/bert-base-NER")
            )
            _MODEL_CACHE[key] = (
                "hf",
                pipeline("ner", model=model_name, aggregation_strategy="simple"),
            )
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Failed to load HuggingFace model: %s", exc)
            _MODEL_CACHE[key] = None

    return _MODEL_CACHE[key]
