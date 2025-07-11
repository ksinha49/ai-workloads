# ACORD XML Generator Service

This service converts extracted document data into a simplified
ACORD 103 XML payload.  It is typically invoked after OCR extraction
and field detection have completed.

The Lambda expects a JSON event with the following keys:

- **fields** – mapping of ACORD tag names to the extracted text values.
- **signatures** – optional mapping of signer roles to the signer name or
  timestamp.

The function returns the generated XML string in the `body` of the
Lambda response.

Example output for a minimal payload might look like:

```xml
<ACORD>
  <InsuranceSvcRq>
    <PolNumber>PN123</PolNumber>
    <Signatures>
      <Insured>John Doe</Insured>
    </Signatures>
  </InsuranceSvcRq>
</ACORD>
```

The accompanying `template.yaml` defines the Lambda function and a
parameter for the CaseImport API endpoint used by downstream
integrations.

## Environment variables

`template.yaml` exposes one parameter that becomes a Lambda environment
variable:

- `CASEIMPORT_ENDPOINT` – API endpoint for the CaseImport service.

The optional signature verification helper honours two additional
settings:

- `SIGNATURE_MODEL_ENDPOINT` – HTTP endpoint of a model returning a
  JSON object with a `score` field.
- `SIGNATURE_THRESHOLD` – confidence threshold used by
  `verify_signature` (default: `0.2`).
