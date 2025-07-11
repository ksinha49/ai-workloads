# Redaction Orchestrator Service

This service coordinates OCR extraction and redaction for uploaded documents. A
single Lambda function is triggered by S3 uploads or a REST endpoint and
performs the following steps:

1. **Copy to IDP** – the source file is copied to the IDP bucket so the OCR
   pipeline can process it.
2. **Wait for OCR output** – the Lambda polls S3 until the combined Markdown
   and optional hOCR files exist.
3. **Detect PII** – the plain text extracted from the document is sent to the
   anonymization service's `/detect-pii` endpoint.
4. **Invoke file redaction** – the original file, hOCR output and detected
   entities are forwarded to the file redaction Lambda.

Status updates may be written to a DynamoDB table when the
`REDACTION_STATUS_TABLE` environment variable is supplied.

## API Payload

When invoked through API Gateway the request body should contain a `file` field
with an `s3://` URI. Example:

```json
{
  "file": "s3://my-bucket/new/doc.pdf"
}
```

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/redaction/template.yaml \
  --stack-name redaction
```
