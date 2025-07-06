"""Scheduled cleanup of ephemeral Milvus collections."""

import datetime
import os
import boto3
from typing import Any, Dict

from common_utils import configure_logger, MilvusClient

logger = configure_logger(__name__)

ddb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("EPHEMERAL_TABLE")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    if not TABLE_NAME:
        logger.error("EPHEMERAL_TABLE not configured")
        return {"dropped": 0}
    table = ddb.Table(TABLE_NAME)
    now = int(datetime.datetime.utcnow().timestamp())
    resp = table.scan()
    dropped = 0
    for item in resp.get("Items", []):
        expires = int(item.get("expires_at", 0))
        name = item.get("collection_name")
        if expires and expires < now and name:
            try:
                MilvusClient(collection_name=name).drop_collection()
                table.delete_item(Key={"collection_name": name})
                dropped += 1
            except Exception:
                logger.exception("Failed to drop collection %s", name)
    logger.info("Dropped %s collections", dropped)
    return {"dropped": dropped}
