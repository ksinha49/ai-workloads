#!/bin/bash
set -euo pipefail

# Usage: ./scripts/deploy_lambda_image.sh <function-name> <account-id> <region> [tag]
#
# Update a Lambda function to use a container image stored in ECR. The optional
# tag defaults to "latest".

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <function-name> <account-id> <region> [tag]" >&2
  exit 1
fi

FUNCTION_NAME="$1"
ACCOUNT_ID="$2"
REGION="$3"
TAG="${4:-latest}"
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${FUNCTION_NAME}:${TAG}"

aws lambda update-function-code --function-name "$FUNCTION_NAME" --image-uri "$IMAGE_URI"

