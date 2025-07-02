"""Simplified accessors for invoking LLM backends.

These wrappers proxy to :mod:`llm_invocation.backends` so code outside
this layer can import a single module.
"""

from llm_invocation.backends import (
    invoke_ollama as _invoke_ollama,
    invoke_bedrock_runtime as _invoke_bedrock_runtime,
    invoke_bedrock_openai as _invoke_bedrock_openai,
)

__all__ = [
    "invoke_ollama",
    "invoke_bedrock_runtime",
    "invoke_bedrock_openai",
]


def invoke_ollama(payload):
    """Forward the payload to an Ollama endpoint."""
    return _invoke_ollama(payload)


def invoke_bedrock_runtime(prompt, model_id=None, system_prompt=None):
    """Invoke the Bedrock runtime directly."""
    return _invoke_bedrock_runtime(prompt, model_id, system_prompt)


def invoke_bedrock_openai(payload):
    """Invoke Bedrock via its OpenAI compatible endpoint."""
    return _invoke_bedrock_openai(payload)
