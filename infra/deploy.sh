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
TEMPLATE_FILE="$(dirname "$0")/main.bicep"

echo "Deploying $PARAMS_FILE to resource group $RESOURCE_GROUP..."

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$TEMPLATE_FILE" \
  --parameters "@$PARAMS_FILE" \
  --output table
