# APS Summarization Use Case

This directory contains a wrapper around the generic summarization
service for processing Attending Physician Statements (APS).  The
`template.yaml` deploys a Step Function that starts the reusable
summarization state machine with the APS prompt collection and then
executes an optional post processing Lambda.

## Environment variables

`aps_workflow_lambda.py` and the underlying `file_summary_lambda`
expect `FONT_DIR` to point to a folder containing TrueType fonts.
The provided template passes the `FontDir` parameter value to both
functions so PDFs can be generated using `DejaVuSans.ttf` and
`DejaVuSans-Bold.ttf` shipped in `src/`.

## Parameters

- `AWSAccountName` – prefix for stack resources.
- `SummarizationStateMachineArn` – ARN of the summarization service
  state machine (`FileProcessingStepFunction` output).
- `LambdaIAMRoleARN` – IAM role used by the Lambda function and state machine.
- `LambdaSubnet1ID` / `LambdaSubnet2ID` – subnets for the Lambda function.
- `LambdaSecurityGroupID1` / `LambdaSecurityGroupID2` – security groups for network access.
- `FontDir` – directory with font files (default `./src`).

## Deployment

Deploy the use case with SAM:

```bash
sam deploy \
  --template-file use-cases/aps-summarization/template.yaml \
  --stack-name aps-summarization \
  --parameter-overrides \
    AWSAccountName=<name> \
    SummarizationStateMachineArn=<arn> \
    LambdaIAMRoleARN=<role-arn> \
    LambdaSubnet1ID=<subnet1> \
    LambdaSubnet2ID=<subnet2> \
    LambdaSecurityGroupID1=<sg1> \
    LambdaSecurityGroupID2=<sg2>
```
