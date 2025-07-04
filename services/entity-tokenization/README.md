# Entity Tokenization Service

This service provides a Lambda for replacing sensitive entity values with stable tokens.
It looks up existing mappings in a DynamoDB table and generates new tokens when none
are found. Tokens can be deterministic when a salt is supplied or random otherwise.

## Lambda

- **tokenize-entity-lambda/app.py** – returns a token for the given entity text.

## Parameters and environment variables

`template.yaml` exposes a few parameters which become environment variables for
the Lambda:

| Parameter | Environment variable | Description |
|-----------|----------------------|-------------|
| `TokenSalt` | `TOKEN_SALT` | Optional salt used when hashing entities. |
| `TokenPrefix` | `TOKEN_PREFIX` | Prefix prepended to generated tokens. |
| `TokenTableName` | `TOKEN_TABLE` | Name of the DynamoDB mapping table. |

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/entity-tokenization/template.yaml --stack-name entity-tokenization
```

The stack exports `TokenizeEntityFunctionArn` and `TokenTableName` for use by
other services.
