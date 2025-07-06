# Summarization Service

This stack orchestrates document summarization using Step Functions. It prepares
files via the file-ingestion workflow, loads prompts from the prompt engine and
invokes the RAG summarization Lambda in parallel for each prompt. Results are
assembled into a summary document.

- **load-prompts-lambda** – `src/load_prompts_lambda.py` fetches templates from
  the prompt engine.
- **summarize-worker-lambda** – `src/summarize_worker_lambda.py` calls the
  summarization Lambda and reports results back to the state machine.
- **summary-document-lambda** – `src/file_summary_lambda.py` assembles the
  final summary document. Helper functions are exposed for PDF generation.

The `template.yaml` defines the SQS queue, Lambda functions and two Step
Functions.

* **SummarizationWorkflow** – starts at `LoadPrompts` and runs the summarization
  tasks.
* **FileProcessingStepFunction** – invokes the file-ingestion workflow and then
  calls `SummarizationWorkflow` to generate the summary.

Both state machine ARNs are exported as `FileProcessingStepFunctionArn` and
`SummarizationWorkflowArn` for use by other stacks.

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
