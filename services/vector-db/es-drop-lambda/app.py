# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Drop an Elasticsearch index."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict

from common_utils import ElasticsearchClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = ElasticsearchClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to delete the Elasticsearch index.

    1. Calls the client ``drop_index`` method to remove the index entirely.

    Returns ``{"dropped": True}`` when successful.
    """

    client.drop_index()
    return {"dropped": True}
