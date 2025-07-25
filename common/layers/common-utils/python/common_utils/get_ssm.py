"""Shared helpers for retrieving SSM parameters and parsing S3 URIs."""

from typing import Optional, Tuple
import os
import boto3
try:  # pragma: no cover - optional dependency
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - allow import without botocore
    BotoCoreError = ClientError = Exception  # type: ignore

from common_utils import configure_logger

__author__ = "Koushik Sinha"
__version__ = "1.0.1"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)
_ssm_client = boto3.client("ssm")
try:
    from aws_lambda_powertools.utilities.parameters import SSMProvider
    from aws_lambda_powertools.utilities.parameters.caches.dynamodb import DynamoDBCache
except Exception:  # pragma: no cover - optional dependency
    SSMProvider = None  # type: ignore
    DynamoDBCache = None  # type: ignore

# Backwards compatible local cache for tests
_SSM_CACHE: dict[str, str] = {}

if SSMProvider:
    table_name = os.environ.get("SSM_CACHE_TABLE")
    cache = DynamoDBCache(table_name=table_name) if table_name else None
    _ssm_provider = SSMProvider(boto3_client=_ssm_client, cache=cache)
else:  # pragma: no cover - fallback when powertools is unavailable
    _ssm_provider = None
s3_client = boto3.client("s3")

def get_values_from_ssm(name: str, decrypt: bool = False) -> Optional[str]:
    """Retrieve a parameter value from SSM with optional decryption."""
    if name in _SSM_CACHE:
        return _SSM_CACHE[name]
    try:
        if _ssm_provider:
            value = _ssm_provider.get(name, decrypt=decrypt)
        else:  # pragma: no cover - fallback when powertools is unavailable
            resp = _ssm_client.get_parameter(Name=name, WithDecryption=decrypt)
            value = resp["Parameter"]["Value"]
        _SSM_CACHE[name] = value
        logger.info("Loaded parameter %s", name)
        return value
    except (BotoCoreError, ClientError, Exception) as exc:
        logger.error("Error retrieving parameter %s: %s", name, exc)
        raise

def get_environment_prefix() -> str:
    """Return the base SSM prefix for the current environment."""
    env = get_values_from_ssm("/parameters/aio/ameritasAI/SERVER_ENV")
    if not env:
        raise RuntimeError("SERVER_ENV not set in SSM")
    return f"/parameters/aio/ameritasAI/{env}"

def parse_s3_uri(s3_uri: str) -> Tuple[str, str]:
    """Split an ``s3://`` URI into bucket and key."""
    assert s3_uri.startswith("s3://"), "Invalid S3 URI"
    bucket, key = s3_uri[5:].split("/", 1)
    return bucket, key


def get_config(name: str, bucket: str | None = None, key: str | None = None,
               decrypt: bool = False) -> Optional[str]:
    """Return configuration ``name`` from S3 object tags or SSM.

    If *bucket* and *key* are provided, the object's tags are consulted first
    for ``name``.  If the tag is absent, the value is read from SSM under
    ``get_environment_prefix()``.
    """

    if bucket and key:
        try:
            resp = s3_client.get_object_tagging(Bucket=bucket, Key=key)
            for tag in resp.get("TagSet", []):
                if tag.get("Key") == name:
                    return tag.get("Value")
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - fallback to SSM
            logger.warning("Tag lookup failed for %s/%s: %s", bucket, key, exc)

    try:
        param_name = f"{get_environment_prefix()}/{name}"
        return get_values_from_ssm(param_name, decrypt)
    except (BotoCoreError, ClientError):
        return None

