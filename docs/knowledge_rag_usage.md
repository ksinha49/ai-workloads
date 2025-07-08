# Knowledge and RAG Usage Guide

This guide covers recommended practices for ingesting documents into the knowledge base and retrieving context using the RAG components.

## Ingesting Documents

1. Use the `/kb/ingest` endpoint provided by the **knowledge-base** service or invoke the `ingest-lambda` function directly.
2. Always include `collection_name` beginning with `kb_` to specify the target collection where embeddings should be stored. The backend defaults to persistent storage but can be changed by setting `KB_VECTOR_DB_BACKEND`.
3. Include optional metadata fields such as `department`, `team`, `user`,
   `entities`, `file_guid` and `file_name` in your request. These values are
   stored with each chunk along with a `hash_key` of the text so you can trace or
   filter results.
4. Large files should be processed by the IDP pipeline first and then passed to the ingestion Step Function from `rag-stack`.
5. Tune the chunk size and overlap through the `CHUNK_SIZE` and `CHUNK_OVERLAP` parameters in Parameter Store to balance retrieval accuracy and cost.

## Querying the Knowledge Base

1. Use `/kb/query` to search the indexed documents. Provide natural language queries and optionally pass the same metadata fields (`department`, `team`, `user`, `entities`) to narrow results.
2. Specify the same `collection_name` used during ingestion so the search runs against the correct collection. Provide a `file_guid` to limit results to chunks from a single document. Set `storage_mode` to `elastic` when querying Elasticsearch.
3. The query Lambda calls the summarization with context function from the `rag-stack` stack. Configure `VECTOR_SEARCH_FUNCTION` to `HybridSearchFunctionArn` for keyword filtering in addition to vector similarity.
4. Enable the re-rank Lambda when higher quality ordering of results is required. Set `RERANK_FUNCTION` in the retrieval stack to the ARN of `rerank-lambda`.
5. Summaries returned from `/kb/query` come from the LLM Gateway. Adjust router settings as documented in [docs/router_configuration.md](router_configuration.md) to experiment with different models.

## Optimizing for Quality

- Index clean text. Remove boilerplate and irrelevant sections before ingestion to avoid diluting search results.
- Consider storing frequently asked questions or curated snippets separately to guarantee consistent answers.
- Monitor search metrics such as hit rate and latency. Adjust chunk sizes or the embedding model if results are poor.
- Use `department`, `team` and `user` metadata to isolate knowledge for different groups so that sensitive information is not returned to unauthorized queries.

By following these guidelines you can get the most out of the knowledge base and RAG retrieval features within this repository.
