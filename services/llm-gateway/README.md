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

These parameters configure the backends invoked by the Lambda. They map
directly to environment variables used in the code.

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `BedrockOpenAIEndpoint` | `BEDROCK_OPENAI_ENDPOINTS` | Comma-separated Bedrock OpenAI endpoints |
| `BedrockSecretName` | `BEDROCK_SECRET_NAME` | Name or ARN of the Bedrock API key secret |
| `BedrockTemperature` | `BEDROCK_TEMPERATURE` | Sampling temperature for Bedrock models |
| `BedrockNumCtx` | `BEDROCK_NUM_CTX` | Context window size |
| `BedrockMaxTokens` | `BEDROCK_MAX_TOKENS` | Maximum tokens in the completion |
| `BedrockTopP` | `BEDROCK_TOP_P` | Nucleus sampling parameter |
| `BedrockTopK` | `BEDROCK_TOP_K` | Top-K sampling parameter |
| `BedrockMaxTokensToSample` | `BEDROCK_MAX_TOKENS_TO_SAMPLE` | Streaming token limit for Claude models |
| `OllamaEndpoint` | `OLLAMA_ENDPOINTS` | URLs of Ollama services |
| `OllamaDefaultModel` | `OLLAMA_DEFAULT_MODEL` | Default model when none supplied |
| `OllamaNumCtx` | `OLLAMA_NUM_CTX` | Context window size |
| `OllamaRepeatLastN` | `OLLAMA_REPEAT_LAST_N` | Repeat penalty look-back |
| `OllamaRepeatPenalty` | `OLLAMA_REPEAT_PENALTY` | Penalize repeating tokens |
| `OllamaTemperature` | `OLLAMA_TEMPERATURE` | Sampling temperature for Ollama models |
| `OllamaSeed` | `OLLAMA_SEED` | Seed for reproducible outputs |
| `OllamaStop` | `OLLAMA_STOP` | Stop sequences separated by commas |
| `OllamaNumPredict` | `OLLAMA_NUM_PREDICT` | Maximum tokens to generate |
| `OllamaTopK` | `OLLAMA_TOP_K` | Top-K sampling parameter |
| `OllamaTopP` | `OLLAMA_TOP_P` | Nucleus sampling parameter |
| `OllamaMinP` | `OLLAMA_MIN_P` | Minimum probability threshold |


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
