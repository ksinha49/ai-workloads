# File Ingestion Service

This service copies uploaded files to the IDP bucket and polls for text extraction results. It provides two Lambdas and a Step Function.

- **file-processing-lambda** – copies the uploaded file to `IDP_BUCKET/RAW_PREFIX`.
- **file-processing-status-lambda** – checks S3 for the text document and updates `fileupload_status`.
- **FileIngestionStateMachine** – orchestrates both Lambdas and then triggers the ingestion workflow.

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

Provide networking and Lambda role parameters (subnets, security groups, role ARN) as with other services.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/file-ingestion/template.yaml \
  --stack-name file-ingestion \
  --parameter-overrides \
    IDPBucketName=<bucket> \
    IDPRawPrefix=<prefix> \
    IngestionStateMachineArn=<arn>
```
