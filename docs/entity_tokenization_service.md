# Entity Tokenization Service

The entity tokenization Lambda converts raw entity strings into stable tokens. It
checks a DynamoDB table for an existing mapping and returns the token if found.
When no mapping exists a new token is generated using a salted hash or random
UUID and stored in the table.

The API endpoint is secured with IAM authentication. HTTP requests must be signed using SigV4 credentials or issued from other AWS services with appropriate IAM roles.

## Environment Variables

| Name | Description |
| ---- | ----------- |
| `TOKEN_TABLE` | DynamoDB table that stores entity/token mappings. |
| `TOKEN_PREFIX` | Prefix added to generated tokens. |
| `TOKEN_SALT` | Optional salt for deterministic hashing. |

The ``TOKEN_TABLE`` uses ``entity`` as the partition key and ``entity_type`` as
the sort key. A ``DomainIndex`` global secondary index is provided with
``entity`` as the partition key and ``domain`` as the sort key.

## Example

Send a request to the API endpoint or invoke the Lambda directly:

```json
{"entity": "Jane Doe", "entity_type": "PERSON", "domain": "Medical"}
```

A response similar to the following is returned:

```json
{"token": "ent_a1b2c3d4"}
```

Subsequent calls with the same entity, type and domain return the same token.

For details on the overall tokenization process see [tokenization_workflow.md](tokenization_workflow.md).
