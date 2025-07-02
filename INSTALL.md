# Installation Guide

This repository contains several AWS SAM templates. You can deploy all services or individual stacks depending on your workflow.

## Prerequisites
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- AWS credentials with permission to deploy Lambda functions and Step Functions
- Python 3.10 or newer

## Clone the Repository
```bash
git clone https://github.com/ameritascorp/aio-enterprise-ai-services.git
cd aio-enterprise-ai-services
```

## Dependency Layers
Each Lambda's Python dependencies are packaged in a layer under `common/layers/`. When you run `sam build` these layers are automatically created and attached to the functions. No additional `pip` install steps are required at the repository root.

## Deploying a Service
Navigate to the desired service directory and run `sam deploy` with any required parameters. For example, to deploy the file assembly service:
```bash
sam deploy \
  --template-file services/file-assembly/template.yaml \
  --stack-name file-assembly \
  --parameter-overrides AWSAccountName=<name>
```
Consult each service README for the full list of parameters and environment variables.

