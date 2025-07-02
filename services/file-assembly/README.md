# File Assembly Service

This service merges summary pages with the original PDF and uploads the merged result to Amazon S3.

- **Lambda**: `file-assemble-lambda/app.py`
- **Layer**: `common/layers/file-assemble-lambda-layer/`

## Environment variable

`AWS_ACCOUNT_NAME` must be provided so resource names can be scoped to your AWS account.

## Deployment

Deploy with SAM using the provided template:

```bash
sam deploy \
  --template-file services/file-assembly/template.yaml \
  --stack-name file-assembly
```
