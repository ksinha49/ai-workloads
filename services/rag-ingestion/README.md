# RAG Ingestion Service

This service turns text documents produced by the IDP pipeline into vector embeddings and stores them in Milvus. It consists of two Lambda functions and a Step Function workflow.

- **text-chunk-lambda** – splits incoming text into overlapping chunks
- **embed-lambda** – generates vector embeddings for each chunk
- **Milvus functions** – handle insert, update, delete and collection management

## Ingestion Step Function

`IngestionStateMachine` orchestrates the ingestion workflow:

1. **TextChunk** – invokes `text-chunk-lambda` to split the input text
2. **Embed** – invokes `embed-lambda` to embed each chunk
3. **MilvusInsert** – calls the Milvus insert Lambda to store the embeddings

New JSON files uploaded under `TextDocPrefix` automatically trigger this state machine. The bucket name and prefix are provided as stack parameters.

Each chunk produced by `text-chunk-lambda` includes the originating `file_guid`
and `file_name`. Downstream services can use these fields to retrieve or filter
content for a specific document.

## Environment variables

The Lambdas read configuration from AWS Systems Manager Parameter Store or environment variables:

- `CHUNK_SIZE` – maximum characters per chunk (default `1000`)
- `CHUNK_OVERLAP` – overlap between successive chunks (default `100`)
- `EXTRACT_ENTITIES` – set to `true` to store entity metadata for each chunk
- `EMBED_MODEL` – default embedding model (`"sbert"`)
- `EMBED_MODEL_MAP` – JSON mapping of document types to models
- `SBERT_MODEL` – SentenceTransformer model path or name

Adjust these values in Parameter Store or when deploying the functions.

## Deployment

Deploy the stack with SAM using `services/rag-ingestion/template.yaml`. Provide the ARNs of the Milvus Lambdas from the `vector-db` stack:

```bash
sam deploy \
  --template-file services/rag-ingestion/template.yaml \
  --stack-name rag-ingestion \
  --parameter-overrides \
    BucketName=<bucket> \
    TextDocPrefix=<prefix> \
    MilvusInsertFunctionArn=<arn> \
    MilvusDeleteFunctionArn=<arn> \
    MilvusUpdateFunctionArn=<arn> \
    MilvusCreateCollectionFunctionArn=<arn> \
    MilvusDropCollectionFunctionArn=<arn>
```

The outputs include the ARNs of `text-chunk-lambda`, `embed-lambda` and the `IngestionStateMachine` for use in other stacks.
