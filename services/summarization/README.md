# Summarization Service

This service provides an end‑to‑end workflow that copies a file to the IDP bucket, waits for text extraction, generates summaries and finally merges them back with the original PDF.

The workflow is orchestrated by an AWS Step Function defined in `template.yaml`.  It invokes three Lambdas in this package:

- **file-processing** – copies the uploaded document to `IDP_BUCKET/RAW_PREFIX` so the IDP pipeline can ingest it.
- **file-processing-status** – polls for the text document produced by the IDP pipeline and updates `fileupload_status` in the state machine.
- **file-summary** – receives pre-generated summaries, creates a summary PDF and uploads the merged result to S3.

Details of the state machine, including the parallel `run_prompts` map state, are documented in [docs/summarization_workflow.md](../../docs/summarization_workflow.md).

## Environment variables

The SAM template exposes a few parameters which become environment variables for the Lambdas:

- `IDPBucketName` – name of the IDP bucket.
- `IDPRawPrefix` – prefix within that bucket where the uploaded file is copied.
- `IngestionStateMachineArn` – ARN of the RAG ingestion state machine invoked after the file is available.
- `RagSummaryFunctionArn` – ARN of the RAG retrieval summary Lambda used by `file-summary`.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/summarization/template.yaml \
  --stack-name summarization \
  --parameter-overrides \
    IDPBucketName=<bucket> \
    IDPRawPrefix=<prefix> \
    IngestionStateMachineArn=<arn> \
    RagSummaryFunctionArn=<arn>
```

The Step Function definition and Lambda code are located in this directory.  See the root `README.md` for additional context.
