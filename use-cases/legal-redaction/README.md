# Legal Subpoena Redaction

This use case demonstrates how the IDP, anonymization and redaction services can
be combined to remove PII from subpoena documents.  Uploaded PDFs are processed
through OCR, sensitive entities are detected using custom regex patterns and the
final redacted files are written back to S3.

## Deployment

Deploy all required services with SAM.  The stack parameters provide network and
IAM settings shared by each nested application.  `LegalRegexPatterns` should be
a JSON string containing any custom patterns for the anonymization service.  A
sample file is included under `config/legal_regex_patterns.json`.

```bash
sam deploy \
  --template-file use-cases/legal-redaction/template.yaml \
  --stack-name legal-redaction \
  --parameter-overrides \
    AWSAccountName=<name> \
    LambdaIAMRoleARN=<role-arn> \
    LambdaSubnet1ID=<subnet1> \
    LambdaSubnet2ID=<subnet2> \
    LambdaSecurityGroupID1=<sg1> \
    LambdaSecurityGroupID2=<sg2> \
    LegalRegexPatterns="$(cat use-cases/legal-redaction/config/legal_regex_patterns.json)"
```

## Retrieving redacted PDFs

Documents uploaded to the redaction API or S3 trigger are copied to the IDP
bucket for OCR extraction.  Once processing is complete the `redact_file_lambda`
from **file-assembly** stores the output under the prefix defined by
`RedactedPrefix` (defaults to `redacted/`).  Locate the final PDF at:

```
s3://<IDP bucket>/<RedactedPrefix><original filename>
```

The associated DynamoDB table exported as `RedactionStatusTableName` records the
processing status for each document.
