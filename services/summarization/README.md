# Summarization Service

This stack orchestrates document summarization using Step Functions. It prepares
files via the file-ingestion workflow, loads prompts from the prompt engine and
invokes the RAG summarization Lambda in parallel for each prompt. Results are
assembled into a summary document.

- **load-prompts-lambda** – `src/load_prompts_lambda.py` fetches templates from
  the prompt engine.
- **summarize-worker-lambda** – `src/summarize_worker_lambda.py` calls the
  summarization Lambda and reports results back to the state machine.
- **file-summary-lambda** – `src/file_summary_lambda.py` creates the final
  document. Helper functions are exposed for PDF generation.

The `template.yaml` defines the SQS queue, Lambda functions and a single Step
Function.

* **SummarizationWorkflow** – starts at `LoadPrompts` and runs the summarization
  tasks. Messages posted to `SummaryQueue` trigger this workflow.
  Failed messages are sent to `SummaryDLQ` after five unsuccessful deliveries.

The payload passed to `file-summary-lambda` may include an optional
`output_format` field which determines the format of the summary file.
Accepted values are `pdf`, `docx`, `json` and `xml`. When omitted the service
produces a PDF. The full schema is documented in
[`docs/event_schemas.md`](../../docs/event_schemas.md#summarization-event).

The state machine ARN is exported as `SummarizationWorkflowArn` for use by other
stacks.

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
