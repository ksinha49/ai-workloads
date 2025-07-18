# Changelog

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.17] - 2025-07-10
### Added
- Redaction service with orchestrator Lambda, file redaction and DynamoDB status tracking
- Email parser service for extracting attachments from incoming emails
- Email classifier service to route messages using rule-based logic
- On-demand OCR Lambda and `FORCE_OCR` option for the IDP pipeline
### Changed
- PII detection outputs structured entity data for compatibility with redaction

## [1.0.16] - 2025-07-08
### Added
- `docker-compose.yml` for the vector-db service to simplify local testing.

## [1.0.15] - 2025-07-07
### Added
- JSON logging option controlled by the `LOG_JSON` environment variable with
  support for `LOG_LEVEL` and `LOG_JSON` values stored in Parameter Store.
- `CommonUtilsLayer` referenced in each service template.

### Changed
- File ingestion and ZIP processing Lambdas now read S3 prefixes from
  configuration parameters.
- Documentation for available services and install steps updated.

### Fixed
- Cleanup Lambda gracefully handles S3 client errors and reports failures.
- Summarization worker and PDF generation Lambdas include improved error
  handling and logging.
- HTTPX calls across services catch request failures and return structured
  error responses.
## [1.0.14] - 2025-07-06
### Added
- Summarization service with Step Function workflow and helper Lambdas.
## [1.0.13] - 2025-07-04
### Added
- `rag-ingestion-worker` microservice that reads requests from SQS and triggers the RAG ingestion state machine.
## [1.0.12] - 2025-07-04
### Added
- Dockerfiles and `docker-compose.yml` files for each service.
- Docker Compose workflow (`docker-compose.ecr.yml`) and `push_ecr.sh` script to build and push images to ECR.
- `deploy_lambda_image.sh` helper for updating Lambda functions with container images.
- Support for loading dependencies and models from EFS using `EFS_DEPENDENCY_PATH` and `MODEL_EFS_PATH`.

### Changed
- Service Dockerfiles now target Python 3.13.
- Documentation expanded for ECR deployment and EFS configuration.

## [1.0.11] - 2025-07-04
### Added
- Lightweight `BaseModel` for event validation in `common_utils.pydantic`.
- `load_ner_model` helper for spaCy/HuggingFace NER models.
- `iter_s3_records` utility and refactored IDP Lambdas.
- RAG architecture overview and workflow diagrams for ingestion, tokenization and summarization.
- Standard Python `.gitignore` template.

### Changed
- Improved exception handling across services.
- README links to new ingestion workflow documentation.

## [1.0.10] - 2025-07-04
### Added
- Entity Tokenization service for deterministic replacement of sensitive values.

## [1.0.9] - 2025-07-03
### Added
- Sensitive Info Detection service with regex and ML-based entity extraction.
- Domain-specific models and customizable regex patterns.

### Changed
- Renamed `pii-detection` to `sensitive-info-detection`.
- Improved error handling and metadata in the detection Lambda.

## [1.0.8] - 2025-07-03
### Added
- Introduction of the Prompt Engine service and SQS-based prompt handling.
- Support for `workflow_id` and `system_prompt` in summarization.
- Universal chunking strategy with configurable mapping.
- Configurable re-rank provider and additional retrieval parameters.
- File GUID tracking, ingestion parameter validation, and removal of obsolete code and services.

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
