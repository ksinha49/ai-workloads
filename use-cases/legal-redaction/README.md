# Legal Subpoena Redaction

This use case demonstrates how the IDP, anonymization and redaction services can
be combined to remove PII from subpoena documents. Uploaded PDFs are processed
through OCR, sensitive entities are detected using custom regex patterns and the
final redacted files are written back to S3.

## Workflow

```mermaid
flowchart LR
    A["Upload PDF to redact/ prefix"] --> B(Redaction orchestrator)
    B --> C[Copy to IDP bucket]
    C --> D(IDP OCR pipeline)
    D --> E[Extracted text & hOCR]
    E --> F[/detect-pii API]
    F --> G(File redaction Lambda)
    G --> H[Redacted PDF in S3]
    G --> I[Update status table]
```

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

## Uploading subpoena documents

Subpoena PDFs can be submitted either via the ingestion API or by uploading
directly to the IDP bucket. The SAM template connects the Redaction Service to
`s3:ObjectCreated:*` events so any file placed under the configured
`SourcePrefix` (default `redact/`) triggers the orchestrator:

```yaml
SourceBucket: !Ref IdpBucketName
SourcePrefix: redact/
Events:
  Upload:
    Type: S3
    Properties:
      Bucket: !Ref SourceBucket
      Events: s3:ObjectCreated:*
      Filter:
        S3Key:
          Rules:
            - Name: prefix
              Value: !Ref SourcePrefix
```

When the event fires, the workflow copies the uploaded PDF to the IDP bucket so
OCR can run before redaction begins.

## Retrieving redacted PDFs

Documents uploaded via either method are copied to the IDP bucket for OCR
extraction. Once processing is complete the `redact_file_lambda` from
**file-assembly** writes the PDF back to the same bucket using the prefix from
the `REDACTED_PREFIX` environment variable (see
[services/file-assembly/README.md](../../services/file-assembly/README.md#environment-variable)).
Locate the final PDF at:

```
s3://<IDP bucket>/<RedactedPrefix><original filename>
```

The associated DynamoDB table exported as `RedactionStatusTableName` records the
processing status for each document.
