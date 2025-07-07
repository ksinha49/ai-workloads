# Enterprise AI Services

Enterprise AI Services is a collection of AWS Lambda microservices for building serverless document processing workflows. Each service focuses on a specific task such as OCR extraction, PDF assembly or embedding generation.

## Services

The repository includes the following directories under `services/`:

- `file-assembly` – merges summary pages with the original PDF
- `file-ingestion` – copies files to the IDP bucket and polls for text
  extraction status
- `idp` – Intelligent Document Processing pipeline (classification, OCR and text extraction)
- `zip-processing` – extracts PDFs from uploaded archives and assembles new ZIPs
- `rag-stack` – combined ingestion and retrieval Lambdas used for RAG workflows
- `vector-db` – manages Milvus collections and search Lambdas
 - `summarization` – runs the summarization workflow and generates PDF or DOCX reports
- `llm-gateway` – renders templates and routes requests to the selected LLM backend
- `knowledge-base` – ingest text snippets and query them through the retrieval stack
- `sensitive-info-detection` – PII/PHI detection for text including legal entities
- `entity-tokenization` – replaces sensitive entities with stable tokens
- `text-anonymization` – replaces or masks detected entities in text

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
cd aio-enterprise-ai-services
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

- [docs/idp_output_format.md](docs/idp_output_format.md)
- [docs/router_configuration.md](docs/router_configuration.md) – LLM Gateway router parameters and heuristics
- [docs/summarization_workflow.md](docs/summarization_workflow.md) – APS summarization workflow from ZIP upload through final ZIP
- [docs/prompt_engine.md](docs/prompt_engine.md)
- [docs/knowledge_rag_usage.md](docs/knowledge_rag_usage.md)
- [docs/rag_architecture.md](docs/rag_architecture.md)
- [docs/event_schemas.md](docs/event_schemas.md)
- [docs/entity_tokenization_service.md](docs/entity_tokenization_service.md)
- [docs/tokenization_workflow.md](docs/tokenization_workflow.md)
- [docs/environment_variables.md](docs/environment_variables.md)
- [docs/file_ingestion_workflow.md](docs/file_ingestion_workflow.md)
- [docs/rag_ingestion_workflow.md](docs/rag_ingestion_workflow.md)
- [docs/ecr_deployment.md](docs/ecr_deployment.md)
- [Deploying Lambdas from ECR Images](docs/ecr_deployment.md#deploying-lambdas-from-ecr-images)
