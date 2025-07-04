"""Backend invocation helpers for the LLM invocation Lambda."""

from __future__ import annotations

import json
import os
from itertools import cycle
from typing import Any, Callable, Dict, List, Sequence
import time

import boto3
import httpx
try:  # pragma: no cover - optional dependency
    from botocore.exceptions import BotoCoreError
except Exception:  # pragma: no cover - allow import without botocore
    BotoCoreError = Exception  # type: ignore
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass
from common_utils import configure_logger
from common_utils.get_ssm import get_config
from common_utils.get_secret import get_secret

logger = configure_logger(__name__)

_secret_name = (
    get_config("BEDROCK_SECRET_NAME")
    or os.environ.get("BEDROCK_SECRET_NAME", "BEDROCK_API_KEY")
)
BEDROCK_API_KEY = get_secret(_secret_name)
OLLAMA_DEFAULT_MODEL = (
    get_config("OLLAMA_DEFAULT_MODEL") or os.environ.get("OLLAMA_DEFAULT_MODEL", "")
)

# Default sampling parameters for Bedrock models
DEFAULT_BEDROCK_TEMPERATURE = 0.5
DEFAULT_BEDROCK_NUM_CTX = 4096
DEFAULT_BEDROCK_MAX_TOKENS = 2048
DEFAULT_BEDROCK_TOP_P = 0.9
DEFAULT_BEDROCK_TOP_K = 50
DEFAULT_BEDROCK_MAX_TOKENS_TO_SAMPLE = 2048

BEDROCK_TEMPERATURE = float(
    get_config("BEDROCK_TEMPERATURE")
    or os.environ.get("BEDROCK_TEMPERATURE", str(DEFAULT_BEDROCK_TEMPERATURE))
)
BEDROCK_NUM_CTX = int(
    get_config("BEDROCK_NUM_CTX")
    or os.environ.get("BEDROCK_NUM_CTX", str(DEFAULT_BEDROCK_NUM_CTX))
)
BEDROCK_MAX_TOKENS = int(
    get_config("BEDROCK_MAX_TOKENS")
    or os.environ.get("BEDROCK_MAX_TOKENS", str(DEFAULT_BEDROCK_MAX_TOKENS))
)
BEDROCK_TOP_P = float(
    get_config("BEDROCK_TOP_P") or os.environ.get("BEDROCK_TOP_P", str(DEFAULT_BEDROCK_TOP_P))
)
BEDROCK_TOP_K = int(
    get_config("BEDROCK_TOP_K") or os.environ.get("BEDROCK_TOP_K", str(DEFAULT_BEDROCK_TOP_K))
)
BEDROCK_MAX_TOKENS_TO_SAMPLE = int(
    get_config("BEDROCK_MAX_TOKENS_TO_SAMPLE")
    or os.environ.get(
        "BEDROCK_MAX_TOKENS_TO_SAMPLE", str(DEFAULT_BEDROCK_MAX_TOKENS_TO_SAMPLE)
    )
)

# Default sampling parameters for Ollama
DEFAULT_OLLAMA_NUM_CTX = 4096
DEFAULT_OLLAMA_REPEAT_LAST_N = 64
DEFAULT_OLLAMA_REPEAT_PENALTY = 1.1
DEFAULT_OLLAMA_TEMPERATURE = 0.7
DEFAULT_OLLAMA_SEED = 42
DEFAULT_OLLAMA_STOP = "AI assistant:"
DEFAULT_OLLAMA_NUM_PREDICT = 42
DEFAULT_OLLAMA_TOP_K = 40
DEFAULT_OLLAMA_TOP_P = 0.9
DEFAULT_OLLAMA_MIN_P = 0.05

