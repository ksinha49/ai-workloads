# File Assembly Service

This service merges summary pages with the original PDF and uploads the merged
result to Amazon S3. It also provides a Lambda for redacting detected PII in
documents.

- **Lambdas**: `src/file_assembly_lambda.py`, `src/redact_file_lambda.py`
- **Layers**: `common/layers/file-assemble-lambda-layer/`,
  `common/layers/file-redaction-lambda-layer/`

The handler signatures reference dataclasses from ``models.py``:

- ``FileAssemblyEvent`` – incoming payload
- ``FileAssemblyResult`` – body of the success response
- ``LambdaResponse`` – wrapper used by ``lambda_handler``

## Environment variable

`AWS_ACCOUNT_NAME` must be provided so resource names can be scoped to your AWS
account. The redaction Lambda also honours `REDACTED_PREFIX` to determine the
upload location for redacted files.

## Deployment

Deploy with SAM using the provided template:

```bash
sam deploy \
  --template-file services/file-assembly/template.yaml \
  --stack-name file-assembly
```

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
