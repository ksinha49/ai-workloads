"""Helper to load secrets from AWS Secrets Manager."""

from __future__ import annotations

import os
from typing import Optional

import boto3
try:  # pragma: no cover - optional dependency
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - allow import without botocore
    BotoCoreError = ClientError = Exception  # type: ignore

from common_utils import configure_logger

logger = configure_logger(__name__)

_secrets_client = boto3.client("secretsmanager")

# Cache so a Lambda invocation only fetches each secret once
_SECRET_CACHE: dict[str, str] = {}


def get_secret(name: str) -> Optional[str]:
    """Return the value of secret ``name`` from Secrets Manager.

    The secret name can be overridden by setting an environment variable
    ``<name>_SECRET_NAME`` (for example ``COHERE_SECRET_NAME``). The first
    request fetches the value from AWS and caches it for subsequent calls.
    """
    secret_name = os.environ.get(f"{name}_SECRET_NAME", name)
    if secret_name in _SECRET_CACHE:
        return _SECRET_CACHE[secret_name]
    try:
        resp = _secrets_client.get_secret_value(SecretId=secret_name)
        value = resp.get("SecretString")
        if value is None:
            value = resp.get("SecretBinary", b"").decode("utf-8")
        _SECRET_CACHE[secret_name] = value
        logger.info("Loaded secret %s", secret_name)
        return value
    except (BotoCoreError, ClientError) as exc:
        logger.error("Error retrieving secret %s: %s", secret_name, exc)
        raise
