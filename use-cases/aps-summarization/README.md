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
The `file_summary_lambda` also searches this directory for a
`summary_labels.json` file.  You can override the location or supply an
SSM parameter name via the `labels_path` property on the workflow input.

## Parameters

- `AWSAccountName` – prefix for stack resources.
- `SummarizationStateMachineArn` – ARN of the summarization service
  state machine (`FileProcessingStepFunction` output).
- `LambdaIAMRoleARN` – IAM role used by the Lambda function and state machine.
- `LambdaSubnet1ID` / `LambdaSubnet2ID` – subnets for the Lambda function.
- `LambdaSecurityGroupID1` / `LambdaSecurityGroupID2` – security groups for network access.
- `FontDir` – directory with font files (default `./src`).
- `LabelsPath` – path or SSM name for `summary_labels.json` (default `./config/summary_labels.json`).

The APS state machine forwards the `FontDir` and `LabelsPath` values as
`font_dir` and `labels_path` properties when it starts the summarization
workflow.  These settings allow `file_summary_lambda` to load custom fonts
and labels without modifying the core service.

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
    LambdaSecurityGroupID2=<sg2> \
    FontDir=<font_dir> \
    LabelsPath=<labels_path>
```
