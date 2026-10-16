#!/bin/sh
# Fail the build on fixable CRITICAL vulnerabilities and write a CycloneDX SBOM per image.
# Runs in the aquasec/trivy image; Trivy authenticates to Artifact Registry with the
# build pod's Workload Identity (Application Default Credentials). Needs REGISTRY and
# the three *_DIGEST variables.
set -eu

mkdir -p sbom
for pair in "cost-api:${COST_API_DIGEST}" "mcp-finops:${MCP_FINOPS_DIGEST}" "agents:${AGENTS_DIGEST}"; do
  svc="${pair%%:*}"
  ref="${REGISTRY}/${svc}@${pair#*:}"
  echo "== ${ref}"
  trivy image --quiet --severity CRITICAL --ignore-unfixed --exit-code 1 "${ref}"
  trivy image --quiet --format cyclonedx --output "sbom/${svc}.cdx.json" "${ref}"
done
