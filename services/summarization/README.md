# Summarization Service

This service orchestrates file ingestion and summarization. The Step Function defined in `template.yaml` first invokes the **FileIngestionStateMachine** from the separate file ingestion service, then generates summaries and finally merges them back with the original PDF.

It invokes two Lambdas from this package:

- **file-summary** – receives pre-generated summaries, creates a summary PDF and uploads the merged result to S3.
- **summarize-worker** – dequeues summarization tasks and sends results back to the Step Function.

Details of the state machine, including the parallel `run_prompts` map state, are documented in [docs/summarization_workflow.md](../../docs/summarization_workflow.md).

## Environment variables

The SAM template exposes a few parameters which become environment variables for the Lambdas:

- `FileIngestionStateMachineArn` – ARN of the file ingestion workflow invoked at the start of the state machine.
- `RagSummaryFunctionArn` – ARN of the RAG retrieval summary Lambda used by `file-summary`.
- `RunPromptsConcurrency` – number of prompts processed in parallel by the `run_prompts` map state.
- `StatusPollSeconds` – number of seconds the Step Function waits before polling for upload status again.
- The service now provisions an SQS queue consumed by a worker Lambda. `RunPromptsConcurrency` controls how many messages are sent in parallel.

Tuning `StatusPollSeconds` controls how frequently the workflow checks for IDP completion.  Lower values reduce latency but increase state machine executions.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/summarization/template.yaml \
  --stack-name summarization \
  --parameter-overrides \
    FileIngestionStateMachineArn=<arn> \
    RagSummaryFunctionArn=<arn> \
    RunPromptsConcurrency=10 \
    StatusPollSeconds=200
```

The Step Function definition and Lambda code are located in this directory.  See the root `README.md` for additional context.

## Scaling the Worker

Queued messages are processed by `summarize-worker-lambda`. To increase
throughput raise the Lambda's reserved concurrency or adjust the queue event
batch size in `template.yaml`. Lowering these values reduces concurrency and
costs.

## `collection_name`

Execution inputs must include a ``collection_name`` value when invoking the
summarization service. The state machine propagates this value through each
step so the retrieval service can search the specified Milvus collection.
If ``collection_name`` is omitted, the workflow returns a
``400`` response and the Step Function execution fails.

