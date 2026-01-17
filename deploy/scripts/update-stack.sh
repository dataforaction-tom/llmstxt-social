#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="${1:-/opt/llmstxt-social}"

if [[ ! -d "${STACK_DIR}" ]]; then
  echo "Missing stack directory: ${STACK_DIR}"
  exit 1
fi

cd "${STACK_DIR}"

echo "Updating repo..."
git pull --rebase

if [[ -f ".env" ]]; then
  ./deploy/scripts/check-env.sh .env
fi

echo "Rebuilding and restarting containers..."
docker compose -f docker-compose.single.yml up -d --build

echo "Running migrations..."
docker compose -f docker-compose.single.yml exec api alembic upgrade head

echo "Done."
