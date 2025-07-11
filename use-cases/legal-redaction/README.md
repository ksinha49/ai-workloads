# Legal Subpoena Redaction

This use case demonstrates how the IDP, anonymization and redaction services can
be combined to remove PII from subpoena documents.  Uploaded PDFs are processed
through OCR, sensitive entities are detected using custom regex patterns and the
final redacted files are written back to S3.

## Configuration

The anonymization service reads configuration from Parameter Store or the Lambda
environment. Populate these variables before deployment:

- `LEGAL_MODEL` – NER model for legal documents
- `LEGAL_REGEX_PATTERNS` – JSON map of regex detectors
- `ANON_MODE` – set to `mask`
- `PRESIDIO_CONFIDENCE` – minimum score for Presidio

Create parameters named as above under `/parameters/aio/ameritasAI/<ENV>/` or
export them as environment variables. See
[services/anonymization/README.md](../../services/anonymization/README.md) and
[docs/environment_variables.md](../../docs/environment_variables.md#sensitive-info-detection)
(lines 113‑129) for detailed descriptions.

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
