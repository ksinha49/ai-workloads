# RAG Ingestion Worker

This service dequeues ingestion requests from SQS and starts the
`IngestionStateMachine` defined by the **rag-ingestion** stack. It is a
lightweight bridge that allows other services to publish ingestion jobs without
invoking the Step Function directly.

## Environment variables

| Variable | Description |
|----------|-------------|
| `QUEUE_URL` | URL of the SQS queue containing ingestion requests. |
| `STATE_MACHINE_ARN` | ARN of the ingestion Step Function to start. |

Each SQS message should contain the same fields accepted by the
`knowledge-base` ingest API (for example `text`, `collection_name`, `docType`
and optional metadata). The worker simply forwards the message body as the Step
Function input.

## Deployment

Deploy with SAM:

```bash
sam deploy \
  --template-file services/rag-ingestion-worker/template.yaml \
  --stack-name rag-ingestion-worker \
  --parameter-overrides \
    AWSAccountName=<name> \
    IngestionStateMachineArn=<arn>
```

The stack provisions an SQS queue and a Lambda function subscribed to it.
`IngestionQueueUrl` is exported for other stacks to publish requests.

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
