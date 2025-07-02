# Vector DB Service

This service manages Milvus collections and provides simple search Lambdas. It consists of the following functions:

- **milvus-create-lambda/app.py** – create a Milvus collection if it does not exist
- **milvus-drop-lambda/app.py** – drop the current Milvus collection
- **milvus-insert-lambda/app.py** – insert embeddings into the collection
- **milvus-delete-lambda/app.py** – delete embeddings by ID
- **milvus-update-lambda/app.py** – update existing embeddings
- **vector-search-lambda/app.py** – query the collection by vector
- **hybrid-search-lambda/app.py** – vector search with optional keyword filtering
- **es-create-lambda/app.py** – create an Elasticsearch index
- **es-drop-lambda/app.py** – delete the Elasticsearch index
- **es-insert-lambda/app.py** – insert documents into Elasticsearch
- **es-delete-lambda/app.py** – delete Elasticsearch documents by ID
- **es-update-lambda/app.py** – update Elasticsearch documents
- **es-search-lambda/app.py** – search the Elasticsearch index
- **es-hybrid-search-lambda/app.py** – vector + keyword search on Elasticsearch

## Parameters and environment variables

`template.yaml` exposes several required parameters. Each one becomes an environment variable for all Lambdas in this stack:

| Parameter        | Environment variable | Description                  |
| ---------------- | -------------------- | ---------------------------- |
| `MilvusHost`     | `MILVUS_HOST`        | Milvus server hostname or IP |
| `MilvusPort`     | `MILVUS_PORT`        | Milvus service port          |
| `MilvusCollection` | `MILVUS_COLLECTION` | Target collection name       |
| `ElasticsearchUrl` | `ELASTICSEARCH_URL` | Elasticsearch endpoint       |
| `ElasticsearchIndexPrefix` | `ELASTICSEARCH_INDEX_PREFIX` | Prefix for index names |

Values are typically stored in AWS Systems Manager Parameter Store and passed to `sam deploy`.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/vector-db/template.yaml
```

## Outputs

The stack exports the ARNs of the search functions:

- `VectorSearchFunctionArn` – ARN of the Milvus vector search Lambda
- `HybridSearchFunctionArn` – ARN of the Milvus hybrid search Lambda
- `EsSearchFunctionArn` – ARN of the Elasticsearch search Lambda
- `EsHybridSearchFunctionArn` – ARN of the Elasticsearch hybrid search Lambda

These values are referenced by other services. For example, `rag-retrieval`
sets the `VECTOR_SEARCH_FUNCTION` environment variable to one of these ARNs to
toggle between pure vector search and hybrid search.