OLLAMA_NUM_CTX = int(
    get_config("OLLAMA_NUM_CTX")
    or os.environ.get("OLLAMA_NUM_CTX", str(DEFAULT_OLLAMA_NUM_CTX))
)
OLLAMA_REPEAT_LAST_N = int(
    get_config("OLLAMA_REPEAT_LAST_N")
    or os.environ.get("OLLAMA_REPEAT_LAST_N", str(DEFAULT_OLLAMA_REPEAT_LAST_N))
)
OLLAMA_REPEAT_PENALTY = float(
    get_config("OLLAMA_REPEAT_PENALTY")
    or os.environ.get("OLLAMA_REPEAT_PENALTY", str(DEFAULT_OLLAMA_REPEAT_PENALTY))
)
OLLAMA_TEMPERATURE = float(
    get_config("OLLAMA_TEMPERATURE")
    or os.environ.get("OLLAMA_TEMPERATURE", str(DEFAULT_OLLAMA_TEMPERATURE))
)
OLLAMA_SEED = int(
    get_config("OLLAMA_SEED") or os.environ.get("OLLAMA_SEED", str(DEFAULT_OLLAMA_SEED))
)
OLLAMA_STOP = get_config("OLLAMA_STOP") or os.environ.get("OLLAMA_STOP", DEFAULT_OLLAMA_STOP)
OLLAMA_NUM_PREDICT = int(
    get_config("OLLAMA_NUM_PREDICT")
    or os.environ.get("OLLAMA_NUM_PREDICT", str(DEFAULT_OLLAMA_NUM_PREDICT))
)
OLLAMA_TOP_K = int(
    get_config("OLLAMA_TOP_K") or os.environ.get("OLLAMA_TOP_K", str(DEFAULT_OLLAMA_TOP_K))
)
OLLAMA_TOP_P = float(
    get_config("OLLAMA_TOP_P") or os.environ.get("OLLAMA_TOP_P", str(DEFAULT_OLLAMA_TOP_P))
)
OLLAMA_MIN_P = float(
    get_config("OLLAMA_MIN_P") or os.environ.get("OLLAMA_MIN_P", str(DEFAULT_OLLAMA_MIN_P))
)


def _get_endpoints(plural_var: str, single_var: str) -> List[str]:
    """Return a list of endpoint URLs read from environment variables."""

    raw = get_config(plural_var) or os.environ.get(plural_var)
    if raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if parts:
            return parts
    single = get_config(single_var) or os.environ.get(single_var)
    return [single] if single else []


def _make_selector(endpoints: Sequence[str]) -> Callable[[], str]:
    """Return a round-robin selector over ``endpoints``."""

    if not endpoints:
        def _select() -> str:
            raise RuntimeError("No endpoints configured")
        return _select

    cyc = cycle(endpoints)

    def _select() -> str:
        return next(cyc)

    return _select


class _HealthCheckedSelector:
    """Round-robin selector with basic health checking."""

    def __init__(
        self,
        endpoints: Sequence[str],
        failure_threshold: int = 1,
        cooldown: int = 60,
    ) -> None:
        """Create a selector over ``endpoints`` with failure tracking."""
        self._endpoints = list(endpoints)
        self._cycle = cycle(self._endpoints) if self._endpoints else None
        self._failures = {ep: 0 for ep in self._endpoints}
        self._last_failure = {ep: 0.0 for ep in self._endpoints}
        self._threshold = failure_threshold
        self._cooldown = cooldown

    def choose(self) -> str:
        """Return the next healthy endpoint or raise if none are configured."""
        if not self._endpoints:
            raise RuntimeError("No endpoints configured")

        for _ in range(len(self._endpoints)):
            ep = next(self._cycle)
            fails = self._failures.get(ep, 0)
            last = self._last_failure.get(ep, 0.0)
            if fails < self._threshold or time.time() - last >= self._cooldown:
                return ep

        return next(self._cycle)

    def record_success(self, endpoint: str) -> None:
        """Mark ``endpoint`` as healthy after a successful request."""
        if endpoint in self._failures:
            self._failures[endpoint] = 0

    def record_failure(self, endpoint: str) -> None:
        """Increment failure count for ``endpoint`` and update cooldown time."""
        if endpoint in self._failures:
            self._failures[endpoint] += 1
            self._last_failure[endpoint] = time.time()


BEDROCK_OPENAI_ENDPOINTS = _get_endpoints(
    "BEDROCK_OPENAI_ENDPOINTS", "BEDROCK_OPENAI_ENDPOINT"
)
OLLAMA_ENDPOINTS = _get_endpoints("OLLAMA_ENDPOINTS", "OLLAMA_ENDPOINT")

_bedrock_selector = _HealthCheckedSelector(BEDROCK_OPENAI_ENDPOINTS)
_ollama_selector = _HealthCheckedSelector(OLLAMA_ENDPOINTS)

def choose_bedrock_openai_endpoint() -> str:
    """Return a healthy endpoint URL for the Bedrock OpenAI runtime."""

    return _bedrock_selector.choose()


