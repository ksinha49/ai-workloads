# Event Schemas

This document lists the minimal JSON schema fragments for the events consumed by the key Lambda functions and the structure of their API payloads.

## S3 Event

The IDP Lambdas are triggered by standard S3 events. Each event contains a list of records identifying the bucket and object key.

```json
{
  "type": "object",
  "properties": {
    "Records": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "s3": {
            "type": "object",
            "properties": {
              "bucket": {
                "type": "object",
                "properties": {"name": {"type": "string"}}
              },
              "object": {
                "type": "object",
                "properties": {"key": {"type": "string"}}
              }
            },
            "required": ["bucket", "object"]
          }
        },
        "required": ["s3"]
      }
    }
  },
  "required": ["Records"]
}
```

## File Assembly Payload

```json
{
  "organic_bucket": "source-bucket",
  "organic_bucket_key": "extracted/doc.pdf",
  "summary_bucket_name": "summary-bucket",
  "summary_bucket_key": "summary/doc.pdf"
}
```

## LLM Router/Invocation Payload

```json
{
  "prompt": "Explain AI services",
  "backend": "ollama",
  "model": "llama2"
}
```

## File Ingestion Payload

```json
{
  "file": "s3://bucket/path/doc.pdf",
  "collection_name": "my-collection",
  "ingest_params": {"chunk_size": 1000},
  "retrieve_params": {"top_k": 5},
  "router_params": {"backend": "bedrock"},
  "llm_params": {"model": "llama2"}
}
```

## Processing Status Payload

```json
{
  "document_id": "abc123",
  "collection_name": "my-collection"
}
```

## Summarization Event

Optionally include an `output_format` property to select `pdf`, `docx`, `json` or `xml` output.

```json
{
  "statusCode": 200,
  "organic_bucket": "source-bucket",
  "organic_bucket_key": "extracted/doc.pdf",
  "collection_name": "my-collection",
  "summaries": [{"Title": "Summary", "content": "text"}],
  "output_format": "pdf"
}
```

## Summarization Workflow Input

```json
{
  "body": {
    "prompts": [{"query": "Summarize", "Title": "Summary"}],
    "collection_name": "my-collection",
    "llm_params": {"system_prompt": "<prompt text>"}
  }
}
```

## Vector Search Payload

```json
{
  "embedding": [0.1, 0.2, 0.3],
  "top_k": 5,
  "collection_name": "my-collection",
  "department": "corp",
  "file_guid": "guid"
}
```

## RAG Summarization Payload

```json
{
  "collection_name": "my-collection",
  "query": "Explain AI",
  "retrieve_params": {"top_k": 5},
  "router_params": {"backend": "bedrock"},
  "llm_params": {"model": "llama2"}
}
```

## Knowledge Base Ingest Request

```json
{
  "text": "Document text",
  "collection_name": "my-collection",
  "docType": "pdf",
  "department": "sales",
  "team": "team1",
  "user": "alice"
}
```

## Knowledge Base Query Request

```json
{
  "collection_name": "my-collection",
  "query": "What is AI?",
  "file_guid": "guid",
  "department": "sales"
}
```
