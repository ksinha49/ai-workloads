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
- `PromptEngineEndpoint` – optional URL of the prompt engine service used for templated prompts.


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
    RunPromptsConcurrency=10 \
    PromptEngineEndpoint=<engine-url>
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

## File GUID

A unique `file_guid` is generated during the file-processing step. This value flows through the ingestion workflow so each chunk and embedding can be traced back to the original document.

## Prompt templates

Each entry in `body.prompts` may specify a `prompt_id` that refers to a template
stored in the prompt engine. When present, the worker Lambda sends
`prompt_id` and an optional `variables` dictionary to the engine before invoking
the summarization logic. The engine renders the template and forwards it to the
LLM router, but the queue worker ignores the response – the original
``query`` value is still passed to ``RAG_SUMMARY_FUNCTION_ARN`` unchanged.

## `system_prompt`

Include model parameters under ``body.llm_params`` when starting a Step
Function execution. To supply a system prompt for the LLM add a
``system_prompt`` entry, e.g.:

```json
{
  "body": {
    "prompts": [
      {"query": "Summary query"}
    ],
    "llm_params": {
      "system_prompt": "<prompt text>"
    }
  }
}
```

An example prompt is available in
[`file-summary-lambda/system_prompt.json`](file-summary-lambda/system_prompt.json).
The queue worker passes ``llm_params`` to the ``llm-invocation`` Lambda which
forwards ``system_prompt`` to the selected backend.