def choose_ollama_endpoint() -> str:
    """Return a healthy endpoint URL for the Ollama runtime."""

    return _ollama_selector.choose()


def invoke_bedrock_runtime(
    prompt: str, model_id: str | None = None, system_prompt: str | None = None
) -> Dict[str, Any]:
    """Call Bedrock using its OpenAI compatible runtime."""

    runtime = boto3.client("bedrock-runtime")
    model_id = (
        model_id
        or get_config("STRONG_MODEL_ID")
        or os.environ.get("STRONG_MODEL_ID")
        or get_config("WEAK_MODEL_ID")
        or os.environ.get("WEAK_MODEL_ID")
    )

    messages = [{"role": "user", "content": prompt}]
    if system_prompt is not None:
        messages.insert(0, {"role": "system", "content": system_prompt})

    body = json.dumps(
        {
            "model": model_id,
            "messages": messages,
            "temperature": BEDROCK_TEMPERATURE,
            "num_ctx": BEDROCK_NUM_CTX,
            "max_tokens": BEDROCK_MAX_TOKENS,
            "top_p": BEDROCK_TOP_P,
            "top_k": BEDROCK_TOP_K,
            "max_tokens_to_sample": BEDROCK_MAX_TOKENS_TO_SAMPLE,
        }
    )

    def _invoke() -> Dict[str, Any]:
        return runtime.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

    try:
        resp = _invoke()
        data = json.loads(resp.get("body").read())
    except (BotoCoreError, json.JSONDecodeError) as exc:  # pragma: no cover - network/runtime failures
        logger.error("Bedrock runtime invocation failed: %s", exc)
        raise

    reply = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return {"reply": reply}


def invoke_bedrock_openai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send ``payload`` to a Bedrock OpenAI endpoint and return the response."""

    endpoint = choose_bedrock_openai_endpoint()
    headers = {"Content-Type": "application/json"}
    if BEDROCK_API_KEY:
        headers["Authorization"] = f"Bearer {BEDROCK_API_KEY}"
    payload.setdefault("temperature", BEDROCK_TEMPERATURE)
    payload.setdefault("num_ctx", BEDROCK_NUM_CTX)
    payload.setdefault("max_tokens", BEDROCK_MAX_TOKENS)
    payload.setdefault("top_p", BEDROCK_TOP_P)
    payload.setdefault("top_k", BEDROCK_TOP_K)
    payload.setdefault("max_tokens_to_sample", BEDROCK_MAX_TOKENS_TO_SAMPLE)
    try:
        resp = httpx.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
    except HTTPError:
        _bedrock_selector.record_failure(endpoint)
        raise
    else:
        _bedrock_selector.record_success(endpoint)
    return resp.json()


def invoke_ollama(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send ``payload`` to an Ollama endpoint and return the response."""

    endpoint = choose_ollama_endpoint()
    payload.setdefault("model", OLLAMA_DEFAULT_MODEL)

    payload.setdefault("num_ctx", OLLAMA_NUM_CTX)
    payload.setdefault("repeat_last_n", OLLAMA_REPEAT_LAST_N)
    payload.setdefault("repeat_penalty", OLLAMA_REPEAT_PENALTY)
    payload.setdefault("temperature", OLLAMA_TEMPERATURE)
    payload.setdefault("seed", OLLAMA_SEED)
    payload.setdefault("stop", OLLAMA_STOP)
    payload.setdefault("num_predict", OLLAMA_NUM_PREDICT)
    payload.setdefault("top_k", OLLAMA_TOP_K)
    payload.setdefault("top_p", OLLAMA_TOP_P)
    payload.setdefault("min_p", OLLAMA_MIN_P)
    try:
        resp = httpx.post(endpoint, json=payload)
        resp.raise_for_status()
    except HTTPError:
        _ollama_selector.record_failure(endpoint)
        raise
    else:
        _ollama_selector.record_success(endpoint)
    return resp.json()


__all__ = [
    "choose_bedrock_openai_endpoint",
    "choose_ollama_endpoint",
    "invoke_bedrock_openai",
    "invoke_bedrock_runtime",
    "invoke_ollama",
]

# Endpoint selection uses ``_HealthCheckedSelector`` instances which perform
# round-robin load balancing and temporarily mark endpoints as unhealthy when
# requests fail.
