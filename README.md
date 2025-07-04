# Enterprise AI Services

Enterprise AI Services is a collection of AWS Lambda microservices for building serverless document processing workflows. Each service focuses on a specific task such as OCR extraction, PDF assembly or embedding generation.

## Services

The repository includes the following directories under `services/`:

- `file-assembly` – merges summary pages with the original PDF
- `file-ingestion` – copies files to the IDP bucket and polls for text
  extraction status
- `idp` – Intelligent Document Processing pipeline (classification, OCR and text extraction)
- `zip-processing` – extracts PDFs from uploaded archives and assembles new ZIPs
- `rag-ingestion` – chunks text and generates embeddings stored in Milvus
- `vector-db` – manages Milvus collections and search Lambdas
- `rag-retrieval` – retrieval functions and API endpoints for summarization or entity extraction
- `summarization` – Step Function workflow orchestrating file processing and summary generation
- `prompt-engine` – renders templates from DynamoDB and forwards them to the router
- `llm-router` – routes prompts via heuristic, predictive and cascading strategies to Amazon Bedrock or local Ollama
- `llm-invocation` – forwards OpenAI-style requests to a specific LLM backend
- `knowledge-base` – ingest text snippets and query them through the retrieval stack
- `sensitive-info-detection` – PII/PHI detection for text including legal entities
- `entity-tokenization` – replaces sensitive entities with stable tokens
- `text-anonymization` – replaces or masks detected entities in text

Shared dependencies are packaged as layers in `common/layers/`.

### Service descriptions

#### file-assembly
Merges summary pages produced by the summarization workflow back into the
original PDF and uploads the result to S3.

#### file-ingestion
Copies files to the IDP bucket and waits for text extraction before starting
RAG ingestion.

#### idp
Implements the Intelligent Document Processing pipeline with steps for
classification, page splitting, text extraction, OCR and posting the final JSON
to an external API.

#### zip-processing
Unpacks uploaded ZIP archives, processes each PDF through the summarization
workflow and assembles a new archive with the merged outputs.

#### rag-ingestion
Splits text documents into overlapping chunks, generates embeddings using
`embed-lambda` and stores them in Milvus via the `vector-db` functions.

#### vector-db
Provides Lambda functions for creating collections, inserting, updating and
searching embeddings stored in Milvus. Similarity search is implemented in
`vector-search-lambda` for pure vector queries and `hybrid-search-lambda` for
vector search with optional keyword filtering. The stack exports the ARNs
`VectorSearchFunctionArn` and `HybridSearchFunctionArn` for these functions.

#### rag-retrieval
Queries the vector database for relevant context and forwards results to
summarization, content extraction or entity extraction endpoints. The retrieval
Lambdas invoke whichever search function name is stored in the
`VECTOR_SEARCH_FUNCTION` environment variable. Pointing this variable to the
`HybridSearchFunctionArn` exported by the `vector-db` stack toggles the service
from pure vector search to hybrid search.

#### summarization
Step Function workflow that depends on the `file-ingestion` stack to copy a
file to the IDP bucket and wait for text extraction. It then generates
summaries with `file-summary-lambda`, which can output PDF, DOCX, JSON or XML
files based on an `output_format` field, and merges them back with the original
PDF when applicable. When a `workflow_id`
is supplied the workflow fetches the corresponding prompt collection from the
Prompt Engine and automatically loads the workflow's system prompt. The service
accepts a `PromptEngineEndpoint` environment variable to override the engine URL.
See [docs/summarization_workflow.md](docs/summarization_workflow.md) for details.

#### prompt-engine
Loads templates from a DynamoDB table, renders them with the provided variables
and forwards the final prompt to the router service.

#### llm-router
Routes prompts to Amazon Bedrock or local Ollama using heuristic, predictive and
cascading strategies. Requests are now queued on SQS so backend invocation
happens asynchronously.

#### llm-invocation
Forwards OpenAI-style requests to the chosen LLM backend with configurable
generation parameters. The handler consumes events from the router's queue and
uses dataclass models for type‑safe payloads.

#### knowledge-base
Provides a lightweight API to ingest short text documents and query them using
the retrieval and summarization stack. Query requests are also published to the
summarization queue for asynchronous processing.

#### sensitive-info-detection
Detects PII, PHI and legal entities in text using regex patterns and optional
machine learning models. Domain-specific models and regex overrides can be
configured via environment variables.

#### entity-tokenization
Replaces sensitive entity values with consistent tokens. Existing mappings are
looked up in DynamoDB and new tokens are generated using an optional salt.

#### text-anonymization
Replaces or masks entities detected in text. The Lambda supports three modes:
`mask` to overwrite spans with `[REMOVED]`, `pseudo` to generate synthetic
values, or `token` to invoke the tokenization service for stable replacements.
The service relies on the entity detection output to locate spans.

## Repository Structure

```text
.
├── INSTALL.md
├── README.md
├── common/
│   └── layers/
├── docs/
│   ├── idp_output_format.md
│   ├── router_configuration.md
│   └── summarization_workflow.md
├── services/
│   └── <service directories>
├── template.yaml
└── tests/
```

## Installation

Refer to [INSTALL.md](INSTALL.md) for detailed steps. In short:

```bash
git clone https://github.com/ameritascorp/aio-enterprise-ai-services.git
cd aio-enterprise-ai-services
sam build
```

Python packages are installed into each Lambda's layer under `common/layers/` during the build.

## Configuration

Runtime settings are stored in AWS Systems Manager Parameter Store using the path `/parameters/aio/ameritasAI/<ENV>/<NAME>`. S3 object tags with the same keys may override these values for individual files.

### OCR Engine

The `OCR_ENGINE` variable controls which OCR backend to use:

- `easyocr` (default)
- `paddleocr`
- `trocr` – requires `TROCR_ENDPOINT`
- `docling` – requires `DOCLING_ENDPOINT`

## Environment Variables

See [docs/environment_variables.md](docs/environment_variables.md) for a
complete list of common variables used across the services.


## Deployment

Deploy a service with `sam deploy --template-file services/<service>/template.yaml --stack-name <name>` and provide any required parameters. See each service's README for details.

## Documentation

Additional documentation is available in the `docs/` directory:

- [docs/idp_output_format.md](docs/idp_output_format.md)
- [docs/router_configuration.md](docs/router_configuration.md)
- [docs/summarization_workflow.md](docs/summarization_workflow.md)
- [docs/prompt_engine.md](docs/prompt_engine.md)
- [docs/knowledge_rag_usage.md](docs/knowledge_rag_usage.md)
- [docs/event_schemas.md](docs/event_schemas.md)
- [docs/entity_tokenization_service.md](docs/entity_tokenization_service.md)
- [docs/tokenization_workflow.md](docs/tokenization_workflow.md)
- [docs/environment_variables.md](docs/environment_variables.md)
