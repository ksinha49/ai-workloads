"""Lightweight helper to extract named entities from text."""

from __future__ import annotations

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

import os
import re
from typing import Iterable, List

from common_utils import configure_logger

logger = configure_logger(__name__)

_NLP = None


def _load_spacy():
    """Load and cache a spaCy model if available.

    The model name is taken from the ``SPACY_MODEL`` environment variable and
    defaults to ``"en_core_web_sm"``.  If spaCy or the requested model cannot be
    loaded, ``None`` is returned.  Subsequent calls return the cached model or
    ``None`` without re-importing spaCy.
    """

    global _NLP
    if _NLP is not None:
        return _NLP
    try:  # pragma: no cover - optional dependency
        import spacy  # type: ignore

        model = os.environ.get("SPACY_MODEL", "en_core_web_sm")
        _NLP = spacy.load(model)
    except Exception:
        _NLP = None
    return _NLP


def extract_entities(text: str) -> List[str]:
    """Return a list of entities detected in ``text``.

    When spaCy is available, the configured model is used. Otherwise a simple
    fallback based on capitalised words is applied.
    """

    nlp = _load_spacy()
    if nlp is not None:
        doc = nlp(text)
        return [f"{ent.label_}:{ent.text}" for ent in doc.ents]

    # very naive fallback – sequences of capitalised words
    pattern = r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\b"
    found = re.findall(pattern, text)
    # remove duplicates while preserving order
    seen = set()
    entities: List[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            entities.append(item)
    return entities
