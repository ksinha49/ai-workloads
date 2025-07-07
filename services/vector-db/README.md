# Vector DB Service

This service exposes a unified Lambda API for managing vector data in
Milvus or Elasticsearch. Operations are routed through a lightweight
proxy that dispatches requests based on the `storage_mode` field in the
payload.

## Lambdas

- **proxy/vector_db_proxy_lambda.py** – entry point used by other
  services. It forwards requests to the Milvus or Elasticsearch handler
  depending on the selected backend.
- **milvus_handler_lambda.py** – implements collection management and
  search operations for Milvus.
- **elastic_search_handler_lambda.py** – implements index operations for
  Elasticsearch.
- **jobs/cleanup_ephemeral_lambda.py** – scheduled job that drops
  ephemeral Milvus collections listed in DynamoDB.

## API

All handler functions expect an `operation` field describing the action.
The following operations are available:

- `insert` – add vectors with optional metadata.
- `delete` – remove vectors by ID.
- `update` – update embeddings or metadata.
- `create` / `drop` – manage Milvus collections.
- `search` – similarity search.
- `hybrid-search` – similarity search filtered by keywords.
- `create-index` / `drop-index` – manage Elasticsearch indices.

The proxy chooses the backend using `storage_mode` in the event. When not
provided it falls back to the `DEFAULT_VECTOR_DB_BACKEND` environment
variable (`milvus` by default).

### Ephemeral storage mode

Collections created for short‑lived experiments can be marked as
*ephemeral*. Their names are written to the DynamoDB table referenced by
`EPHEMERAL_TABLE`. The `cleanup_ephemeral_lambda.py` job runs daily and
drops any expired collections from Milvus before removing the table
entries.

To create an ephemeral collection send a `create` request with the
`ephemeral` flag set to `true` and an `expires_at` UNIX timestamp:

```json
{
  "operation": "create",
  "collection_name": "tmp123",
  "dimension": 768,
  "ephemeral": true,
  "expires_at": 1700000000
}
```

## Environment variables

`template.yaml` exposes several parameters that become Lambda environment
variables:

- `DEFAULT_VECTOR_DB_BACKEND` – fallback backend when `storage_mode` is not set.
- `MILVUS_HOST` / `MILVUS_PORT` – address of the Milvus server.
- `MILVUS_COLLECTION` – default collection name.
- `ELASTICSEARCH_URL` – endpoint for the Elasticsearch backend.
- `ELASTICSEARCH_INDEX_PREFIX` – prefix for index names.
- `EPHEMERAL_TABLE` – DynamoDB table for ephemeral collections.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/vector-db/template.yaml
```

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
