# Service Descriptions

This directory groups all serverless microservices that make up the Enterprise AI platform. Each service focuses on a specific task and exposes one or more AWS Lambda functions. Individual directories contain deployment templates and additional documentation.

## file-assembly
Merges summary pages produced by the summarization workflow back into the original PDF and uploads the result to Amazon S3.

- **Lambda:** `file-assemble-lambda`
- Requires `AWS_ACCOUNT_NAME` to scope resources

## file-ingestion
Copies uploaded files to the IDP bucket and waits for text extraction results before triggering RAG ingestion.

- **Lambdas:** `file-processing-lambda`, `file-processing-status-lambda`
- **State machine:** `FileIngestionStateMachine` orchestrates the flow

See the [file ingestion workflow](../docs/file_ingestion_workflow.md) for an overview.

## idp
Complete Intelligent Document Processing pipeline performing classification, page splitting, text extraction and OCR before posting JSON output to an external API.

- Supports multiple OCR engines via the `OCR_ENGINE` variable
- Consumes and produces events from S3

## zip-processing
Unpacks uploaded ZIP archives, processes PDFs through the summarization workflow and assembles a new ZIP with the merged outputs.

- **Lambdas:** `zip-extract-lambda`, `zip-creation-lambda`
- Driven by a Step Function defined in the stack

## rag-ingestion
Splits text into overlapping chunks, generates embeddings and stores them in Milvus.

- **Lambdas:** `text-chunk-lambda`, `embed-lambda`
- Exports the ingestion state machine for other stacks

For a detailed workflow, see [../docs/rag_ingestion_workflow.md](../docs/rag_ingestion_workflow.md).

## vector-db
Manages Milvus collections and provides search functions.

- Collection management Lambdas for create/drop/update
- Search Lambdas for vector and hybrid queries
- Exports `VectorSearchFunctionArn` and `HybridSearchFunctionArn`

## rag-retrieval
Retrieves relevant context from the vector database and forwards it to summarization or extraction APIs.

- Uses the search function referenced by `VECTOR_SEARCH_FUNCTION`
- Supports pure vector and hybrid search modes

## summarization
Orchestrates file ingestion, prompt execution and summary generation.

- Generates PDF, DOCX, JSON or XML summaries
- Integrates with the prompt engine using `workflow_id`

## prompt-engine
Renders prompt templates stored in DynamoDB and sends the final prompt to the LLM router.

- Parameterised by `PromptLibraryTable` and `RouterEndpoint`
- Accepts `prompt_id` and `variables` in requests

## llm-router
Routes prompts to Amazon Bedrock or a local Ollama instance using heuristic, predictive and cascading strategies.

- Requests are queued on SQS for asynchronous processing
- Returns which backend produced the response

## llm-invocation
Forwards OpenAI-style requests to the configured backend with optional system prompts.

- Can be invoked directly or via the router queue
- Uses dataclass models for type-safe payloads

## knowledge-base
Provides a lightweight API to ingest short text documents and query them using the retrieval stack.

- Supports metadata and entity filters on queries
- Publishes summarization requests to a queue for async processing

## sensitive-info-detection
Detects PII, PHI and legal entities in text using regex patterns and optional machine learning models.

- Exports `DetectSensitiveInfoFunctionArn` for other services
- Regex overrides can be supplied via environment variables

## entity-tokenization
Replaces sensitive entity values with stable tokens stored in DynamoDB.

- Generates deterministic tokens when a salt is provided
- Exports `TokenizeEntityFunctionArn` and `TokenTableName`

## text-anonymization
Masks or replaces entities detected in text.

- Supports `mask`, `pseudo` and `token` modes
- Relies on the entity detection output to locate spans

