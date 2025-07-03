# Prompt Engine Service

This service provides a simple Lambda for rendering prompts stored in a DynamoDB
 table. The function loads a template from `PromptLibraryTable`, substitutes
variables passed in the request and forwards the final prompt to the LLM router
specified by `RouterEndpoint`.

## Parameters

`template.yaml` exposes several parameters which become environment variables for
the Lambda:

| Parameter | Environment variable | Description |
|-----------|---------------------|-------------|
| `TableName` | `PROMPT_LIBRARY_TABLE` | DynamoDB table containing prompt templates |
| `RouterEndpoint` | `ROUTER_ENDPOINT` | URL of the LLM router handling requests |
| `LambdaSubnet1ID` / `LambdaSubnet2ID` | — | Subnets used by the Lambda |
| `LambdaSecurityGroupID1` / `LambdaSecurityGroupID2` | — | Security groups attached to the Lambda |
| `LambdaIAMRoleARN` | — | IAM role assumed by the function |

## Deployment

Deploy the stack with SAM:

```bash
sam deploy \
  --template-file services/prompt-engine/template.yaml \
  --stack-name prompt-engine \
  --parameter-overrides \
    TableName=<table-name> \
    RouterEndpoint=<router-url>
```

## Usage

Invoke the Lambda with a JSON payload referencing a template name and any
variables required by that template. The function returns the response from the
router service.
