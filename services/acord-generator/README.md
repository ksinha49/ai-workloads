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
