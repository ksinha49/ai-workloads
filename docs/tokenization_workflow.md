# Tokenization Workflow

This document explains how the entity tokenization service converts sensitive values into stable tokens and how the tokens can be re-anonymized.
See [entity_tokenization_service.md](entity_tokenization_service.md) for deployment parameters and examples.

## Consistent Token Generation

1. Incoming requests provide an `entity`, its `entity_type` and optional `domain`.
2. The Lambda checks the DynamoDB mapping table for an existing entry matching all three fields.
3. If a record is found the stored token is returned. Otherwise a new token is created by:
   - Prepending the value of the `TOKEN_SALT` environment variable to the entity text.
   - Hashing the result with SHA‑256 and taking the first eight characters.
   - Prefixing the digest with the string from `TOKEN_PREFIX`.
4. The mapping of entity to token is stored in DynamoDB so subsequent calls return the same value.

Providing a salt ensures identical entities are hashed to the same output across invocations. When no salt is configured the service falls back to a random UUID, still storing the mapping for consistent behaviour.

## Rotating Salts or Namespaces

Over time you may need to re‑anonymize existing data. Two approaches are supported:

1. **Change `TOKEN_SALT`** – Update the Lambda's environment variable and clear the DynamoDB table. Incoming entities will hash to new tokens using the fresh salt.
2. **Use a new `TOKEN_PREFIX` or DynamoDB table** – Keep historical mappings intact but start writing to a different table or prefix. This effectively namespaces the tokens so old data remains valid while new data receives brand new values.

Either method avoids token collisions and lets you regenerate identifiers when requirements change.

## Security Considerations

- **IAM roles** – The function runs with permissions limited to reading and writing its DynamoDB table. Follow the principle of least privilege when granting additional access.
- **Encryption at rest** – Enable DynamoDB server-side encryption and store salts or table names in AWS Systems Manager Parameter Store. Both services encrypt data at rest.
- **Audit logging** – Enable CloudTrail for DynamoDB and Lambda to capture all read/write activity. Logs can be forwarded to CloudWatch or an external system for auditing purposes.

Following these practices helps protect sensitive data while still allowing repeatable tokenization.
