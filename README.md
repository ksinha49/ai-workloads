# Enterprise AI Services

Ameritas Enterprise AI Services is a collection of custom built microservices for building serverless document processing workflows. Each service focuses on a specific task such as OCR extraction, PDF assembly or embedding generation.

## Services

The repository includes the following directories under `services/`:

- `file-assembly` – merges summary pages with the original PDF
- `file-ingestion` – copies files to the IDP bucket and polls for text
  extraction status
- `idp` – Intelligent Document Processing pipeline (classification, OCR and text extraction)
- `zip-processing` – extracts PDFs from uploaded archives and assembles new ZIPs
- `rag-stack` – combined ingestion and retrieval Lambdas used for RAG workflows. Includes a worker that polls the ingestion queue and starts the workflow
- `vector-db` – manages Milvus or Elasticsearch backends and search Lambdas
- `summarization` – Step Function orchestrates retrieval and summary generation into PDF or DOCX reports
- `llm-gateway` – renders templates and routes requests to the selected LLM backend
- `knowledge-base` – ingest text snippets and query them through the retrieval stack
- `anonymization` – detects sensitive entities, generates tokens and masks or pseudonymizes text
- `redaction` – orchestrates OCR extraction, PII detection and file redaction with DynamoDB tracking
- `email-parser-service` – extracts attachments from raw emails stored in S3
- `email-classifier-service` – monitors a mailbox and routes messages based on dynamic rules

Shared dependencies are packaged as layers in `common/layers/`.

Detailed descriptions of each service are available in
[services/README.md](services/README.md).


## Repository Structure

```text
.
├── INSTALL.md
├── README.md
├── common/
│   └── layers/
├── docs/
│   ├── idp_output_format.md
│   ├── router_configuration.md
│   └── summarization_workflow.md
├── services/
│   └── <service directories>
├── template.yaml
└── tests/
```

## Installation

Refer to [INSTALL.md](INSTALL.md) for detailed steps. In short:

```bash
git clone https://github.com/ameritascorp/aio-enterprise-ai-services.git
cd ai-workloads
sam build
```

Python packages are installed into each Lambda's layer under `common/layers/` during the build.

## Configuration

Runtime settings are stored in AWS Systems Manager Parameter Store using the path `/parameters/aio/ameritasAI/<ENV>/<NAME>`. S3 object tags with the same keys may override these values for individual files.
Values are cached by the shared `get_values_from_ssm` helper using
[AWS Lambda Powertools](https://awslabs.github.io/aws-lambda-powertools-python/latest/utilities/parameters/).
When the `SSM_CACHE_TABLE` environment variable is defined, the cache
uses DynamoDB to persist entries across cold starts.

### Logging

The default log level is `INFO` but can be overridden using the `LOG_LEVEL`
environment variable. Set `LOG_JSON=true` to emit structured logs in JSON
format. Both variables may also be supplied via Parameter Store using the same
names.

### OCR Engine

The `OCR_ENGINE` variable controls which OCR backend to use:

- `easyocr` (default)
- `paddleocr`
- `trocr` – requires `TROCR_ENDPOINT`
- `docling` – requires `DOCLING_ENDPOINT`

## Environment Variables

See [docs/environment_variables.md](docs/environment_variables.md) for a
complete list of common variables used across the services.


## Deployment

Deploy a service with `sam deploy --template-file services/<service>/template.yaml --stack-name <name>` and provide any required parameters. See each service's README for details.

Container images for all services can be built and pushed to ECR using:

```bash
./scripts/push_ecr.sh <account-id> <region> [tag]
```

This does not alter the existing SAM deployment process but allows functions to reference ECR images if desired.

If your dependencies or models exceed the Lambda package limit, mount an EFS access
point and install the packages to that volume. Set the environment variables
`EFS_DEPENDENCY_PATH` and `MODEL_EFS_PATH` (or provide them via Parameter Store)
so services can import modules and load models directly from EFS.

## Documentation

Additional documentation is available in the `docs/` directory:
- [summarization_workflow](docs/summarization_workflow.md)
- [rag_ingestion_workflow](docs/rag_ingestion_workflow.md)

- [idp_output_format](docs/idp_output_format.md)
- [router_configuration](docs/router_configuration.md)
- [prompt_engine](docs/prompt_engine.md)
- [knowledge_rag_usage](docs/knowledge_rag_usage.md)
- [rag_architecture](docs/rag_architecture.md)
- [event_schemas](docs/event_schemas.md)
- [entity_tokenization_service](docs/entity_tokenization_service.md)
- [tokenization_workflow](docs/tokenization_workflow.md)
- [environment_variables](docs/environment_variables.md)
- [file_ingestion_workflow](docs/file_ingestion_workflow.md)
- [ecr_deployment](docs/ecr_deployment.md)
- [Deploying Lambdas from ECR Images](docs/ecr_deployment.md#deploying-lambdas-from-ecr-images)
