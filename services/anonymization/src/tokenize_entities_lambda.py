"""Tokenize entities and store mappings in DynamoDB."""

from __future__ import annotations

import hashlib
import os
import uuid
from typing import Any, Dict

import boto3
from common_utils import configure_logger
try:
    from botocore.exceptions import BotoCoreError, ClientError
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal env
    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass
from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

TABLE_NAME = get_config("TOKEN_TABLE") or os.environ.get("TOKEN_TABLE")
PREFIX = get_config("TOKEN_PREFIX") or os.environ.get("TOKEN_PREFIX", "ent_")
SALT = get_config("TOKEN_SALT") or os.environ.get("TOKEN_SALT", "")

_dynamo = boto3.resource("dynamodb")
_table = _dynamo.Table(TABLE_NAME)


def _generate_token(entity: str) -> str:
    """Return a token for ``entity`` using SALT or a random UUID."""
    if SALT:
        digest = hashlib.blake2b(
            (SALT + entity).encode("utf-8"), digest_size=4
        ).hexdigest()
    else:
        digest = uuid.uuid4().hex[:8]
    return PREFIX + digest


def _lookup_token(entity: str, etype: str, domain: str) -> str | None:
    """Return stored token if a mapping exists."""
    try:
        resp = _table.query(
            IndexName="DomainIndex",
            KeyConditionExpression="entity = :e AND domain = :d",
            FilterExpression="entity_type = :t",
            ExpressionAttributeValues={":e": entity, ":d": domain, ":t": etype},
        )
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - runtime safeguard
        logger.exception("DynamoDB query failed")
        return None
    items = resp.get("Items", [])
    if items:
        return items[0].get("token")
    return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    entity = event.get("entity")
    etype = event.get("entity_type")
    domain = event.get("domain", "")
    if not entity or not etype:
        return {"error": "entity and entity_type required"}

    token = _lookup_token(entity, etype, domain)
    if token:
        return {"token": token}

    token = _generate_token(entity)
    item = {
        "token": token,
        "entity": entity,
        "entity_type": etype,
        "domain": domain,
    }
    try:
        _table.put_item(Item=item)
    except (ClientError, BotoCoreError) as exc:  # pragma: no cover - runtime safety
        logger.exception("Failed to store mapping")
        return {"error": "dynamo failure"}
    return {"token": token}
