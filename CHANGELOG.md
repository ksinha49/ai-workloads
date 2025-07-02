# Changelog

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.7] - 2025-07-02
### Added
- Dataclass models for Lambda events and responses documented in `docs/event_schemas.md`.
- Async invocation via SQS for router, invocation and knowledge-base services.
### Changed
- Logging initialized with `configure_logger` across modules.
- Improved error handling and structured responses.
### Fixed
- Structured error responses for S3 and Lambda invocation failures.

## [1.0.6] - 2025-07-01
### Added
- Detailed logging utilities across services for consistent diagnostics.
- Knowledge base service enabling lightweight text ingestion and retrieval.
- Health-checked endpoint selection for routing LLM requests.
- Cross-encoder reranking service for improved RAG results.
- Comprehensive docstrings across router, backend, and helper modules.
- Internationalization and environment variable documentation.

### Changed
- Centralized logger configuration for all Lambdas.
- Revised Lambda handler docstrings and module metadata.

### Fixed
- Minor bugs in RAG retrieval and vector search services.

## [1.0.5] - 2025-06-30
### Added
- LLM router service with heuristic, predictive, generative, and cascading strategies.
- LLM invocation service supporting multiple backends (Bedrock, Ollama).
- Summarization workflow updates including ingestion step and Map state.
- Zip-processing service separated from summarization.
- RAG summarization integration with parameter overrides.

### Changed
- Updated SAM templates and deployment docs for new services.

## [1.0.4] - 2025-06-29
### Added
- Vector DB service with Milvus management operations.
- RAG ingestion service for chunking text and generating embeddings.
- RAG retrieval service for searching and providing context.
- Document combine logic and output API posting in the IDP pipeline.
- Support for TrOCR and PaddleOCR engines; Docling processor Lambda.

### Changed
- Refactored project structure into service-specific directories.
- Improved PDF handling and text extraction using `fitz`.

## [1.0.3] - 2025-06-28
### Added
- Intelligent Document Processing (IDP) pipeline including:
  - Classification, PDF splitting, text extraction, OCR, and combine stages.
  - Office document extraction and page classifier enhancements.
- OCR layer and utilities for different engines.
- Initial summarization workflow.

### Changed
- Unified SSM configuration loading and Lambda responses.

## [1.0.2] - 2025-06-27
### Added
- Shared utilities module (`get_ssm.py`) for fetching configuration.
- Consistent response structure for Lambda functions.
- Placeholder Lambda directories with initial setup.

### Changed
- Refactored S3 client initialization across services.

## [1.0.1] - 2025-06-27
### Added
- Repository structure refactored for services and README added.
- Base SAM template for the pipeline.

## [1.0.0] - 2025-05-29
### Added
- Integrate with Globalscape to automatically ingest zipped APS documents from an AWS S3 bucket.
- Implement an SQS queue to buffer uploads and validate PDF contents and XML metadata.
- Perform OCR when necessary, summarize content using an AI microservice, and assemble the final PDF.
- Append summaries to the original PDF or create a separate summary PDF.
- Store final documents in S3 for archival and forward them to TPP.

### Fixed
- Prevent high volumes from overwhelming the AI microservice through SQS buffering and Lambda concurrency scaling.
- Improve summary quality via ongoing model and prompt enhancements during pilot testing.
- Handle subfolder structures up to six levels deep when allocating files.

### Refactored
- Leverage AWS Lambda, S3, and SQS for serverless orchestration.
- Provision resources with `template.yaml`.
- Manage dependencies using Lambda layers.
- Orchestrate reusable services through AWS Step Functions.
- Centralize logging with CloudWatch and ELK Stash for auditing and troubleshooting.
- Encrypt data in transit and at rest while enforcing least-privilege IAM roles.
