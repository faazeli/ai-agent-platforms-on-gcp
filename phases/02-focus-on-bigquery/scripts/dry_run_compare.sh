#!/usr/bin/env bash
# Phase 2 · Lab 2.4 — prove that partitioning and clustering pay off.
#
# Creates an unpartitioned, unclustered copy of focus_costs, then dry-runs the
# same query against both tables and prints the bytes each would scan.
# Dry runs are free. Put both numbers in your ADR.
#
# Usage:  PROJECT=my-project ./scripts/dry_run_compare.sh
set -euo pipefail
: "${PROJECT:?Set PROJECT to your GCP project id}"
DATASET="${DATASET:-finops}"

echo "==> Creating ${DATASET}.focus_costs_flat (no partitions, no clustering)"
bq query --project_id="$PROJECT" --use_legacy_sql=false --quiet \
  "CREATE OR REPLACE TABLE ${DATASET}.focus_costs_flat AS
   SELECT * FROM ${DATASET}.focus_costs WHERE ChargePeriodStart >= TIMESTAMP('2000-01-01')"

QUERY='SELECT ServiceName, SUM(EffectiveCost) AS cost
FROM `TABLE`
WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))
  AND x_TeamId = "payments"
GROUP BY ServiceName'

bytes() {
  local table="$1"
  bq query --project_id="$PROJECT" --use_legacy_sql=false --dry_run --format=json \
    "${QUERY//TABLE/${PROJECT}.${DATASET}.${table}}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["statistics"]["totalBytesProcessed"])'
}

PARTITIONED=$(bytes focus_costs)
FLAT=$(bytes focus_costs_flat)
echo
printf "%-28s %15s bytes\n" "partitioned + clustered:" "$PARTITIONED"
printf "%-28s %15s bytes\n" "flat copy:" "$FLAT"
python3 -c "p,f=$PARTITIONED,$FLAT; print(f'Scanned {p/f*100:.1f}% of the flat table\'s bytes.' if f else 'Flat table is empty')"
echo
echo "Note: dry runs estimate before clustering's block pruning, so the real saving"
echo "from clustering only shows in the job's bytes billed after it runs."
echo "Also try the query without the date filter on focus_costs: it should fail,"
echo "because require_partition_filter is on."
echo
echo "Clean up the copy when done:  bq rm -f -t ${PROJECT}:${DATASET}.focus_costs_flat"
