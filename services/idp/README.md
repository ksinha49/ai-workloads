# Intelligent Document Processing Service

This folder contains eight AWS Lambda functions forming a simple
Intelligent Document Processing (IDP) pipeline. Each step is triggered
by S3 events and writes results back to the same bucket under different
prefixes.

All handlers accept the :class:`models.S3Event` dataclass and return a
``LambdaResponse`` defined in ``models.py``.

## Workflow

1. **classifier** – `src/classifier_lambda.py` is triggered when objects
   arrive under `RAW_PREFIX`. It inspects PDFs to see if they already
   contain text and then copies the file to either `OFFICE_PREFIX` for
   direct processing or a raw PDF prefix for splitting.
2. **office-extractor** – `src/office_extractor_lambda.py` converts DOCX,
   PPTX and XLSX files from `CLASSIFIED_PREFIX` into Markdown pages
   stored in `TEXT_DOC_PREFIX`.
3. **pdf-split** – `src/pdf_split_lambda.py` splits PDFs into individual
   pages saved as `page_NNN.pdf` inside `PAGE_PREFIX/<documentId>/`. A
   `manifest.json` written alongside these pages records the
   `documentId` and total `pages`. See the implementation in
   `pdf_split_lambda.py` for details.
4. **pdf-page-classifier** – `src/pdf_page_classifier_lambda.py` checks
   each page and routes it to `PAGE_PREFIX` when text is present or to an
   OCR prefix for scanning.
5. **pdf-text-extractor** – `src/pdf_text_extractor_lambda.py` extracts
   embedded text from pages under `PAGE_PREFIX` and stores Markdown
   output in `TEXT_PREFIX`.
6. **pdf-ocr-extractor** – `src/pdf_ocr_extractor_lambda.py` performs OCR
   on scanned pages using the engine specified by `OCR_ENGINE`. Markdown
   results are written to `OCR_PREFIX` and, when the `ocrmypdf` engine is
   used, word bounding boxes are stored under `HOCR_PREFIX`.
7. **combine** – `src/combine_lambda.py` waits until all page outputs
   exist and combines them into a single JSON document under
   `COMBINE_PREFIX` / `TEXT_DOC_PREFIX`. If hOCR files are present, they
   are merged into a document-level JSON under `HOCR_PREFIX`.
8. **output** – `src/output_lambda.py` posts the final JSON from
   `TEXT_DOC_PREFIX` to an external API and stores any response under
   `OUTPUT_PREFIX`.

The relationships between file types and Lambda functions are illustrated
in the following diagram.

```mermaid
flowchart LR
    A["Upload to RAW_PREFIX"] --> B(classifier)
    B -- "DOCX/PPTX/XLSX" --> C(office-extractor)
    B -- "PDF" --> D(pdf-split)
    D --> E(pdf-page-classifier)
    subgraph "per-page lambdas"
        direction TB
        E -- "text page" --> F(pdf-text-extractor)
        E -- "scan page" --> G(pdf-ocr-extractor)
        G --> J[hOCR JSON]
    end
    C --> H(combine)
    F --> H
    G --> H
    H --> I(output)
```

### On-demand OCR

An additional Lambda called **on-demand-ocr** can process any document when a
message is placed on the `OcrRequestQueue`. The queue payload must specify the
`bucket` and `key` of the source file. The Lambda downloads the PDF, runs OCR on
each page and writes the merged Markdown to `TEXT_DOC_PREFIX`. When the
`ocrmypdf` engine is used, a document-level hOCR JSON is also stored under
`HOCR_PREFIX`.

```mermaid
flowchart LR
    Q(OcrRequestQueue) --> L(on-demand-ocr)
    L --> T(TEXT_DOC_PREFIX)
    L -->|"hOCR (ocrmypdf)"| H(HOCR_PREFIX)
```

## Environment variables

Several prefixes and options are provided via environment variables in
`template.yaml`. Typical values are stored in AWS Systems Manager
Parameter Store and read at runtime using the shared `get_config`
helper. Key variables include:

- `BUCKET_NAME` – S3 bucket holding all pipeline objects.
- `RAW_PREFIX` – prefix for new uploads that trigger the classifier.
- `CLASSIFIED_PREFIX` – where the classifier writes its results.
- `OFFICE_PREFIX` – destination for Office documents and PDFs with
  embedded text.
- `SPLIT_PREFIX` – location for PDFs to be split into pages.
- `PAGE_PREFIX` – prefix containing individual page PDFs.
- `TEXT_PREFIX` – prefix for Markdown created from text-based pages.
- `OCR_PREFIX` – prefix for OCR results.
- `HOCR_PREFIX` – prefix for hOCR JSON word boxes.
- `COMBINE_PREFIX` – location where combined page results are emitted.
- `OUTPUT_PREFIX` – final output prefix used by the output Lambda.
- `TEXT_DOC_PREFIX` – prefix for the merged document JSON files.
- `OCR_ENGINE` – selected OCR engine (`easyocr`, `paddleocr`, `trocr`, `ocrmypdf`).

Values are typically stored under `/parameters/aio/ameritasAI/<ENV>/` in
Parameter Store and automatically loaded by each Lambda.

Optional variables for OCR engines:

- `TROCR_ENDPOINT` – HTTP endpoint for TrOCR when `OCR_ENGINE="trocr"`.
- `DOCLING_ENDPOINT` – HTTP endpoint for Docling when
  `OCR_ENGINE="docling"`.

### OCR Engine

The `OCR_ENGINE` variable controls which backend to run:

- `easyocr` (default)
- `paddleocr`
- `trocr` – requires `TROCR_ENDPOINT`
- `docling` – requires `DOCLING_ENDPOINT`
- `ocrmypdf` – outputs hOCR files with word coordinates

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/idp/template.yaml
```

## Local testing

Build and run with Docker Compose:

```bash
docker compose build
docker compose up
```
