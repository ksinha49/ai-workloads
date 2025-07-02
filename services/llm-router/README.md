# LLM Router Service

This service routes prompts to different Large Language Model backends such as Amazon Bedrock or a local Ollama instance. `router-lambda/app.py` implements the Lambda entry point and relies on utilities shipped in the shared layer `common/layers/router-layer`.

The routing logic is split into small modules which can also be reused outside the Lambda:

- **main_router.py** – exposes `route_event` orchestrating the routing flow.
- **cascading_router.py** – implements a *weak then strong* strategy that tries a cheaper model first and escalates if the response fails a quality check.
- **heuristic_router.py** – simple rule based routing by prompt length.
- **predictive_router.py** – placeholder for ML based routing logic.
- **generative_router.py** – fallback that always selects a backend so a reply is returned.
- **routellm_integration.py** – helper for forwarding a request to an external RouteLLM service.

## Parameters

`template.yaml` exposes a few parameters that become environment variables:

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `BedrockOpenAIEndpoint` | `BEDROCK_OPENAI_ENDPOINTS` | Comma-separated Bedrock OpenAI endpoints |
| `BedrockApiKey` | `BEDROCK_API_KEY` | API key when calling Bedrock |
| `OllamaEndpoint` | `OLLAMA_ENDPOINTS` | URLs of Ollama services |
| `OllamaDefaultModel` | `OLLAMA_DEFAULT_MODEL` | Default model when none supplied |
| `PromptComplexityThreshold` | `PROMPT_COMPLEXITY_THRESHOLD` | Word threshold used by the heuristic router |
| `LlmInvocationFunctionName` | `LLM_INVOCATION_FUNCTION` | Name of the Lambda that invokes the selected backend |

## Environment variables

In addition to the parameters above the Lambda accepts optional tuning variables for both Bedrock and Ollama such as `BEDROCK_TEMPERATURE`, `BEDROCK_NUM_CTX`, `OLLAMA_REPEAT_PENALTY`, etc. See `template.yaml` for the complete list and default values.

## Deployment

Deploy the router with SAM:

```bash
sam deploy \
  --template-file services/llm-router/template.yaml \
  --stack-name llm-router
```

## Usage

Send an OpenAI-style payload to the Lambda. For example using the AWS CLI:

```bash
aws lambda invoke \
  --function-name llm-router \
  --payload '{"prompt": "Tell me a joke"}' out.json
```

The response includes a `backend` field indicating which service handled the request. You may set `backend` in the payload to force a specific destination. When omitted the router uses the heuristic strategy described above.
