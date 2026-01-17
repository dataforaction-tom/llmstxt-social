#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}"
  exit 1
fi

declare -A env_map
while IFS='=' read -r key value; do
  [[ -z "${key}" ]] && continue
  [[ "${key}" =~ ^# ]] && continue
  env_map["${key}"]="${value}"
done < "${ENV_FILE}"

required_keys=(
  ANTHROPIC_API_KEY
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  STRIPE_MONITORING_PRICE_ID
  VITE_STRIPE_PUBLIC_KEY
  RESEND_API_KEY
  SECRET_KEY
  POSTGRES_PASSWORD
  BASE_URL
  FRONTEND_URL
  CORS_ORIGINS
)

missing=()
for key in "${required_keys[@]}"; do
  if [[ -z "${env_map[${key}]:-}" ]]; then
    missing+=("${key}")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "Missing required env keys:"
  printf "  - %s\n" "${missing[@]}"
  exit 2
fi

if [[ "${#env_map[SECRET_KEY]}" -lt 32 ]]; then
  echo "SECRET_KEY looks short; use 32+ random characters."
  exit 3
fi

echo "Env check passed: ${ENV_FILE}"
