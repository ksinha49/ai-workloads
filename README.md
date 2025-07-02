# Enterprise AI Services

Enterprise AI Services is a collection of AWS Lambda microservices for building serverless document processing workflows. Each service focuses on a specific task such as OCR extraction, PDF assembly or embedding generation.

## Services

The repository includes the following directories under `services/`:

- `file-assembly` – merges summary pages with the original PDF
- `idp` – Intelligent Document Processing pipeline (classification, OCR and text extraction)
- `zip-processing` – extracts PDFs from uploaded archives and assembles new ZIPs
- `rag-ingestion` – chunks text and generates embeddings stored in Milvus
- `vector-db` – manages Milvus collections and search Lambdas
- `rag-retrieval` – retrieval functions and API endpoints for summarization or entity extraction
- `summarization` – Step Function workflow orchestrating file processing and summary generation
- `llm-router` – routes prompts via heuristic, predictive and cascading strategies to Amazon Bedrock or local Ollama
- `llm-invocation` – forwards OpenAI-style requests to a specific LLM backend
- `knowledge-base` – ingest text snippets and query them through the retrieval stack

Shared dependencies are packaged as layers in `common/layers/`.

### Service descriptions

#### file-assembly
Merges summary pages produced by the summarization workflow back into the
original PDF and uploads the result to S3.

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
Step Function workflow that copies a file to the IDP bucket, waits for text
extraction, generates summaries and merges them back with the original PDF.

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

Each service loads its configuration from Parameter Store or the Lambda
environment. The table below summarises the most common variables.

### Core services

- `AWS_ACCOUNT_NAME` – scopes stack resources for the file‑assembly,
  zip‑processing and summarization stacks.

### Intelligent Document Processing (IDP)

- `BUCKET_NAME` – S3 bucket for pipeline objects.
- `RAW_PREFIX` – uploads waiting to be processed.
- `CLASSIFIED_PREFIX` – classifier output prefix.
- `OFFICE_PREFIX` – Office files with embedded text.
- `SPLIT_PREFIX` – where PDFs are split into pages.
- `PAGE_PREFIX` – PDF pages waiting for further processing.
- `TEXT_PREFIX` – text extracted from PDF pages.
- `OCR_PREFIX` – OCR results for scanned pages.
- `COMBINE_PREFIX` – location for combined page JSON.
- `OUTPUT_PREFIX` – final output JSON after external API calls.
- `TEXT_DOC_PREFIX` – merged document JSON files.
- `OCR_ENGINE` – selected OCR engine.
- `TROCR_ENDPOINT` – TrOCR service URL when using `trocr`.
- `DOCLING_ENDPOINT` – Docling service URL when using `docling`.
- `PDF_RAW_PREFIX`, `PDF_PAGE_PREFIX`, `PDF_TEXT_PAGE_PREFIX`,
  `PDF_SCAN_PAGE_PREFIX`, `TEXT_PAGE_PREFIX` – internal prefixes used by
  the pipeline.
- `DPI` – image resolution for OCR.
- `EDI_SEARCH_API_URL` / `EDI_SEARCH_API_KEY` – external API for IDP output.

### RAG Ingestion

- `CHUNK_SIZE` – characters per chunk.
- `CHUNK_OVERLAP` – overlap between chunks.
- `EXTRACT_ENTITIES` – set to `true` to add entity metadata to chunks.
- `EMBED_MODEL` – default embedding provider.
- `EMBED_MODEL_MAP` – JSON mapping of document types to models.
- `SBERT_MODEL` – SentenceTransformer model path or name.
- `OPENAI_EMBED_MODEL` – embedding model for OpenAI.
- `COHERE_API_KEY` – API key for Cohere embeddings.

### Vector DB

- `MILVUS_HOST` / `MILVUS_PORT` – Milvus server connection.
- `MILVUS_COLLECTION` – target collection name.
- `MILVUS_UPSERT` – upsert behaviour for inserts.
- `TOP_K` – default number of search results.
- `MILVUS_INDEX_PARAMS` – JSON index settings.
- `MILVUS_METRIC_TYPE` – distance metric for embeddings.
- `MILVUS_SEARCH_PARAMS` – JSON search parameters.

### RAG Retrieval

 - `VECTOR_SEARCH_FUNCTION` – ARN or name of the search Lambda. Set this to
   `VectorSearchFunctionArn` for pure similarity search or
   `HybridSearchFunctionArn` to enable keyword filtering.
- `SUMMARY_ENDPOINT` – optional summarization service URL.
- `CONTENT_ENDPOINT` – endpoint for content extraction.
- `ENTITIES_ENDPOINT` – endpoint for entity extraction.
- `ROUTELLM_ENDPOINT` – LLM router URL.
- `EMBED_MODEL` / `SBERT_MODEL` – embedding configuration.
- `OPENAI_EMBED_MODEL` – OpenAI model name.
- `COHERE_API_KEY` – Cohere API key.

### LLM Router and Invocation

- `BEDROCK_OPENAI_ENDPOINTS` – comma‑separated Bedrock endpoints.
- `BEDROCK_API_KEY` – API key for Bedrock.
- `BEDROCK_TEMPERATURE`, `BEDROCK_NUM_CTX`, `BEDROCK_MAX_TOKENS`,
  `BEDROCK_TOP_P`, `BEDROCK_TOP_K`,
  `BEDROCK_MAX_TOKENS_TO_SAMPLE` – generation settings for Bedrock.
- `OLLAMA_ENDPOINTS` – comma‑separated URLs of Ollama servers.
- `OLLAMA_DEFAULT_MODEL` – default Ollama model name.
- `OLLAMA_NUM_CTX`, `OLLAMA_REPEAT_LAST_N`, `OLLAMA_REPEAT_PENALTY`,
  `OLLAMA_TEMPERATURE`, `OLLAMA_SEED`, `OLLAMA_STOP`,
  `OLLAMA_NUM_PREDICT`, `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P` –
  generation settings for Ollama.
- `PROMPT_COMPLEXITY_THRESHOLD` – word count before switching models.
- `HEURISTIC_ROUTER_CONFIG` – JSON rules for advanced routing.
- `LLM_INVOCATION_FUNCTION` – Lambda used to invoke the chosen backend.
- `STRONG_MODEL_ID` / `WEAK_MODEL_ID` – model identifiers for routing.

## Deployment

Deploy a service with `sam deploy --template-file services/<service>/template.yaml --stack-name <name>` and provide any required parameters. See each service's README for details.

## Documentation

Additional documentation is available in the `docs/` directory:

- [docs/idp_output_format.md](docs/idp_output_format.md)
- [docs/router_configuration.md](docs/router_configuration.md)
- [docs/summarization_workflow.md](docs/summarization_workflow.md)
- [docs/knowledge_rag_usage.md](docs/knowledge_rag_usage.md)
- [docs/event_schemas.md](docs/event_schemas.md)
