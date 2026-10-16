# Sourced (not executed) by the "Resolve digests" Run step, so the variables it
# sets become the step's output variables. Needs: REGISTRY, TAG.
# shellcheck shell=bash
set -euo pipefail

digest_of() {
  gcloud artifacts docker images describe "${REGISTRY}/$1:${TAG}" \
    --format='value(image_summary.digest)'
}

COST_API_DIGEST="$(digest_of cost-api)"
MCP_FINOPS_DIGEST="$(digest_of mcp-finops)"
AGENTS_DIGEST="$(digest_of agents)"

for d in "$COST_API_DIGEST" "$MCP_FINOPS_DIGEST" "$AGENTS_DIGEST"; do
  [[ "$d" == sha256:* ]] || { echo "could not resolve a digest for tag ${TAG}" >&2; exit 1; }
done
echo "cost-api   ${COST_API_DIGEST}"
echo "mcp-finops ${MCP_FINOPS_DIGEST}"
echo "agents     ${AGENTS_DIGEST}"
export COST_API_DIGEST MCP_FINOPS_DIGEST AGENTS_DIGEST
