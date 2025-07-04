# Deploying Lambda Container Images to ECR

This repository can build all service images for AWS Elastic Container Registry (ECR) using Docker Compose. The container images can then be referenced by your SAM templates or deployed directly as Lambda functions.

## Prerequisites

- Run `sam build` to generate all Lambda layers under `common/layers`.
- Docker must be authenticated to your AWS account.

## Building and Pushing Images

Use the helper script `scripts/push_ecr.sh` to log in to ECR and push all images defined in `docker-compose.ecr.yml`:

```bash
./scripts/push_ecr.sh <account-id> <region> [tag]
```

The script builds each service image and pushes it to `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/<service>:TAG`. The optional `TAG` defaults to `latest`.

## Example

```bash
./scripts/push_ecr.sh 123456789012 us-east-1 v1
```

After pushing, the images can be referenced from your Lambda function configurations without affecting the existing SAM-based deployment process.
