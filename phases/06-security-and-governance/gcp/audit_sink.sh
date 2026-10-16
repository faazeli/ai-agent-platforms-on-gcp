#!/usr/bin/env bash
# Lab 6.4 — make audit entries immutable: Cloud Logging → Cloud Storage with Bucket Lock.
#
# Services write audit entries as JSON to stdout (costpilot_security.audit).
# On GKE those become log entries with jsonPayload.event_type="audit". A log sink
# copies them to a bucket whose retention policy is LOCKED: no one, including
# project owners, can delete or overwrite objects until they are RETENTION old.
#
# ⚠ Locking is permanent. A locked bucket cannot be deleted until every object in
# it has aged past retention. For the lab, use a short retention (1 day) and a
# throwaway bucket. In production choose the period with your compliance team.
#
# Usage: PROJECT=my-project BUCKET=my-project-costpilot-audit RETENTION=1d ./gcp/audit_sink.sh [--lock]
set -euo pipefail
: "${PROJECT:?Set PROJECT}"; : "${BUCKET:?Set BUCKET}"
RETENTION="${RETENTION:-1d}"
LOCATION="${LOCATION:-us}"

gcloud storage buckets describe "gs://${BUCKET}" --project "$PROJECT" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT" --location "$LOCATION" \
    --uniform-bucket-level-access --public-access-prevention

gcloud storage buckets update "gs://${BUCKET}" --retention-period="$RETENTION"

gcloud logging sinks describe costpilot-audit --project "$PROJECT" >/dev/null 2>&1 || \
  gcloud logging sinks create costpilot-audit "storage.googleapis.com/${BUCKET}" --project "$PROJECT" \
    --log-filter='jsonPayload.event_type="audit"'

WRITER="$(gcloud logging sinks describe costpilot-audit --project "$PROJECT" --format='value(writerIdentity)')"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member "$WRITER" --role roles/storage.objectCreator

if [[ "${1:-}" == "--lock" ]]; then
  echo "Locking the retention policy on gs://${BUCKET}. This cannot be undone."
  gcloud storage buckets update "gs://${BUCKET}" --lock-retention-period
fi

cat <<EOT
Sink ready. Log files arrive in gs://${BUCKET} in hourly batches.
Verify a chain:   gcloud storage cat "gs://${BUCKET}/**/*.json" | python -m costpilot_security.audit
(Cloud Logging wraps each entry; extract jsonPayload first, e.g. with jq '.jsonPayload' -c.)
EOT
