# RAG Retrieval Service

This service exposes several Lambda functions that retrieve text from a vector database and forward the results to downstream APIs for summarization or extraction.
The retrieval logic calls the search Lambda defined by the `VECTOR_SEARCH_FUNCTION` environment variable. Pointing this variable to the
`HybridSearchFunctionArn` exported by the vector‑db stack switches from pure vector similarity search to hybrid search with keyword filtering.

## Lambdas and API Endpoints

- **summarize-with-context-lambda/app.py** – `/summarize`
  - Searches for relevant text, optionally re-ranks the matches and forwards the request through the LLM router.
- **extract-content-lambda/app.py** – `/extract-content`
  - Calls an external content extraction service with the query and retrieved context.
- **extract-entities-lambda/app.py** – `/extract-entities`
  - Sends the query and context to an entity extraction API.
- **rerank-lambda/app.py** – _no direct API_
  - Re-ranks search results using a cross-encoder model.

## Environment variables

- `VECTOR_SEARCH_FUNCTION` – ARN or name of the search Lambda. Set this to `VectorSearchFunctionArn` for pure similarity search or `HybridSearchFunctionArn` to include keyword filtering.
- `RERANK_FUNCTION` – optional Lambda used to re-rank search results.
- `SUMMARY_ENDPOINT` – optional HTTP endpoint for a summarization service.
- `CONTENT_ENDPOINT` – URL used by `extract-content`.
- `ENTITIES_ENDPOINT` – URL used by `extract-entities`.
- `ROUTELLM_ENDPOINT` – base URL for the LLM router.
- `EMBED_MODEL` – default embedding provider (`sbert` by default).
- `SBERT_MODEL` – SentenceTransformer model name or S3 path.
- `OPENAI_EMBED_MODEL` – embedding model name for OpenAI.
- `COHERE_API_KEY` – API key when using Cohere embeddings.
- `CROSS_ENCODER_MODEL` – model name or S3 path for the cross-encoder.
- `VECTOR_SEARCH_CANDIDATES` – number of candidates retrieved before re-ranking.

Values can be stored in Parameter Store and loaded with the shared `get_config` helper.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/rag-retrieval/template.yaml \
  --stack-name rag-retrieval \
  --parameter-overrides \
    VectorSearchFunctionArn=<arn> \
    RouteLlmEndpoint=<router-url> \
    SummaryEndpoint=<summary-url> \
    ContentEndpoint=<content-url> \
    EntitiesEndpoint=<entities-url>
```

The summarization Lambda forwards requests through the LLM router defined by
`ROUTELLM_ENDPOINT`. Configure any router specific variables as described in
[../../docs/router_configuration.md](../../docs/router_configuration.md).
