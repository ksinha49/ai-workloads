# PII Detection Service

This service exposes a single Lambda for detecting personally identifiable
information (PII) in text. The handler combines regex based patterns with an
optional machine learning model to recognise entities.

## Lambda

- **detect-pii-lambda/app.py** – returns a JSON list of detected entities.

## Parameters and environment variables

`template.yaml` defines optional parameters used to configure the underlying NER
model. Each parameter becomes an environment variable for the Lambda:

| Parameter   | Environment variable | Description                                |
| ----------- | -------------------- | ------------------------------------------ |
| `NerLibrary` | `NER_LIBRARY`       | `spacy` or `hf` to select the library.     |
| `SpacyModel` | `SPACY_MODEL`       | spaCy model name when using `spacy`.       |
| `HFModel`    | `HF_MODEL`          | HuggingFace model name when using `hf`.    |

The Lambda always runs a small set of regex detectors in addition to any model.

## Response format

The function returns JSON in the following form:

```json
{
  "entities": [
    {"text": "John", "type": "PERSON", "start": 0, "end": 4}
  ]
}
```

Each entity includes the text span, label, and character offsets.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/pii-detection/template.yaml --stack-name pii
```

The output exports `DetectPiiFunctionArn` which can be used by other services.
