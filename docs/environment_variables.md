# Environment Variables

Each service loads its configuration from Parameter Store or the Lambda environment. Values are retrieved using the ``get_config`` helper so every variable may be supplied via SSM under the environment prefix. The table below summarises the most common variables.

### Core services

- `AWS_ACCOUNT_NAME` – scopes stack resources for the file‑assembly, zip‑processing and summarization stacks.
- `SSM_CACHE_TABLE` – DynamoDB table used by the SSM caching layer.

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
- `PDF_RAW_PREFIX`, `PDF_PAGE_PREFIX`, `PDF_TEXT_PAGE_PREFIX`, `PDF_SCAN_PAGE_PREFIX`, `TEXT_PAGE_PREFIX` – internal prefixes used by the pipeline.
- `DPI` – image resolution for OCR.
- `EDI_SEARCH_API_URL` / `EDI_SEARCH_API_KEY` – external API for IDP output.

### RAG Ingestion

- `CHUNK_SIZE` – characters per chunk.
- `CHUNK_OVERLAP` – overlap between chunks.
- `CHUNK_STRATEGY` – chunking strategy (`simple` or `universal`).
- `CHUNK_STRATEGY_MAP` – JSON mapping of document types to strategies.
- `EXTRACT_ENTITIES` – set to `true` to add entity metadata to chunks.
- `EMBED_MODEL` – default embedding provider.
- `EMBED_MODEL_MAP` – JSON mapping of document types to models.
- `SBERT_MODEL` – SentenceTransformer model path or name.
- `OPENAI_EMBED_MODEL` – embedding model for OpenAI.
- `COHERE_SECRET_NAME` – name or ARN of the Cohere API key secret.

### Vector DB

- `MILVUS_HOST` / `MILVUS_PORT` – Milvus server connection.
- `MILVUS_COLLECTION` – target collection name.
- `MILVUS_UPSERT` – upsert behaviour for inserts.
- `TOP_K` – default number of search results.
- `MILVUS_INDEX_PARAMS` – JSON index settings.
- `MILVUS_METRIC_TYPE` – distance metric for embeddings.
- `MILVUS_SEARCH_PARAMS` – JSON search parameters.

### RAG Retrieval

- `VECTOR_SEARCH_FUNCTION` – ARN or name of the search Lambda. Set this to `VectorSearchFunctionArn` for pure similarity search or `HybridSearchFunctionArn` to enable keyword filtering.
- `SUMMARY_ENDPOINT` – optional summarization service URL.
- `CONTENT_ENDPOINT` – endpoint for content extraction.
- `ENTITIES_ENDPOINT` – endpoint for entity extraction.
- `ROUTELLM_ENDPOINT` – LLM router URL.
- `EMBED_MODEL` / `SBERT_MODEL` – embedding configuration.
- `OPENAI_EMBED_MODEL` – OpenAI model name.
- `COHERE_SECRET_NAME` – name or ARN of the Cohere API key secret.
- `RERANK_FUNCTION` – optional Lambda used to re-rank search results.
- `RERANK_PROVIDER` – provider for the re-ranking model.
- `NVIDIA_SECRET_NAME` – name or ARN of the NVIDIA API key secret.
- `VECTOR_SEARCH_CANDIDATES` – number of search results retrieved before re-ranking.

### LLM Router and Invocation

- `BEDROCK_OPENAI_ENDPOINTS` – comma‑separated Bedrock endpoints.
- `BEDROCK_SECRET_NAME` – name or ARN of the Bedrock API key secret.
- `BEDROCK_TEMPERATURE`, `BEDROCK_NUM_CTX`, `BEDROCK_MAX_TOKENS`, `BEDROCK_TOP_P`, `BEDROCK_TOP_K`, `BEDROCK_MAX_TOKENS_TO_SAMPLE` – generation settings for Bedrock.
- `OLLAMA_ENDPOINTS` – comma‑separated URLs of Ollama servers.
- `OLLAMA_DEFAULT_MODEL` – default Ollama model name.
- `OLLAMA_NUM_CTX`, `OLLAMA_REPEAT_LAST_N`, `OLLAMA_REPEAT_PENALTY`, `OLLAMA_TEMPERATURE`, `OLLAMA_SEED`, `OLLAMA_STOP`, `OLLAMA_NUM_PREDICT`, `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P` – generation settings for Ollama.
- `ALLOWED_BACKENDS` – comma-separated list of permitted router backends.
- `PROMPT_COMPLEXITY_THRESHOLD` – word count before switching models.
- `HEURISTIC_ROUTER_CONFIG` – JSON rules for advanced routing.
- `LLM_INVOCATION_FUNCTION` – Lambda used to invoke the chosen backend.
- `STRONG_MODEL_ID` / `WEAK_MODEL_ID` – model identifiers for routing.
- `CLASSIFIER_MODEL_ID` – optional model used to classify prompts when predictive routing is enabled.

### Knowledge Base

- `FILE_INGESTION_STATE_MACHINE_ARN` – ARN of the file ingestion workflow started before the main ingestion state machine.
- `STATE_MACHINE_ARN` – ARN of the main ingestion workflow.
- `SUMMARY_QUEUE_URL` – queue URL consumed by the query Lambda.
- `KNOWLEDGE_BASE_NAME` – optional name tag.
- `DELETE_AFTER_DAYS` – retention days for source files tagged `pending-delete=true`.
- `CLEANUP_BUCKETS` – comma separated list of buckets scanned by the cleanup Lambda.

### Sensitive Info Detection

- `NER_LIBRARY` – NLP library to use (`spacy` or `hf`).
- `SPACY_MODEL` – spaCy model name.
- `HF_MODEL` – HuggingFace model name.
- `MEDICAL_MODEL` – model when `domain` is `Medical`.
- `LEGAL_MODEL` – model when `domain` is `Legal`.
- `REGEX_PATTERNS` – JSON map of custom regex detectors.
- `LEGAL_REGEX_PATTERNS` – JSON map of legal-specific patterns.

### Entity Tokenization

- `TOKEN_TABLE` – DynamoDB table for entity/token mappings.
- `TOKEN_PREFIX` – Prefix prepended to generated tokens.
- `TOKEN_SALT` – Optional salt for deterministic hashing.

### Text Anonymization

- `ANON_MODE` – how to anonymize text: `mask`, `pseudo` or `token`.
- `TOKEN_API_URL` – endpoint for tokenization when using token mode.
- `ANON_TIMEOUT` – seconds before falling back to `[REMOVED]`.

### EFS Storage

- `EFS_DEPENDENCY_PATH` – mount location containing Python packages installed on EFS.
- `MODEL_EFS_PATH` – base directory on EFS holding ML model files.

Both variables may also be supplied via Parameter Store using the same names.

See [services/text-anonymization/README.md](../services/text-anonymization/README.md) for more details.
