# Email Parser Service

Parses raw email files from S3 and saves attachments to another bucket.

## Environment variables

- `ATTACHMENTS_BUCKET` – destination bucket for uploaded attachments.

## Deployment

Deploy with AWS SAM using the provided template:

```bash
sam deploy \
  --template-file services/email-parser-service/template.yaml \
  --stack-name email-parser
```

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
