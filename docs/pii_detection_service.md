# PII Detection Service

The `detect_sensitive_info_lambda.py` Lambda extracts personally identifiable information from input text.
It does **not** modify or anonymize the text. The function is exposed through the `/detect-pii` API endpoint
in the `anonymization` service.

## Request

Send a JSON payload with a `text` field and optional `domain` value:

```json
{"text": "Jane Doe 123-45-6789", "domain": "Medical"}
```

The domain selects a specialized model when provided (`Medical` or `Legal`).

## Response

A JSON object containing the detected entities is returned:

```json
{"entities": [{"text": "Jane Doe", "type": "PERSON", "start": 0, "end": 8}]}
```

Each entity includes the matched substring, its type and positional offsets within the original text.
