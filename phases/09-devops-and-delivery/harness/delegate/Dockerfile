# Harness delegate with a current kustomize.
#
# Harness bundles kustomize 3.5.4 (4.0.0 behind a feature flag). Our overlays use
# kustomize 5 features (labels, replacements, includeTemplates), so the delegate gets
# the same kustomize the GitHub track and the course tests use, via KUSTOMIZE_PATH.
#
# Build:  docker build --build-arg DELEGATE_TAG=<tag shown in Harness: Delegates → New Delegate> \
#           -t us-central1-docker.pkg.dev/PROJECT/costpilot/harness-delegate:<DELEGATE_TAG>-k5 .
ARG DELEGATE_TAG
FROM harness/delegate:${DELEGATE_TAG}

ARG KUSTOMIZE_VERSION=5.7.1
ARG TARGETARCH=amd64

USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /tmp
RUN base="https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}" \
 && tarball="kustomize_v${KUSTOMIZE_VERSION}_linux_${TARGETARCH}.tar.gz" \
 && curl -fsSLo "${tarball}" "${base}/${tarball}" \
 && curl -fsSLo checksums.txt "${base}/checksums.txt" \
 && grep " ${tarball}\$" checksums.txt | sha256sum -c - \
 && mkdir -p /opt/kustomize5 \
 && tar -xzf "${tarball}" -C /opt/kustomize5 kustomize \
 && rm -f "${tarball}" checksums.txt \
 && /opt/kustomize5/kustomize version

ENV KUSTOMIZE_PATH=/opt/kustomize5/kustomize
USER harness
