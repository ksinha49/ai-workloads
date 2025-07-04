# Text Anonymization Service

This service provides a Lambda function for anonymising text based on a list of entities.
Depending on configuration the function can mask entity spans, replace them with
synthetic values or call the tokenisation service.

- **Lambda**: `anonymize-text-lambda/app.py`

## Environment variables

`template.yaml` exposes the following variables used by the Lambda:

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `AnonymizationMode` | `ANON_MODE` | `mask`, `pseudo` or `token`. |
| `TokenApiUrl` | `TOKEN_API_URL` | URL of the tokenization Lambda when using token mode. |
| `AnonymizationTimeout` | `ANON_TIMEOUT` | Seconds before falling back to `[REMOVED]`. |

## Deployment

Deploy with SAM using the included template:

```bash
sam deploy --template-file services/text-anonymization/template.yaml --stack-name text-anonymization
```

