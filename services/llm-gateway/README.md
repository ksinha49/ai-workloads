# LLM Gateway Service

This consolidated service groups three Lambdas that work together to process Large Language Model requests.  Templates are rendered by the prompt engine, queued through the router and finally executed by the invocation function.

## Lambdas

- **prompt_engine_lambda.py** – loads a template from DynamoDB and forwards the rendered prompt to the router.
- **llm_router_lambda.py** – selects a backend and places the request on the invocation queue.
- **llm_invocation_lambda.py** – invokes Bedrock or Ollama and returns the raw response.

## Parameters and environment variables

`template.yaml` defines parameters for each Lambda that become environment variables.

### prompt_engine_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `TableName` | `PROMPT_LIBRARY_TABLE` | DynamoDB table containing prompt templates |
| `RouterEndpoint` | `ROUTER_ENDPOINT` | URL of the router service |
| `LambdaSubnet1ID` / `LambdaSubnet2ID` | – | Subnets used by the Lambda |
| `LambdaSecurityGroupID1` / `LambdaSecurityGroupID2` | – | Security groups attached to the Lambda |
| `LambdaIAMRoleARN` | – | IAM role assumed by the function |

### llm_router_lambda

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `BedrockOpenAIEndpoint` | `BEDROCK_OPENAI_ENDPOINTS` | Comma-separated Bedrock OpenAI endpoints |
| `BedrockSecretName` | `BEDROCK_SECRET_NAME` | Name or ARN of the Bedrock API key secret |
| `OllamaEndpoint` | `OLLAMA_ENDPOINTS` | URLs of Ollama services |
| `OllamaDefaultModel` | `OLLAMA_DEFAULT_MODEL` | Default model when none supplied |
| `PromptComplexityThreshold` | `PROMPT_COMPLEXITY_THRESHOLD` | Word threshold used by the heuristic router |
| `LlmInvocationFunctionName` | `LLM_INVOCATION_FUNCTION` | Name of the invocation Lambda |
| `ClassifierModelId` | `CLASSIFIER_MODEL_ID` | Optional model used for predictive routing |

### llm_invocation_lambda

Parameters mirror the environment variables controlling each backend. The most common ones are:

- `BEDROCK_TEMPERATURE`, `BEDROCK_NUM_CTX`, `BEDROCK_MAX_TOKENS`,
  `BEDROCK_TOP_P`, `BEDROCK_TOP_K`, `BEDROCK_MAX_TOKENS_TO_SAMPLE`
- `OLLAMA_NUM_CTX`, `OLLAMA_REPEAT_LAST_N`, `OLLAMA_REPEAT_PENALTY`,
  `OLLAMA_TEMPERATURE`, `OLLAMA_SEED`, `OLLAMA_STOP`, `OLLAMA_NUM_PREDICT`,
  `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P`

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/llm-gateway/template.yaml --stack-name llm-gateway
```

The stack exports `PromptEngineFunctionArn`, `RouterFunctionArn` and `LlmInvocationFunctionArn` for use by other services.

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
