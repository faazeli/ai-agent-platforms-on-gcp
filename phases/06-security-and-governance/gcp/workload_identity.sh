#!/usr/bin/env bash
# Lab 6.1 — keyless identity for every CostPilot workload on GKE.
#
# Pattern A (classic): a Kubernetes service account (KSA) impersonates a Google
# service account (GSA). IAM roles are granted to the GSA.
# Pattern B (direct): grant IAM roles straight to the KSA as a principal://
# identity, with no GSA at all. Fewer moving parts; not every Google API accepts it yet.
#
# Prerequisite: a GKE cluster with Workload Identity Federation enabled (Autopilot
# has it on by default; Phase 9 creates the cluster with OpenTofu).
#
# Usage: PROJECT=my-project NAMESPACE=costpilot ./gcp/workload_identity.sh
set -euo pipefail
: "${PROJECT:?Set PROJECT}"
NAMESPACE="${NAMESPACE:-costpilot}"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
POOL="${PROJECT}.svc.id.goog"

# One identity per service, each with the least privilege it needs.
setup_identity() {
  local svc="$1"; shift
  local gsa="${svc}-gsa@${PROJECT}.iam.gserviceaccount.com"
  echo "==> ${svc}: GSA ${gsa}"
  gcloud iam service-accounts describe "$gsa" --project "$PROJECT" >/dev/null 2>&1 \
    || gcloud iam service-accounts create "${svc}-gsa" --project "$PROJECT" --display-name "CostPilot ${svc}"

  local role
  for role in "$@"; do
    gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${gsa}" --role "$role" \
      --condition=None --quiet >/dev/null
  done

  # Pattern A: allow the KSA <namespace>/<svc> to impersonate the GSA.
  gcloud iam service-accounts add-iam-policy-binding "$gsa" --project "$PROJECT" \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:${POOL}[${NAMESPACE}/${svc}]" --quiet >/dev/null

  # ...and annotate the KSA so GKE knows which GSA to hand out (Phase 9's manifests
  # already carry this annotation; this is for clusters you set up by hand).
  if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    kubectl create serviceaccount "$svc" -n "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    kubectl annotate serviceaccount "$svc" -n "$NAMESPACE" --overwrite "iam.gke.io/gcp-service-account=${gsa}"
  fi
}

setup_identity cost-api   roles/bigquery.dataViewer roles/bigquery.jobUser
setup_identity mcp-finops                       # calls cost-api only: needs no Google API roles
setup_identity agents     roles/modelarmor.user # screens prompts with Model Armor
setup_identity litellm    roles/aiplatform.user # the gateway is the only caller of Vertex AI

cat <<EOT

Pattern B, for comparison (no GSA): grant a role directly to the KSA identity:

  gcloud projects add-iam-policy-binding ${PROJECT} --role roles/bigquery.dataViewer \\
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/subject/ns/${NAMESPACE}/sa/cost-api"

Verify from inside a pod:
  kubectl run -n ${NAMESPACE} wi-test --rm -it --image=google/cloud-sdk:slim \\
    --overrides='{"spec":{"serviceAccountName":"cost-api"}}' -- gcloud auth list
Then confirm there are no keys anywhere:
  gcloud iam service-accounts keys list --iam-account cost-api-gsa@${PROJECT}.iam.gserviceaccount.com --managed-by=user
EOT
