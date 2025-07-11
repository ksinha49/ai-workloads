# Services Overview

This directory contains individual microservices used to build end‑to‑end AI processing workflows. Each service has its own `README.md` with deployment instructions and environment variables. The table below summarizes the purpose of each service.

| Service directory | Description |
|-------------------|-------------|
| **anonymization** | Detects sensitive entities and provides tokenization and masking functions. |
| **file-assembly** | Merges generated summary pages with the original PDF and uploads the result to S3. |
| **file-ingestion** | Copies uploaded files to the IDP bucket, polls for extraction status and cleans up temporary objects. |
| **idp** | Implements the Intelligent Document Processing pipeline for OCR and text extraction. |
| **knowledge-base** | Ingests text into the vector database and exposes query endpoints for retrieval. |
| **llm-gateway** | Renders prompts, routes requests and invokes language models. |
| **rag-stack** | Provides text chunking, embedding generation and retrieval functions for RAG workflows. |
| **summarization** | Orchestrates summarization through a Step Function and outputs PDF or DOCX summaries. |
| **vector-db** | Unified API for Milvus and Elasticsearch vector storage backends. |
| **zip-processing** | Extracts PDFs from archives, runs processing for each file and assembles a new ZIP. |
| **email-classifier-service** | Monitors an inbox, applies rules and routes extracted data. |
| **email-parser-service** | Parses raw email files from S3 and stores attachments. |
| **redaction** | Coordinates OCR extraction, PII detection and file redaction. |

Shared Lambda layers reside under `common/layers/` and are referenced by several services.

