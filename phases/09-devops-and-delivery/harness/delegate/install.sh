#!/usr/bin/env bash
# Install a Harness delegate into the current kubectl context (Lab 9.H2).
#
#   PROJECT_ID=my-dev-project ENV=dev HARNESS_ACCOUNT_ID=... HARNESS_DELEGATE_TOKEN=... \
#   DELEGATE_IMAGE=us-central1-docker.pkg.dev/my-dev-project/costpilot/harness-delegate:<tag>-k5 \
#   ./install.sh
#
# Prerequisites: the cluster from Lab 9.2, the GSAs from harness/infra (tofu), and
# the delegate image built from ./Dockerfile and pushed (it must be attested too, or
# Binary Authorization will refuse it: run the sign step from the CI stage by hand once).
set -euo pipefail
: "${PROJECT_ID:?}" "${ENV:?}" "${HARNESS_ACCOUNT_ID:?}" "${HARNESS_DELEGATE_TOKEN:?}" "${DELEGATE_IMAGE:?}"
MANAGER_ENDPOINT="${MANAGER_ENDPOINT:-https://app.harness.io}"   # your Harness cluster's URL
NAME="costpilot-gke-${ENV}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# The platform namespace (restricted Pod Security) exists before the first deploy,
# because the delegate is not allowed to create namespaces.
kubectl apply -f "${HERE}/../../deploy/k8s/base/namespace.yaml"

helm repo add harness-delegate https://app.harness.io/storage/harness-download/delegate-helm-chart/
helm repo update harness-delegate
helm upgrade --install "${NAME}" harness-delegate/harness-delegate-ng \
  --namespace harness-delegate-ng --create-namespace \
  --set delegateName="${NAME}" \
  --set accountId="${HARNESS_ACCOUNT_ID}" \
  --set delegateToken="${HARNESS_DELEGATE_TOKEN}" \
  --set managerEndpoint="${MANAGER_ENDPOINT}" \
  --set delegateDockerImage="${DELEGATE_IMAGE}" \
  --set replicas=1 \
  --set upgrader.enabled=false \
  --set k8sPermissionsType=NAMESPACE_ADMIN

# Find the delegate's KSA instead of guessing the chart's naming.
SA="$(kubectl -n harness-delegate-ng get deploy "${NAME}" -o jsonpath='{.spec.template.spec.serviceAccountName}')"
echo "delegate service account: ${SA}"

sed -e "s/DELEGATE_SA/${SA}/g" -e "s/PROJECT_ID/${PROJECT_ID}/g" "${HERE}/rbac.yaml" | kubectl apply -f -

# Workload Identity: the delegate's KSA acts as the harness-delegate GSA.
kubectl -n harness-delegate-ng annotate serviceaccount "${SA}" --overwrite \
  "iam.gke.io/gcp-service-account=harness-delegate@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts add-iam-policy-binding \
  "harness-delegate@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/iam.workloadIdentityUser \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[harness-delegate-ng/${SA}]" --quiet
kubectl -n harness-delegate-ng rollout restart deploy "${NAME}"
kubectl -n harness-delegate-ng rollout status deploy "${NAME}" --timeout=5m
echo "Delegate ${NAME} is up. Check Harness → Project settings → Delegates."
