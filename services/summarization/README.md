# Summarization Service

This service orchestrates document processing and summarization. The Step
Function defined in `template.yaml` begins by invoking the
`FileIngestionStateMachine` from the **file-ingestion** stack. Once the uploaded
file has been prepared, the workflow runs the prompts, generates summaries and
merges them with the original PDF using the **file-assembly** service. The same
state machine is also triggered from the **knowledge-base** ingestion pipeline
when uploading new documents.

Details of the state machine, including the parallel `run_prompts` map state, are documented in [docs/summarization_workflow.md](../../docs/summarization_workflow.md).

## Environment variables

The SAM template exposes a few parameters which become environment variables for the Lambdas:

- `FileIngestionStateMachineArn` – ARN of the file ingestion workflow invoked at the start of the state machine.
- `RagSummaryFunctionArn` – ARN of the RAG retrieval summary Lambda.
- `FileAssembleFunctionArn` – ARN of the file assembly Lambda used to merge summaries with the original PDF.
- `RunPromptsConcurrency` – number of prompts processed in parallel by the `run_prompts` map state.
- The service now provisions an SQS queue consumed by a worker Lambda. `RunPromptsConcurrency` controls how many messages are sent in parallel.


## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/summarization/template.yaml \
  --stack-name summarization \
  --parameter-overrides \
    FileIngestionStateMachineArn=<arn> \
    RagSummaryFunctionArn=<arn> \
    FileAssembleFunctionArn=<arn> \
    RunPromptsConcurrency=10
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

