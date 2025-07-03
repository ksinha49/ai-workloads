# Prompt Engine

The prompt engine is a lightweight Lambda that renders text templates stored in a DynamoDB table and forwards the result to the LLM router. Templates are addressed by a `prompt_id` and `version` so multiple revisions can be stored.

## DynamoDB Items

Entries in the table include at minimum the following attributes:

```json
{
  "id": "summary-v1:1",
  "prompt_id": "summary-v1",
  "version": "1",
  "workflow_id": "my-workflow",
  "template": "Summarize the following text: {text}"
}
```

The `id` combines `prompt_id` and `version` using a colon. Additional fields may be stored alongside the template text.

## Adding Templates

Insert new prompts with the standard DynamoDB `PutItem` API. Specify a unique `prompt_id` and increment the `version` when updating a template. Sample collections such as `file-summary-lambda/aps_prompts.json` can be loaded into the table using the AWS CLI:

```bash
aws dynamodb put-item \
  --table-name <PromptLibraryTable> \
  --item file://aps_prompts.json
```

## Invocation

Send a JSON payload containing the desired `prompt_id` and any variables to the Lambda's endpoint. The rendered prompt is forwarded to the router service and the response is returned unchanged:

```json
{"prompt_id": "summary-v1", "variables": {"text": "example content"}}
```

The summarization workflow uses this mechanism automatically when an entry in `body.prompts` specifies a `prompt_id`.
