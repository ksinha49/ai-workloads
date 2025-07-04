# LLM Router Service

This service routes prompts to different Large Language Model backends such as Amazon Bedrock or a local Ollama instance. `router-lambda/app.py` implements the Lambda entry point and relies on utilities shipped in the shared layer `common/layers/router-layer`.

Handler type hints reference dataclasses defined in ``models.py``:

- ``LlmRouterEvent`` – event passed to ``lambda_handler``
- ``LambdaResponse`` – HTTP-style response wrapper

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
| `BedrockSecretName` | `BEDROCK_SECRET_NAME` | Name or ARN of the Bedrock API key secret |
| `OllamaEndpoint` | `OLLAMA_ENDPOINTS` | URLs of Ollama services |
| `OllamaDefaultModel` | `OLLAMA_DEFAULT_MODEL` | Default model when none supplied |
| `PromptComplexityThreshold` | `PROMPT_COMPLEXITY_THRESHOLD` | Word threshold used by the heuristic router |
| `LlmInvocationFunctionName` | `LLM_INVOCATION_FUNCTION` | Name of the Lambda that invokes the selected backend |
| `ClassifierModelId` | `CLASSIFIER_MODEL_ID` | Optional model used to classify prompt complexity |
| `InvocationQueueUrl` | `INVOCATION_QUEUE_URL` | SQS queue used for async invocation |
| `MaxPromptLength` | `MAX_PROMPT_LENGTH` | Maximum length of the accepted prompt |
| `AllowedBackends` | `ALLOWED_BACKENDS` | Comma-separated list of permitted backends (default `bedrock,ollama`) |

Enabling `ClassifierModelId` activates predictive routing. The router will call
the classifier model to decide between the weak and strong Bedrock models
configured via `WEAK_MODEL_ID` and `STRONG_MODEL_ID`.

## Environment variables

In addition to the parameters above the Lambda accepts optional tuning variables for both Bedrock and Ollama such as `BEDROCK_TEMPERATURE`, `BEDROCK_NUM_CTX`, `OLLAMA_REPEAT_PENALTY`, etc. See `template.yaml` for the complete list and default values.

## Deployment

Deploy the router with SAM:

```bash
sam deploy \
  --template-file services/llm-router/template.yaml \
  --stack-name llm-router
```

To enable predictive routing supply model identifiers:

```bash
sam deploy \
  --parameter-overrides \
    ClassifierModelId=my-classifier \
    WeakModelId=my-weak-model \
    StrongModelId=my-strong-model
```

## Usage

Send an OpenAI-style payload to the Lambda. For example using the AWS CLI:

```bash
aws lambda invoke \
  --function-name llm-router \
  --payload '{"prompt": "Tell me a joke"}' out.json
```

The response includes a `backend` field indicating which service handled the request. You may set `backend` in the payload to force a specific destination. When omitted the router uses the heuristic strategy described above.

Requests are now placed on the SQS queue configured by `INVOCATION_QUEUE_URL` so the invocation Lambda processes them asynchronously.

The heuristic strategy is implemented by the `HeuristicRouter` module in the
shared layer.  By default it chooses Bedrock once the prompt length exceeds
`PROMPT_COMPLEXITY_THRESHOLD` words. Additional rules can be supplied via the
`HEURISTIC_ROUTER_CONFIG` environment variable.

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
