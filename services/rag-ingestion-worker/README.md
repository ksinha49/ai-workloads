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

## Queue configuration

The stack provisions an `IngestionQueue` with a `VisibilityTimeout` of
`300` seconds. This value should be at least as long as the Lambda timeout
so that messages are not returned to the queue while they are still being
processed. You can change the timeout in `template.yaml` if ingestion jobs
regularly take longer.

For production deployments it is recommended to attach a dead letter queue
(DLQ) to `IngestionQueue` using an SQS `RedrivePolicy`. Messages that fail
repeatedly will then be moved to the DLQ for manual inspection instead of
being retried indefinitely.

## Failure handling and retries

`WorkerFunction` processes one message at a time (`BatchSize: 1`). If the
Step Function execution fails and the Lambda invocation raises an error, the
message remains on the queue and becomes visible again after the visibility
timeout, triggering a retry. Because messages are deleted only after
successful processing, the same payload is retried until it succeeds or
exceeds the maximum receives configured by any DLQ.

## Scaling the worker

AWS Lambda automatically scales the number of concurrent executions based on
the queue depth. To increase throughput you can raise the function's reserved
concurrency or use a larger batch size. Each invocation requires the
following environment variables:

- `QUEUE_URL` – URL of the SQS queue.
- `STATE_MACHINE_ARN` – ARN of the ingestion Step Function.

Adjusting reserved concurrency controls how many ingestion workflows may run
in parallel and therefore how quickly queued messages are drained.
