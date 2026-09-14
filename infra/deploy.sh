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

# Chapter 5 onward: the worker's real MCP search tool needs a Tavily
# credential. Also a gitignored local file, never checked in.
TAVILY_KEY_FILE="$INFRA_DIR/.tavily-api-key"
TAVILY_API_KEY="$(cat "$TAVILY_KEY_FILE" 2>/dev/null || true)"

# Chapter 3 onward: the params files reference container images by
# registry, and Chapter 7/9/13/18 onward reference an APIM publisher
# email, an Entra ID app, an allow-listed sign-in identity, and the
# deployed frontend's origin. None of those belong in a checked-in file --
# each reader's values are different. The params files hold placeholder
# tokens instead (YOUR_REGISTRY.azurecr.io, YOUR_EMAIL@example.com, and so
# on); this script substitutes your own values from a local, gitignored
# config file before deploying. Copy infra/.local-config.example to
# infra/.local-config and fill in what the chapter you're deploying needs --
# see the "Stage-by-stage reference" table in azure-setup.md for which
# chapter introduces which value.
LOCAL_CONFIG="$INFRA_DIR/.local-config"
if [ -f "$LOCAL_CONFIG" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$LOCAL_CONFIG"
  set +a
fi

RESOLVED_PARAMS_FILE="$(mktemp)"
trap 'rm -f "$RESOLVED_PARAMS_FILE"' EXIT
cp "$PARAMS_FILE" "$RESOLVED_PARAMS_FILE"

substitute() {
  local token="$1"
  local value="${2:-}"
  if [ -n "$value" ]; then
    local escaped
    escaped=$(printf '%s' "$value" | sed -e 's/[\/&|]/\\&/g')
    sed -i.bak "s|$token|$escaped|g" "$RESOLVED_PARAMS_FILE"
    rm -f "$RESOLVED_PARAMS_FILE.bak"
  fi
}

substitute "YOUR_REGISTRY.azurecr.io" "${REGISTRY_LOGIN_SERVER:-}"
substitute "YOUR_EMAIL@example.com" "${APIM_PUBLISHER_EMAIL:-}"
substitute "YOUR_ALLOWED_USERS@example.com" "${ALLOWED_USERS:-}"
substitute "YOUR_ENTRA_CLIENT_ID" "${ENTRA_CLIENT_ID:-}"
substitute "YOUR_ENTRA_TENANT_ID" "${ENTRA_TENANT_ID:-}"
substitute "https://YOUR_STATIC_WEB_APP_HOSTNAME" "${ALLOWED_ORIGIN:-}"

if grep -qE "YOUR_REGISTRY|YOUR_EMAIL@example.com|YOUR_ALLOWED_USERS@example.com|YOUR_ENTRA_CLIENT_ID|YOUR_ENTRA_TENANT_ID|YOUR_STATIC_WEB_APP_HOSTNAME" "$RESOLVED_PARAMS_FILE"; then
  echo "Warning: $PARAMS_FILE still has unresolved placeholder values." >&2
  echo "Set the matching variable in $LOCAL_CONFIG (see .local-config.example) and re-run." >&2
  grep -oE '"[A-Za-z]+": \{\s*"value": "[^"]*YOUR_[^"]*"' "$RESOLVED_PARAMS_FILE" >&2 || true
fi

echo "Deploying $PARAMS_FILE to resource group $RESOURCE_GROUP..."

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$TEMPLATE_FILE" \
  --parameters "@$RESOLVED_PARAMS_FILE" \
  --parameters postgresAdminPassword="$POSTGRES_ADMIN_PASSWORD" \
  --parameters tavilyApiKey="$TAVILY_API_KEY" \
  --output table
