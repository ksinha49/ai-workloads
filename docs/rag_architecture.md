# RAG Architecture Overview

This guide illustrates how the retrieval augmented generation components connect across services. It covers document ingestion, embedding creation, vector search and summarization.

## Components

- **rag-ingestion** – chunks documents and generates embeddings.
- **vector-db** – maintains Milvus collections used for semantic search.
- **knowledge-base** – stores metadata for ingested chunks and exposes `/kb/*` endpoints.
- **rag-retrieval** – performs vector search and orchestrates summarization with context.
- **summarization** – Step Function workflow that can call retrieval functions when creating summaries.

## End-to-End Flow

The ingestion services generate embeddings and store metadata. Retrieval functions later query the vector database and pass the results to the summarization stack.

```mermaid
sequenceDiagram
    participant Client
    participant Ingestion as rag-ingestion
    participant DB as vector-db
    participant KB as knowledge-base
    participant Retrieval as rag-retrieval
    participant Sum as summarization

    Client->>Ingestion: upload document
    Ingestion->>DB: store embeddings
    Ingestion->>KB: save chunk metadata
    Client->>Retrieval: query for context
    Retrieval->>DB: vector search
    Retrieval->>KB: filter by metadata
    Retrieval->>Sum: send top chunks
    Sum-->>Client: return summary
```

The summarization Step Function may invoke retrieval during its workflow to supply relevant context before generating the final response. Both ingestion and retrieval rely on the `vector-db` service to manage Milvus collections.
