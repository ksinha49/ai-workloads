# Anonymization Service

This consolidated service groups three Lambdas for detecting, tokenizing and anonymizing sensitive text.

All API endpoints in this stack are protected using IAM authentication. Requests
must be signed with AWS credentials (SigV4) or invoked directly from other AWS
services with appropriate IAM roles.

## Lambdas

- **detect_sensitive_info_lambda.py** – returns detected PII entities.
- **tokenize_entities_lambda.py** – generates or looks up a token for an entity.
- **mask_text_lambda.py** – anonymizes text using masking, pseudonyms or tokens.

## Parameters and environment variables

`template.yaml` defines parameters that become environment variables for each Lambda.

### detect_sensitive_info_lambda

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `NerLibrary` | `NER_LIBRARY` | NLP library to use (`spacy` or `hf`). |
| `SpacyModel` | `SPACY_MODEL` | spaCy model name. |
| `HFModel` | `HF_MODEL` | HuggingFace model name. |
| `MedicalModel` | `MEDICAL_MODEL` | Model when `domain` is `Medical`. |
| `LegalModel` | `LEGAL_MODEL` | Model when `domain` is `Legal`. |
| `RegexPatterns` | `REGEX_PATTERNS` | JSON map of regex detectors. |
| `LegalRegexPatterns` | `LEGAL_REGEX_PATTERNS` | JSON map for legal domain. |

### tokenize_entities_lambda

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `TokenSalt` | `TOKEN_SALT` | Optional salt for deterministic tokens. |
| `TokenPrefix` | `TOKEN_PREFIX` | Prefix for generated tokens. |
| `TokenTableName` | `TOKEN_TABLE` | DynamoDB table for token mappings. |

### mask_text_lambda

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `AnonymizationMode` | `ANON_MODE` | `mask`, `pseudo` or `token`. |
| `TokenApiUrl` | `TOKEN_API_URL` | URL of the tokenization Lambda. |
| `AnonymizationTimeout` | `ANON_TIMEOUT` | Seconds before falling back to `[REMOVED]`. |

### DynamoDB tables

The `tokenize_entities_lambda` uses the `TOKEN_TABLE` DynamoDB table to persist entity/token mappings. The table stores items with `entity` as the partition key and `entity_type` as the sort key. A `DomainIndex` GSI allows lookups by domain. The table name is exported as `TokenTableName` for other stacks.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/anonymization/template.yaml --stack-name anonymization
```

The stack exports `DetectSensitiveInfoFunctionArn`, `TokenizeEntityFunctionArn`, `AnonymizeTextFunctionArn` and `TokenTableName` for use by other services.


## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
