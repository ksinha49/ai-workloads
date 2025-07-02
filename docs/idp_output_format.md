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

