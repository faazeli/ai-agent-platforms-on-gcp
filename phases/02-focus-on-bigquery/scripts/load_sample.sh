#!/usr/bin/env bash
# Phase 2 · Lab 2.3 — create the dataset and table, then load fresh synthetic data.
#
# Usage:  PROJECT=my-project ./scripts/load_sample.sh            (from this phase's folder)
# Cost:   a few MB of storage and well under 1 GB of query bytes: effectively $0.
set -euo pipefail

: "${PROJECT:?Set PROJECT to your GCP project id}"
DATASET="${DATASET:-finops}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Swap the dataset name in the SQL files (portable across GNU and BSD sed).
sql() { sed -E "s/(^|[^A-Za-z_])finops\./\1${DATASET}./g; s/SCHEMA IF NOT EXISTS finops/SCHEMA IF NOT EXISTS ${DATASET}/" "$1"; }

echo "==> Generating 92 days of synthetic FOCUS data ending yesterday"
python3 "$ROOT/data/generate_sample.py" --recent --out "$TMP/focus.csv"

echo "==> Creating dataset ${PROJECT}:${DATASET} and table focus_costs"
sql "$HERE/sql/01_dataset_and_table.sql" | bq query --project_id="$PROJECT" --use_legacy_sql=false

echo "==> Loading CSV into staging table (all columns as STRING)"
SCHEMA="BillingAccountId:STRING,SubAccountId:STRING,ServiceProviderName:STRING,ServiceName:STRING,ServiceCategory:STRING,ChargeCategory:STRING,ChargePeriodStart:STRING,ChargePeriodEnd:STRING,BillingPeriodStart:STRING,BilledCost:STRING,EffectiveCost:STRING,ListCost:STRING,BillingCurrency:STRING,RegionId:STRING,ResourceId:STRING,Tags:STRING,x_TeamId:STRING"
bq load --project_id="$PROJECT" --replace --skip_leading_rows=1 --source_format=CSV \
  "${DATASET}.stg_focus_costs" "$TMP/focus.csv" "$SCHEMA"

echo "==> MERGE staging into focus_costs (safe to re-run)"
sql "$HERE/sql/02_load_merge.sql" | bq query --project_id="$PROJECT" --use_legacy_sql=false

echo "==> Dimensions and materialized view"
sql "$HERE/sql/03_dimensions_and_views.sql" | bq query --project_id="$PROJECT" --use_legacy_sql=false

echo "==> Row count per month"
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=pretty \
  "SELECT DATE_TRUNC(DATE(ChargePeriodStart), MONTH) AS month, COUNT(*) AS rows
   FROM ${DATASET}.focus_costs
   WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 120 DAY))
   GROUP BY month ORDER BY month"

echo "Done. Next: ./scripts/dry_run_compare.sh"
