# Intelligent Document Processing Service

This folder contains eight AWS Lambda functions forming a simple
Intelligent Document Processing (IDP) pipeline. Each step is triggered
by S3 events and writes results back to the same bucket under different
prefixes.

## Workflow

1. **1-classifier** – triggered when objects arrive under `RAW_PREFIX`.
   It inspects PDFs to see if they already contain text and then copies
   the file to either `OFFICE_PREFIX` for direct processing or a raw PDF
   prefix for splitting.
2. **2-office-extractor** – converts DOCX, PPTX and XLSX files from
   `CLASSIFIED_PREFIX` into Markdown pages stored in `TEXT_DOC_PREFIX`.
3. **3-pdf-split** – splits PDFs into per page files and writes a
   `manifest.json` under `PAGE_PREFIX`.
4. **4-pdf-page-classifier** – checks each page and routes it to
   `PAGE_PREFIX` when text is present or to an OCR prefix for scanning.
5. **5-pdf-text-extractor** – extracts embedded text from pages under
   `PAGE_PREFIX` and stores Markdown output in `TEXT_PREFIX`.
6. **6-pdf-ocr-extractor** – performs OCR on scanned pages using the
   engine specified by `OCR_ENGINE` and writes results to `OCR_PREFIX`.
7. **7-combine** – waits until all page outputs exist and combines them
   into a single JSON document under `COMBINE_PREFIX` / `TEXT_DOC_PREFIX`.
8. **8-output** – posts the final JSON from `TEXT_DOC_PREFIX` to an
   external API and stores any response under `OUTPUT_PREFIX`.

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
- `COMBINE_PREFIX` – location where combined page results are emitted.
- `OUTPUT_PREFIX` – final output prefix used by the output Lambda.
- `TEXT_DOC_PREFIX` – prefix for the merged document JSON files.
- `OCR_ENGINE` – selected OCR engine (`easyocr`, `paddleocr` or `trocr`).

Values are typically stored under `/parameters/aio/ameritasAI/<ENV>/` in
Parameter Store and automatically loaded by each Lambda.

Optional variables for OCR engines:

- `TROCR_ENDPOINT` – HTTP endpoint for TrOCR when `OCR_ENGINE="trocr"`.
- `DOCLING_ENDPOINT` – HTTP endpoint for Docling when
  `OCR_ENGINE="docling"`.

## Deployment

Deploy the stack with SAM:

```bash
sam deploy --template-file services/idp/template.yaml
```
