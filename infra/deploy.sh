#!/usr/bin/env bash
# Deploys the cumulative infrastructure for one chapter.
#
# Usage: ./infra/deploy.sh infra/params/chapter-01.json [resource-group]
#
# This is the ONE deploy mechanism shared by every chapter -- each
# chapter's parameter file is the only thing that changes. Safe to
# re-run: an ARM deployment is idempotent, so running an earlier
# chapter's parameters again (or a later chapter's, if you skipped
# tearing down) only creates or updates what's actually missing.

set -euo pipefail

PARAMS_FILE="${1:?Usage: deploy.sh <params-file> [resource-group]}"
RESOURCE_GROUP="${2:-stock-research-book-rg}"
INFRA_DIR="$(dirname "$0")"
TEMPLATE_FILE="$INFRA_DIR/main.bicep"

# Chapter 3 onward: Postgres needs an administrator password. It's a
# @secure() parameter, so it never lives in the checked-in params file --
# generate one on first use and reuse it from a local, gitignored file for
# every later deployment in this test run.
PASSWORD_FILE="$INFRA_DIR/.postgres-admin-password"
if [ ! -f "$PASSWORD_FILE" ]; then
  echo "$(openssl rand -hex 12)Aa1!" > "$PASSWORD_FILE"
  chmod 600 "$PASSWORD_FILE"
fi
POSTGRES_ADMIN_PASSWORD="$(cat "$PASSWORD_FILE")"

echo "Deploying $PARAMS_FILE to resource group $RESOURCE_GROUP..."

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$TEMPLATE_FILE" \
  --parameters "@$PARAMS_FILE" \
  --parameters postgresAdminPassword="$POSTGRES_ADMIN_PASSWORD" \
  --output table
