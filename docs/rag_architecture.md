# RAG Architecture Overview

This guide illustrates how the retrieval augmented generation components connect across services. It covers document ingestion, embedding creation, vector search and summarization.

## Components

- **file-ingestion** – orchestrates text extraction and enqueues ingestion jobs.
- **idp** – Intelligent Document Processing pipeline used by file-ingestion for OCR and classification.
- **rag-stack** – chunks documents, generates embeddings and performs retrieval.
- **rag-stack-worker** – polls `IngestionQueue` and starts the ingestion workflow, moving failed messages to a DLQ. The queue URL is exported as `IngestionQueueUrl` for other stacks.
- **vector-db** – manages Milvus or Elasticsearch backends used for semantic search.
- **knowledge-base** – stores metadata for ingested chunks and exposes `/kb/*` endpoints.
- **summarization** – Step Function workflow that can call retrieval functions when creating summaries.

## End-to-End Flow

The ingestion services generate embeddings and store metadata. Retrieval functions later query the vector database and pass the results to the summarization stack.

```mermaid
sequenceDiagram
    participant Client
    participant FileIng as file-ingestion
    participant IDP as idp
    participant Queue as IngestionQueue
    participant Worker as rag-stack-worker
    participant Ingestion as rag-stack
    participant Queue as IngestionQueue
    participant Worker as rag-stack-worker
    participant DB as vector-db
    participant KB as knowledge-base
    participant Retrieval as rag-stack
    participant Sum as summarization

    Client->>FileIng: upload file
    FileIng->>IDP: text extraction
    IDP-->>FileIng: result
    FileIng-->>Queue: publish job
    Worker->>Queue: receive
    Worker->>Ingestion: start workflow
    Ingestion->>DB: store embeddings
    Ingestion->>KB: save chunk metadata
    Ingestion-->>Queue: publish job
    Worker->>Queue: receive
    Worker->>Ingestion: start workflow
    Client->>Retrieval: query for context
    Retrieval->>DB: vector search
    Retrieval->>KB: filter by metadata
    Retrieval->>Sum: send top chunks
    Sum-->>Client: return summary
```

The summarization Step Function may invoke retrieval during its workflow to supply
relevant context before generating the final response. Both ingestion and
retrieval rely on the `vector-db` service to manage vector database backends.

In a typical flow the `file-ingestion` Step Function copies the file to the IDP
bucket and waits until text extraction completes. After the IDP pipeline
produces the parsed document, `file-ingestion` publishes the ingestion
parameters to `IngestionQueue`. The `rag-stack-worker` Lambda dequeues these
messages and starts the `IngestionStateMachine`. Failed jobs are moved to a dead
letter queue and retried automatically using the `batchItemFailures` response
format.
