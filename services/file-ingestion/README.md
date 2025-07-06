# File Ingestion Service

This service copies uploaded files to the IDP bucket and polls for text extraction results. It provides two Lambdas and a Step Function.

- **file-processing-lambda** – `src/file_processing_lambda.py` copies the uploaded file to `IDP_BUCKET/RAW_PREFIX`.
  The Lambda validates the copy by comparing the source and destination objects'
  `ETag` and `ContentLength` before tagging the original object with
  `pending-delete=true`.
- **file-processing-status-lambda** – `src/file_processing_status_lambda.py` checks S3 for the text document and updates `fileupload_status`.
- **FileIngestionStateMachine** – orchestrates both Lambdas and then triggers the ingestion workflow.
- **pending-delete-cleanup-lambda** – `src/pending_delete_cleanup_lambda.py` runs daily to remove objects tagged
  `pending-delete=true` once they are older than `DeleteAfterDays`.

The dataclasses `FileProcessingEvent` and `ProcessingStatusEvent` used by these
Lambdas are provided by the shared `common-utils` layer so they can be imported
simply with ``from models import FileProcessingEvent``.

## External Callers

The `FileIngestionStateMachine` is invoked by other stacks before they begin
processing a document. The summarization state machine starts this workflow to
prepare files for summarization, and the knowledge-base ingestion service reuses
it when uploading documents to the vector database.

## Parameters

`template.yaml` exposes these parameters:

- `IDPBucketName` – name of the IDP bucket.
- `IDPRawPrefix` – prefix within that bucket where the uploaded file is copied.
- `IngestionStateMachineArn` – ARN of the ingestion Step Function started after the file is ready.
- `StatusPollSeconds` – wait time between polling for file status.
- `FileIngestionStateMachineIAMRole` – IAM role used by the Step Function.
- `DeleteAfterDays` – number of days to keep source files tagged
  `pending-delete=true` before cleanup.
- `CleanupBuckets` – comma separated list of buckets containing the tagged
  objects.

Provide networking and Lambda role parameters (subnets, security groups, role ARN) as with other services.

### Environment variables

The scheduled cleanup Lambda reads these values from the environment or
Parameter Store:

- `DELETE_AFTER_DAYS` – retention period for tagged objects.
- `CLEANUP_BUCKETS` – comma separated list of buckets scanned for pending
  deletes.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/file-ingestion/template.yaml \
  --stack-name file-ingestion \
  --parameter-overrides \
    IDPBucketName=<bucket> \
    IDPRawPrefix=<prefix> \
    IngestionStateMachineArn=<arn> \
    DeleteAfterDays=1 \
    CleanupBuckets=<bucket>
```

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
