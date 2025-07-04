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

## Deploying Lambdas from ECR Images

The container images produced by `scripts/push_ecr.sh` can be deployed by
referencing the ECR URI in your SAM template or by updating an existing Lambda
function with the AWS CLI.

### SAM Template Update

Add the following properties to the function resource in your SAM template:

```yaml
MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    PackageType: Image
    ImageUri: <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<service>:<tag>
```

Deploy the stack with `sam deploy` to create or update the function using the
container image.

### Updating an Existing Function

To update a Lambda directly, provide the image URI to `update-function-code`:

```bash
aws lambda update-function-code --function-name <name> \
  --image-uri <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<service>:<tag>
```

Instead of typing the full command each time, you can run the helper script
`scripts/deploy_lambda_image.sh` which constructs the image URI automatically:

```bash
./scripts/deploy_lambda_image.sh <function-name> <account-id> <region> [tag]
```

The optional `tag` defaults to `latest`.

You can find the correct URI with `aws ecr describe-images` or from the output
of `scripts/push_ecr.sh`.
