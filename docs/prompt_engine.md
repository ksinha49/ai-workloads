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

### Sample DynamoDB View

Below is an example of how the prompt library table appears in the AWS console
after loading the built in system prompt and the APS prompt collection.  The
`template`/`query` columns are truncated for brevity.

#### System Prompt

| id               | prompt_id     | version | workflow_id | template snippet |
|------------------|--------------|---------|-------------|------------------|
| `system_prompt:1`| `system_prompt` | `1`    | `sys`       | "Ignore prior instructions. You..." |

#### APS Prompts

| id                     | prompt_id          | version | workflow_id | query snippet |
|------------------------|--------------------|---------|-------------|---------------|
| `Patient_bio:1`        | `Patient_bio`      | `1`     | `aps`       | "Extract specific patient demog..." |
| `Medical_Summary:1`    | `Medical_Summary`  | `1`     | `aps`       | "Please generate a detailed and..." |
| `Specialist:1`         | `Specialist`       | `1`     | `aps`       | "Review the provided APS docume..." |
| `Blood_Pressure:1`     | `Blood_Pressure`   | `1`     | `aps`       | "Please analyze the provided me..." |
| `BMI:1`                | `BMI`              | `1`     | `aps`       | "List all BMI records with corr..." |
| `Height_Weight:1`      | `Height_Weight`    | `1`     | `aps`       | "List all records of the patien..." |
| `Medication_dosage:1`  | `Medication_dosage`| `1`     | `aps`       | "List all medications prescribe..." |
| `Lab_Results:1`        | `Lab_Results`      | `1`     | `aps`       | "List all lab results, includin..." |
| `Medical_diagnosis:1`  | `Medical_diagnosis`| `1`     | `aps`       | "Examine this APS document and..." |

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
