# Enterprise AI Services

Enterprise AI Services is a collection of AWS Lambda microservices for building serverless document processing workflows. Each service focuses on a specific task such as OCR extraction, PDF assembly or embedding generation.

## Services

The repository includes the following directories under `services/`:

- `file-assembly` – merges summary pages with the original PDF
- `file-ingestion` – copies files to the IDP bucket and polls for text
  extraction status
- `idp` – Intelligent Document Processing pipeline (classification, OCR and text extraction)
- `zip-processing` – extracts PDFs from uploaded archives and assembles new ZIPs
- `rag-ingestion` – chunks text and generates embeddings stored in Milvus
- `rag-ingestion-worker` – dequeues SQS messages and starts the ingestion state
  machine
- `vector-db` – manages Milvus collections and search Lambdas
- `rag-retrieval` – retrieval functions and API endpoints for summarization or entity extraction
- `summarization` – Step Function workflow orchestrating file processing and summary generation
- `prompt-engine` – renders templates from DynamoDB and forwards them to the router
- `llm-router` – routes prompts via heuristic, predictive and cascading strategies to Amazon Bedrock or local Ollama
- `llm-invocation` – forwards OpenAI-style requests to a specific LLM backend
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
- [docs/router_configuration.md](docs/router_configuration.md)
- [docs/summarization_workflow.md](docs/summarization_workflow.md)
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
