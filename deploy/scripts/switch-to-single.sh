#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="${1:-/opt/llmstxt-social}"

if [[ ! -d "${STACK_DIR}" ]]; then
  echo "Missing stack directory: ${STACK_DIR}"
  exit 1
fi

cd "${STACK_DIR}"

if [[ ! -f "docker-compose.single.yml" ]]; then
  echo "Missing docker-compose.single.yml in ${STACK_DIR}"
  exit 1
fi

echo "Stopping any dev stack (docker-compose.yml)..."
if [[ -f "docker-compose.yml" ]]; then
  docker compose -f docker-compose.yml down
fi

echo "Starting single-VM stack..."
docker compose -f docker-compose.single.yml up -d --build

echo "Running migrations..."
docker compose -f docker-compose.single.yml exec api alembic upgrade head

echo "Done."
echo "Note: avoid 'docker compose down -v' unless you intend to wipe the DB volume."
