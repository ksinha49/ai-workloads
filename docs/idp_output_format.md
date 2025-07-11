# Canonical IDP Output Format

This document describes the standard Markdown representation for text extracted from documents. All consumers of IDP output should conform to this structure to ensure interoperability.

## Required Fields

| Field       | Type   | Description                                     |
|-------------|--------|-------------------------------------------------|
| `documentId`| string | Unique identifier for the source document.      |
| `pageNumber`| number | Page number where the text was found.           |
| `content`   | string | Extracted text content for the page.            |

### JSON Example

```json
{
  "documentId": "abc123",
  "pageNumber": 1,
  "content": "Sample page text"
}
```

## Markdown Conventions

- **Headings**: Use `#` for the document title, `##` for sections, and so on. Do not skip levels.
- **Tables**: Include a blank line before and after each table. Use pipe `|` characters to separate columns and dashes `-` for the header row divider.
- **Plain Text**: For multi-line content, preserve line breaks exactly as they appear in the source. Do not embed Markdown formatting inside `content` fields.

By standardizing on this format, text extracted by different IDP engines can be processed uniformly across downstream services.

## OCR Bounding Box Output

When the `ocrmypdf` engine is selected, each page also produces a JSON file
containing word-level bounding boxes. Files are written to
`<HOCR_PREFIX><documentId>/page_<n>.json` and have the following structure:

```json
{
  "words": [
    {"bbox": [50, 717, 89, 734], "text": "Sample"}
  ]
}
```

The `bbox` values correspond to the coordinates from the original hOCR output
(`x1`, `y1`, `x2`, `y2`).

## On-Demand OCR Interface

The `on-demand-ocr` Lambda can be invoked through SQS. Each message must contain
the source bucket and document key:

```json
{
  "bucket": "source-bucket",
  "key": "uploads/doc.pdf"
}
```

After processing, the Lambda writes the combined Markdown to
`<TEXT_DOC_PREFIX><documentId>.json`. When the `ocrmypdf` engine is used, a
corresponding hOCR JSON file is written to `<HOCR_PREFIX><documentId>.json`.
The Lambda returns the keys of these objects:

```json
{
  "text_doc_key": "text-docs/doc.json",
  "hocr_key": "hocr/doc.json"
}
```

