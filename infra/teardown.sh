#!/usr/bin/env bash
# Deletes the entire book test resource group.
#
# Run this once, after testing every chapter straight through --
# not between chapters. Deleting the whole resource group is simpler
# and safer than tearing down individual resources: nothing can be
# left orphaned.

set -euo pipefail

RESOURCE_GROUP="${1:-stock-research-book-rg}"

echo "This will permanently delete the resource group: $RESOURCE_GROUP"
read -p "Type the resource group name to confirm: " CONFIRM
if [ "$CONFIRM" != "$RESOURCE_GROUP" ]; then
  echo "Confirmation did not match. Aborting."
  exit 1
fi

az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "Deletion of $RESOURCE_GROUP started (running in the background)."
