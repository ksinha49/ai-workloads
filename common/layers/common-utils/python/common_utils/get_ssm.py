"""Shared helpers for retrieving SSM parameters and parsing S3 URIs."""

import logging
from typing import Optional, Tuple
import boto3

__author__ = "Koushik Sinha"
__version__ = "1.0.1"
__modified_by__ = "Koushik Sinha"

logger = logging.getLogger(__name__)
_ssm_client = boto3.client("ssm")

# Simple in-memory cache so functions within a single Lambda invocation
# don't repeatedly hit SSM
_SSM_CACHE: dict[str, str] = {}
s3_client = boto3.client("s3")

def get_values_from_ssm(name: str, decrypt: bool = False) -> Optional[str]:
    """Retrieve a parameter value from SSM with optional decryption."""
    if name in _SSM_CACHE:
        return _SSM_CACHE[name]
    try:
        resp = _ssm_client.get_parameter(Name=name, WithDecryption=decrypt)
        value = resp["Parameter"]["Value"]
        _SSM_CACHE[name] = value
        logger.info("Parameter Value for %s: %s", name, value)
        return value
    except Exception as exc:
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
        except Exception as exc:  # pragma: no cover - fallback to SSM
            logger.warning("Tag lookup failed for %s/%s: %s", bucket, key, exc)

    param_name = f"{get_environment_prefix()}/{name}"
    return get_values_from_ssm(param_name, decrypt)

