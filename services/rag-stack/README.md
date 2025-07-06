# RAG Stack Service

This service consolidates the ingestion and retrieval components used for Retrieval Augmented Generation workflows. It bundles the text chunking and embedding Lambdas, the SQS worker that starts the ingestion Step Function and the summarization lambda that performs retrieval with context.

## Lambdas

- **text_chunk_lambda.py** – splits text into overlapping chunks and optionally extracts entities.
- **embed_lambda.py** – generates vector embeddings for each chunk.
- **ingestion_worker_lambda.py** – dequeues messages and starts the ingestion workflow.
- **retrieval_lambda.py** – searches the vector database and forwards the request to the LLM router.
- **extract_content_lambda.py** – fetches structured content from a content service using search context.
- **extract_entities_lambda.py** – extracts entities by posting search context to an external service.
- **rerank_lambda.py** – reorders vector search matches using a rerank provider.

## Parameters and environment variables

`template.yaml` combines the parameters from the original services. Key settings include:

- `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNK_STRATEGY` – control chunking behaviour.
- `EMBED_MODEL`, `EMBED_MODEL_MAP` – default embedding model and overrides per document type.
- `STATE_MACHINE_ARN`, `QUEUE_URL` – configure the ingestion worker.
- `VECTOR_SEARCH_FUNCTION`, `RERANK_FUNCTION`, `ROUTELLM_ENDPOINT` – retrieval endpoints.

Refer to the template for the full list of parameters and their defaults.

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
