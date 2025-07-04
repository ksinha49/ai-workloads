# RAG Retrieval Service

This service exposes several Lambda functions that retrieve text from a vector database and forward the results to downstream APIs for summarization or extraction.
The retrieval logic calls the search Lambda defined by the `VECTOR_SEARCH_FUNCTION` environment variable. Pointing this variable to the
`HybridSearchFunctionArn` exported by the vector‑db stack switches from pure vector similarity search to hybrid search with keyword filtering.

## Lambdas and API Endpoints

- **summarize-with-context-lambda/app.py** – `/summarize`
  - Searches for relevant text, optionally re-ranks the matches and forwards the request through the LLM router.
  - Triggered by messages on the SQS queue configured for the knowledge base service.
  - The event payload must include ``collection_name`` to target a specific Milvus collection.
- **extract-content-lambda/app.py** – `/extract-content`
  - Calls an external content extraction service with the query and retrieved context.
- **extract-entities-lambda/app.py** – `/extract-entities`
  - Sends the query and context to an entity extraction API.
- **rerank-lambda/app.py** – _no direct API_
  - Re-ranks search results using a configurable provider.

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
 - `COHERE_SECRET_NAME` – name or ARN of the Cohere API key secret.
- `CROSS_ENCODER_MODEL` – model name or S3 path for the cross-encoder.
- `CROSS_ENCODER_EFS_PATH` – local path to load the cross encoder from an
  attached EFS volume.
- `RERANK_PROVIDER` – rerank provider (`huggingface`, `cohere` or `nvidia`).
- `NVIDIA_SECRET_NAME` – name or ARN of the NVIDIA API key secret.
- `VECTOR_SEARCH_CANDIDATES` – number of candidates retrieved before re-ranking.

Values can be stored in Parameter Store and loaded with the shared `get_config` helper.

## Mounting an EFS access point

To keep the cross encoder available between invocations, mount an EFS
access point to the re-rank Lambda and point `CROSS_ENCODER_EFS_PATH`
to the model on that file system.

1. Create an EFS file system and access point.
2. Add a `FileSystemConfigs` block to `RerankFunction` in
   `template.yaml`:

   ```yaml
   RerankFunction:
     Type: AWS::Serverless::Function
     Properties:
       FileSystemConfigs:
         - Arn: arn:aws:elasticfilesystem:<region>:<account-id>:access-point/<ap-id>
           LocalMountPath: /mnt/models
   ```
3. Copy the cross encoder to `/mnt/models` and set
   `CROSS_ENCODER_EFS_PATH` accordingly.

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
