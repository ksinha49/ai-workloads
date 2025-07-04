#!/bin/bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <account-id> <region> [tag]" >&2
  exit 1
fi

ACCOUNT_ID="$1"
REGION="$2"
TAG="${3:-latest}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
export ECR_REGISTRY TAG

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker compose -f docker-compose.ecr.yml build

docker compose -f docker-compose.ecr.yml push
