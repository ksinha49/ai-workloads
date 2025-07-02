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
