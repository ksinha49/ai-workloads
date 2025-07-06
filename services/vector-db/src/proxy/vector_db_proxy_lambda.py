"""Dispatch vector DB operations to the configured backend."""

from __future__ import annotations

import os
from typing import Any, Dict

from common_utils import configure_logger

from .. import milvus_handler_lambda as milvus_handler
from .. import elastic_search_handler_lambda as es_handler

logger = configure_logger(__name__)

DEFAULT_VECTOR_DB_BACKEND = os.environ.get("DEFAULT_VECTOR_DB_BACKEND", "milvus")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    backend = (event.get("storage_mode") or DEFAULT_VECTOR_DB_BACKEND).lower()
    if backend.startswith("es") or backend.startswith("elastic"):
        logger.info("Routing operation '%s' to Elasticsearch", event.get("operation"))
        return es_handler.lambda_handler(event, context)
    logger.info("Routing operation '%s' to Milvus", event.get("operation"))
    return milvus_handler.lambda_handler(event, context)
