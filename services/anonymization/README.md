# Anonymization Service

This consolidated service groups three Lambdas for detecting, tokenizing and anonymizing sensitive text.

## Lambdas

- **detect_sensitive_info_lambda.py** – returns detected PII entities.
- **tokenize_entities_lambda.py** – generates or looks up a token for an entity.
- **mask_text_lambda.py** – anonymizes text using masking, pseudonyms or tokens.

## Parameters and environment variables

`template.yaml` exposes a number of parameters which become environment variables for the Lambdas:

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `NerLibrary` | `NER_LIBRARY` | NLP library for detection (`spacy` or `hf`). |
| `SpacyModel` | `SPACY_MODEL` | spaCy model name. |
| `HFModel` | `HF_MODEL` | HuggingFace model name. |
| `MedicalModel` | `MEDICAL_MODEL` | Model when `domain` is `Medical`. |
| `LegalModel` | `LEGAL_MODEL` | Model when `domain` is `Legal`. |
| `RegexPatterns` | `REGEX_PATTERNS` | JSON map of regex detectors. |
| `LegalRegexPatterns` | `LEGAL_REGEX_PATTERNS` | JSON map for legal domain. |
| `TokenSalt` | `TOKEN_SALT` | Optional salt for deterministic tokens. |
| `TokenPrefix` | `TOKEN_PREFIX` | Prefix for generated tokens. |
| `TokenTableName` | `TOKEN_TABLE` | DynamoDB table for mappings. |
| `AnonymizationMode` | `ANON_MODE` | `mask`, `pseudo` or `token`. |
| `TokenApiUrl` | `TOKEN_API_URL` | URL of the tokenization Lambda. |
| `AnonymizationTimeout` | `ANON_TIMEOUT` | Seconds before falling back to `[REMOVED]`. |

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/anonymization/template.yaml --stack-name anonymization
```

The stack exports `DetectSensitiveInfoFunctionArn`, `TokenizeEntityFunctionArn`,
`AnonymizeTextFunctionArn` and `TokenTableName` for use by other services.

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
