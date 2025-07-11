# New Business Intake Workflow

This Usecase for Paper App to TPP processing processes new business submissions and generate ACORD XML for CaseImport.

## Parameters

- `AWSAccountName` – prefix for stack resources.
- `LambdaIAMRoleARN` – IAM role used by the Lambda functions and state machine.
- `LambdaSubnet1ID` / `LambdaSubnet2ID` – subnets for the Lambda functions.
- `LambdaSecurityGroupID1` / `LambdaSecurityGroupID2` – security groups for network access.
- `CaseImportEndpoint` – API endpoint for the CaseImport service.

## Deployment

Deploy the workflow with SAM:

```bash
sam deploy \
  --template-file use-cases/new-business-intake/template.yaml \
  --stack-name new-business-intake \
  --parameter-overrides \
    AWSAccountName=<name> \
    LambdaIAMRoleARN=<role-arn> \
    LambdaSubnet1ID=<subnet1> \
    LambdaSubnet2ID=<subnet2> \
    LambdaSecurityGroupID1=<sg1> \
    LambdaSecurityGroupID2=<sg2> \
    CaseImportEndpoint=<endpoint>
```
