# RAG Stack Service

This service consolidates the ingestion and retrieval components used for Retrieval Augmented Generation workflows. It bundles the text chunking and embedding Lambdas, the SQS worker that starts the ingestion Step Function and the retrieval Lambda that assembles context and forwards requests to RouteLLM.

## Lambdas

- **text_chunk_lambda.py** – splits text into overlapping chunks and optionally extracts entities.
- **embed_lambda.py** – generates vector embeddings for each chunk.
- **ingestion_worker_lambda.py** – dequeues messages and starts the ingestion workflow.
- **retrieval_lambda.py** – searches the vector database, assembles search context and forwards the request to the LLM router. The router's response is returned under a `result` key.
- **extract_content_lambda.py** – fetches structured content from a content service using search context.
- **extract_entities_lambda.py** – extracts entities by posting search context to an external service.
- **rerank_lambda.py** – reorders vector search matches using a rerank provider.

## Parameters and environment variables

`template.yaml` defines parameters for each Lambda that become environment variables.

### text_chunk_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `ChunkSize` | `CHUNK_SIZE` | Maximum characters per chunk. |
| `ChunkOverlap` | `CHUNK_OVERLAP` | Overlap between adjacent chunks. |
| `ChunkStrategy` | `CHUNK_STRATEGY` | `simple` or `universal` chunking. |
| `ChunkStrategyMap` | `CHUNK_STRATEGY_MAP` | JSON map of strategies by document type. |
| `ExtractEntities` | `EXTRACT_ENTITIES` | Set to `true` to add entity metadata. |

### embed_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `EmbedModel` | `EMBED_MODEL` | Default embedding provider. |
| `EmbedModelMap` | `EMBED_MODEL_MAP` | JSON mapping of document types to models. |
| `SbertModel` | `SBERT_MODEL` | SentenceTransformer model path or name. |
| `OpenAiEmbedModel` | `OPENAI_EMBED_MODEL` | OpenAI embedding model. |
| `CohereSecretName` | `COHERE_SECRET_NAME` | Name or ARN of the Cohere API key secret. |
| `ModelEfsPath` | `MODEL_EFS_PATH` | Base directory for models on EFS. |

### ingestion_worker_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `StateMachineArn` | `STATE_MACHINE_ARN` | ARN of the ingestion workflow. |
| `QueueUrl` | `QUEUE_URL` | URL of the ingestion queue. |

### retrieval_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `VectorSearchFunctionArn` | `VECTOR_SEARCH_FUNCTION` | Lambda used for vector search. |
| `RerankFunctionArn` | `RERANK_FUNCTION` | Optional rerank Lambda. |
| `VectorSearchCandidates` | `VECTOR_SEARCH_CANDIDATES` | Number of search results to retrieve. |
| `RouteLlmEndpoint` | `ROUTELLM_ENDPOINT` | URL for forwarding requests to RouteLLM. |
| `CohereSecretName` | `COHERE_SECRET_NAME` | Name or ARN of the Cohere API key secret. |
| `EmbedModel` | `EMBED_MODEL` | Default embedding provider. |
| `SbertModel` | `SBERT_MODEL` | SentenceTransformer model path or name. |
| `OpenAiEmbedModel` | `OPENAI_EMBED_MODEL` | OpenAI embedding model. |
| `ModelEfsPath` | `MODEL_EFS_PATH` | Base directory for models on EFS. |

### extract_content_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `VectorSearchFunctionArn` | `VECTOR_SEARCH_FUNCTION` | Lambda used for vector search. |
| `ContentEndpoint` | `CONTENT_ENDPOINT` | External content service URL. |

### extract_entities_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `VectorSearchFunctionArn` | `VECTOR_SEARCH_FUNCTION` | Lambda used for vector search. |
| `EntitiesEndpoint` | `ENTITIES_ENDPOINT` | Entity extraction service URL. |
| `ReraiseErrors` | `RERAISE_ERRORS` | Set to `true` to propagate failures. |

### rerank_lambda

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `TopK` | `TOP_K` | Default number of search results. |
| `CrossEncoderModel` | `CROSS_ENCODER_MODEL` | HuggingFace cross‑encoder model. |
| `CrossEncoderEfsPath` | `CROSS_ENCODER_EFS_PATH` | Optional EFS path for the model. |
| `RerankProvider` | `RERANK_PROVIDER` | Selected rerank provider. |
| `CohereSecretName` | `COHERE_SECRET_NAME` | Name or ARN of the Cohere API key secret. |
| `NvidiaRerankEndpoint` | `NVIDIA_RERANK_ENDPOINT` | NVIDIA rerank service URL. |
| `NvidiaSecretName` | `NVIDIA_SECRET_NAME` | Name or ARN of the NVIDIA API key secret. |
| `ModelEfsPath` | `MODEL_EFS_PATH` | Base directory for models on EFS. |

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/rag-stack/template.yaml --stack-name rag-stack
```

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
