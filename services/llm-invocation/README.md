# LLM Invocation Service

This service exposes a single Lambda function that forwards OpenAI-style requests to a specific LLM backend. It is typically invoked by the LLM router but can also be called directly.
The function can now be triggered asynchronously from an SQS queue used by the router service.

The handler uses dataclasses from ``models.py``:

- ``LlmInvocationEvent`` – normalised request payload
- ``LambdaResponse`` – wrapper around the backend reply

`invoke-lambda/app.py` contains the handler. All Python dependencies come from the shared layer `common/layers/llm-invocation-layer` so no additional requirements file is needed.

## Environment variables

Parameters defined in `template.yaml` map directly to environment variables used by the Lambda. The most common ones are:

### Bedrock options
- `BEDROCK_OPENAI_ENDPOINTS` – comma-separated endpoints for the Bedrock OpenAI API.
- `BEDROCK_API_KEY` – API key used when contacting Bedrock.
- `BEDROCK_TEMPERATURE`, `BEDROCK_NUM_CTX`, `BEDROCK_MAX_TOKENS`,
  `BEDROCK_TOP_P`, `BEDROCK_TOP_K`, `BEDROCK_MAX_TOKENS_TO_SAMPLE` – sampling
  settings applied to each Bedrock request.

### Ollama options
- `OLLAMA_ENDPOINTS` – comma-separated URLs of local Ollama servers.
- `OLLAMA_DEFAULT_MODEL` – model name when not specified in the payload.
- `OLLAMA_NUM_CTX`, `OLLAMA_REPEAT_LAST_N`, `OLLAMA_REPEAT_PENALTY`,
  `OLLAMA_TEMPERATURE`, `OLLAMA_SEED`, `OLLAMA_STOP`, `OLLAMA_NUM_PREDICT`,
  `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P` – corresponding generation
  parameters for Ollama.

## Deployment

Deploy the Lambda with SAM:

```bash
sam deploy \
  --template-file services/llm-invocation/template.yaml \
  --stack-name llm-invocation
```

## Usage

Invoke the function with a payload specifying the backend and prompt:

```bash
aws lambda invoke \
  --function-name invoke-llm \
  --payload '{"backend": "bedrock", "prompt": "Hello"}' out.json
```

If `system_prompt` is provided it will be sent as the system message to the backend.
