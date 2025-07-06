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

All handler functions expect an `operation` field describing the action
(`insert`, `delete`, `update`, `create`, `drop`, `search`,
`hybrid-search`, `create-index`, `drop-index`). Payload parameters match
those of the previous individual Lambdas.

The proxy chooses the backend using `storage_mode` in the event. When not
provided it falls back to the `DEFAULT_VECTOR_DB_BACKEND` environment
variable (`milvus` by default).

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
