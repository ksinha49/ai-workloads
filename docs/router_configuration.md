# LLM Gateway Router Configuration

This document details the environment variables used by the router Lambda that forms part of the **llm-gateway** service and how they are typically provided.

## Environment Variables

| Name | Description |
| ---- | ----------- |
| `BEDROCK_OPENAI_ENDPOINTS` | Comma‑separated Bedrock endpoints implementing the OpenAI API. |
| `BEDROCK_SECRET_NAME` | Name or ARN of the Bedrock API key secret. |
| `BEDROCK_TEMPERATURE` | Sampling temperature for Bedrock models (default `0.5`). |
| `BEDROCK_NUM_CTX` | Context length for Bedrock calls (default `4096`). |
| `BEDROCK_MAX_TOKENS` | Maximum tokens to generate (default `2048`). |
| `BEDROCK_TOP_P` | Nucleus sampling parameter (default `0.9`). |
| `BEDROCK_TOP_K` | Top‑k sampling parameter (default `50`). |
| `BEDROCK_MAX_TOKENS_TO_SAMPLE` | Maximum tokens Bedrock should sample (default `2048`). |
| `OLLAMA_ENDPOINTS` | Comma‑separated URLs of the local Ollama services. |
| `OLLAMA_DEFAULT_MODEL` | Default model name if one is not supplied in the payload. |
| `OLLAMA_NUM_CTX` | Context length for Ollama requests (default `4096`). |
| `OLLAMA_REPEAT_LAST_N` | Repetition window size for Ollama (default `64`). |
| `OLLAMA_REPEAT_PENALTY` | Repetition penalty for Ollama (default `1.1`). |
| `OLLAMA_TEMPERATURE` | Sampling temperature for Ollama models (default `0.7`). |
| `OLLAMA_SEED` | Random seed for generation (default `42`). |
| `OLLAMA_STOP` | Stop sequence for Ollama (default `"AI assistant:"`). |
| `OLLAMA_NUM_PREDICT` | Number of tokens to predict (default `42`). |
| `OLLAMA_TOP_K` | Top‑k sampling parameter (default `40`). |
| `OLLAMA_TOP_P` | Nucleus sampling parameter (default `0.9`). |
| `OLLAMA_MIN_P` | Minimum probability threshold (default `0.05`). |
| `ALLOWED_BACKENDS` | Comma-separated list of permitted backend names (default `bedrock,ollama`). |
| `PROMPT_COMPLEXITY_THRESHOLD` | Word count threshold that determines when to switch from Ollama to Bedrock (defaults to `20`). |
| `ROUTELLM_ENDPOINT` | Optional URL for forwarding requests to a RouteLLM service. |
| `STRONG_MODEL_ID` | Identifier for the more capable Bedrock model. |
| `WEAK_MODEL_ID` | Identifier for the lightweight model used with shorter prompts. |
| `CLASSIFIER_MODEL_ID` | Optional model used to classify prompts for predictive routing. |
| `LLM_INVOCATION_FUNCTION` | Name of the Lambda used for actual model invocation. |

When `CLASSIFIER_MODEL_ID` is set the router bypasses the simple length
heuristic and delegates prompt selection to the predictive strategy. The
classifier model decides whether a prompt is *simple* or *complex* and routes to
`WEAK_MODEL_ID` or `STRONG_MODEL_ID` accordingly.

## Setting Values with Parameter Store

1. Open AWS Systems Manager &rarr; Parameter Store.
2. Create parameters for each variable under your stack's prefix.
3. Deploy the Lambda with `sam deploy`, passing the prefix via `--parameter-overrides` if needed.
4. During execution the Lambda reads these values from the environment.
