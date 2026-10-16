#!/usr/bin/env bash
# Sign each image and its SBOM with cosign (Cloud KMS key), then create the Binary
# Authorization attestation the cluster requires at admission.
#
# Compare with the GitHub track: there, cosign signs *keylessly* with the workflow's
# OIDC identity (Sigstore Fulcio + Rekor). Harness has no GitHub-style OIDC identity
# that Fulcio trusts, so here the signing identity is a KMS key that only the
# harness-builder GSA may use. Both are keyless for humans: nobody holds a key file.
#
# Needs: REGISTRY, PROJECT, COSIGN_KEY, ATTESTOR_KEY_VERSION, *_DIGEST; sbom/ from the scan step.
set -euo pipefail

COSIGN_VERSION=v2.5.3
curl -fsSL -o /usr/local/bin/cosign \
  "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64"
curl -fsSL -o /tmp/cosign_checksums.txt \
  "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign_checksums.txt"
(cd /usr/local/bin && grep ' cosign-linux-amd64$' /tmp/cosign_checksums.txt | sed 's/cosign-linux-amd64/cosign/' | sha256sum -c -)
chmod +x /usr/local/bin/cosign

for pair in "cost-api:${COST_API_DIGEST}" "mcp-finops:${MCP_FINOPS_DIGEST}" "agents:${AGENTS_DIGEST}"; do
  svc="${pair%%:*}"
  ref="${REGISTRY}/${svc}@${pair#*:}"
  echo "== ${ref}"
  cosign sign --yes --tlog-upload=false --key "${COSIGN_KEY}" "${ref}"
  cosign attest --yes --tlog-upload=false --key "${COSIGN_KEY}" \
    --type cyclonedx --predicate "sbom/${svc}.cdx.json" "${ref}"
  gcloud beta container binauthz attestations sign-and-create \
    --artifact-url="${ref}" \
    --attestor=built-by-ci --attestor-project="${PROJECT}" \
    --keyversion="${ATTESTOR_KEY_VERSION}"
done
