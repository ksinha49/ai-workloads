# ZIP Processing Service

This module extracts PDFs from an uploaded archive, processes them individually and assembles a new ZIP file once all files complete.

## Lambdas

- **zip-extract-lambda** – reads a ZIP from S3, extracts PDF/XML files and returns their S3 paths.
- **zip-creation-lambda** – collects summarized PDFs and metadata then writes the final ZIP to S3.

A state machine defined in `template.yaml` orchestrates the flow:
1. **ExtractZip** invokes `zip-extract-lambda`.
2. **ProcessAllPdfs** maps each extracted PDF through the `FileProcessingStepFunctionArn` state machine.
3. **AssembleZip** calls `zip-creation-lambda` to build the output archive.
4. Errors are summarized and emailed via an SNS topic subscribed to `FileProcessingEmailId`.

## Environment variables

Both Lambdas require `AWS_ACCOUNT_NAME` which is passed from the stack parameter of the same name.

## Parameters

- `AWSAccountName` – account prefix for naming resources.
- `LambdaSubnet1ID` / `LambdaSubnet2ID` – subnets for the Lambdas.
- `LambdaSecurityGroupID1` / `LambdaSecurityGroupID2` – security groups for network access.
- `LambdaIAMRoleARN` – IAM role assumed by the functions.
- `FileProcessingStepFunctionArn` – ARN of the per‑file processing state machine.
- `FileProcessingStepFunctionIAMRole` – IAM role used by the ZIP state machine.
- `FileProcessingEmailId` – email address subscribed to the SNS failure report.

## Deployment

Deploy the service with SAM:

```bash
sam deploy \
  --template-file services/zip-processing/template.yaml \
  --stack-name zip-processing \
  --parameter-overrides \
    AWSAccountName=<name> \
    LambdaSubnet1ID=<subnet1> \
    LambdaSubnet2ID=<subnet2> \
    LambdaSecurityGroupID1=<sg1> \
    LambdaSecurityGroupID2=<sg2> \
    LambdaIAMRoleARN=<role-arn> \
    FileProcessingStepFunctionArn=<arn> \
    FileProcessingStepFunctionIAMRole=<role-arn> \
    FileProcessingEmailId=<email>
```
