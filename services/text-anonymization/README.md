# Text Anonymization Service

This service provides a Lambda for removing sensitive information from text using masking, pseudonyms or tokenization.

## Lambda

- **anonymize-text-lambda/app.py** – anonymizes text based on entity spans.

## Parameters and environment variables

`template.yaml` exposes a few parameters which become environment variables for the Lambda:

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `AnonymizationMode` | `ANON_MODE` | `mask`, `pseudo` or `token`. |
| `TokenApiUrl` | `TOKEN_API_URL` | URL of the tokenization Lambda when using token mode. |
| `AnonymizationTimeout` | `ANON_TIMEOUT` | Seconds before falling back to `[REMOVED]`. |

## Example

Request body:

```json
{
  "text": "John works at Acme.",
  "entities": [
    {"text": "John", "type": "PERSON", "start": 0, "end": 4},
    {"text": "Acme", "type": "ORG", "start": 15, "end": 19}
  ]
}
```

Example response when using pseudonym mode:

```json
{
  "text": "Jane Doe works at Widget Corp.",
  "replacements": [
    {"text": "John", "type": "PERSON", "start": 0, "end": 4, "replacement": "Jane Doe"},
    {"text": "Acme", "type": "ORG", "start": 15, "end": 19, "replacement": "Widget Corp"}
  ]
}
```

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/text-anonymization/template.yaml --stack-name text-anonymization
```

The stack exports `AnonymizeTextFunctionArn` for use by other services.
