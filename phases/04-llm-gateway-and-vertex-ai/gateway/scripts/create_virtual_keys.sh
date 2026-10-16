#!/usr/bin/env bash
# Lab 4.2 — one virtual key per agent, each with its own budget and allowed models.
# A runaway agent hits its own budget and stops; the others keep working.
#
# Usage: LITELLM_MASTER_KEY=sk-... ./scripts/create_virtual_keys.sh
# Prints an export line per key. Store real keys in Secret Manager (Phase 6/9), not in files.
set -euo pipefail
: "${LITELLM_MASTER_KEY:?Set LITELLM_MASTER_KEY}"
GATEWAY="${GATEWAY:-http://localhost:4000}"

create_key() {
  local alias="$1" team="$2" budget="$3" models="$4"
  curl -sS -X POST "$GATEWAY/key/generate" \
    -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
    -d "{\"key_alias\": \"$alias\", \"models\": $models, \"max_budget\": $budget,
         \"budget_duration\": \"30d\", \"metadata\": {\"agent\": \"$alias\", \"team\": \"$team\"}}" \
  | ALIAS="$alias" python3 -c 'import json, os, sys
key = json.load(sys.stdin)["key"]
name = os.environ["ALIAS"].upper().replace("-", "_") + "_VKEY"
print("export " + name + "=" + key)'
}

create_key coordinator      finops 2  '["fast"]'
create_key cost-analyst     finops 5  '["smart", "fast"]'
create_key anomaly-detector finops 2  '["fast"]'
create_key recommender      finops 5  '["smart", "fast"]'
create_key eval-runner      finops 10 '["smart", "fast"]'
echo "# Budgets are in USD per 30 days. Check spend: curl -s $GATEWAY/key/info?key=<key> -H 'Authorization: Bearer \$LITELLM_MASTER_KEY'"
