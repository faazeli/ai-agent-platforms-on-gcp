# Phase 9 — Docker, OpenTofu, GKE and modern CI/CD

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 23–25 (≈ 35 h) | ≈ $3–6 per day while the dev cluster runs; destroy it between sessions | Phases 1–8 | Hardened images; the whole platform as OpenTofu; GKE manifests with default-deny networking; keyless CI/CD with an eval gate; GitOps with canaries; signed images; traces, SLOs and DORA metrics |

## Why this phase matters

Everything so far runs because you started it by hand. In production, nothing should depend on a person's laptop, credentials or memory. The goal: a fresh project goes from empty to a working CostPilot through the pipeline alone; no human holds production credentials; every change, including a prompt change, is a reviewed commit that is tested, evaluated, signed, canaried and traced.

> **Verification note.** When the course was built, the delivery assets were checked with hadolint (Dockerfiles), kustomize and kubeconform (all rendered manifests against Kubernetes schemas, Argo CD and Argo Rollouts CRD schemas), actionlint (workflows) and `tofu fmt` (HCL). `docker build`, `tofu plan/apply` and the workflows themselves could not be run in the authoring environment. Expect to adjust small things such as action versions and provider arguments, and please open an issue when you do.

## You will learn

- Production container images: multi-stage builds, non-root users, small attack surface, digests instead of tags
- OpenTofu: modules, remote state, plan-in-PR, apply-from-CI, destroy-and-rebuild
- GKE Autopilot deployment patterns: requests and limits, probes, HPA, PDB, Pod Security Standards, Workload Identity, default-deny NetworkPolicy, Kustomize overlays
- Keyless CI/CD with GitHub Actions and Workload Identity Federation
- An **eval gate**: prompt and agent changes can't ship if they lower accuracy
- GitOps with Argo CD, and progressive delivery with Argo Rollouts canaries judged by agent evals
- Supply-chain security: SBOMs, SLSA provenance, cosign signatures, Binary Authorization
- Observability: OpenTelemetry traces across services, SLOs with burn-rate alerts, DORA metrics next to AI metrics

## Before you start

1. Tools: Docker, `gcloud`, `kubectl`, `kustomize`, [OpenTofu](https://opentofu.org/docs/intro/install/) 1.8+, and a GitHub repository holding your copy of this course.
2. Your Phase 8 sizing ADR: the runtime and capacity you decided on are what you codify here.
3. Read (about 3 hours):
   - [Dockerfile best practices](https://docs.docker.com/build/building/best-practices/)
   - [OpenTofu: modules and state](https://opentofu.org/docs/language/modules/), and the [Google provider docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs) for the resources you use
   - [GKE Autopilot security](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-security) and [network policies](https://cloud.google.com/kubernetes-engine/docs/how-to/network-policy)
   - [Workload Identity Federation for GitHub Actions](https://github.com/google-github-actions/auth#workload-identity-federation-through-a-service-account)
   - [Argo CD getting started](https://argo-cd.readthedocs.io/en/stable/getting_started/), [Argo Rollouts canary](https://argoproj.github.io/argo-rollouts/features/canary/)
   - [SLSA](https://slsa.dev/spec/v1.0/levels), [Binary Authorization](https://cloud.google.com/binary-authorization/docs/overview), [DORA's four keys](https://dora.dev/guides/dora-metrics-four-keys/)

## What's in this folder

```
docker/          cost-api, mcp-finops, agents Dockerfiles + compose.yaml (whole stack locally)
infra/tofu/      modules: network, gke, bigquery, iam, artifact_registry, audit, supply_chain
                 envs/dev: the dev environment composed from the modules
deploy/k8s/      base (hardened manifests, default-deny NetworkPolicy) + overlays dev/prod
deploy/argocd/   GitOps applications
deploy/rollouts/ agents canary gated by in-cluster agent evals
ci/github-workflows/  app-ci, eval-gate, infra, promote-prod  (copy to .github/workflows/)
observability/   OpenTelemetry setup, SLO definitions
dora/            DORA metrics from a deployments log
harness/         Track B: the same pipeline in Harness (CI, eval-gated canary, CV, approvals, OPA)
tests/           offline checks for all of the above
starter/         the same tree with gaps for Labs 9.1–9.4 (work here)
```

```bash
cd phases/09-devops-and-delivery
pip install pyyaml pytest
pytest -q starter/tests     # fails until the starter gaps are filled; uses kustomize/kubeconform/hadolint/actionlint/tofu if installed
pytest -q tests             # the reference passes
```

## Two tracks for delivery

Labs 9.1–9.3 (images, infrastructure, cluster) are shared. Delivery then comes in two tracks that ship the **same platform through the same gates**:

| | Track A: GitHub Actions + Argo (Labs 9.4–9.6) | Track B: Harness ([`harness/`](harness/), Labs 9.H1–9.H7) |
| --- | --- | --- |
| Model | Assemble best-of-breed open tools; Git is the glue | One platform for CI, CD, verification, approvals and audit |
| Deploy style | GitOps pull (Argo CD syncs from Git) | Push from inside the cluster (delegate runs tasks) |
| Canary judged by | Agent evals in an Argo AnalysisRun | The **same** agent eval Job as a pipeline step, plus optional ML-based Continuous Verification |
| Credentials | GitHub OIDC → Workload Identity Federation | Delegate and build pods use Workload Identity |
| Signing | cosign keyless (Sigstore) | cosign with a Cloud KMS key |
| Guardrails | Branch protection, protected environments | OPA policies on the pipeline, approver ≠ executor |
| You operate | Argo CD, Argo Rollouts | A delegate; Harness itself is SaaS |

Do Track A first: it shows every moving part. Track B is optional, and most useful if your organization uses Harness or is choosing a delivery platform. Lab 9.H7 compares the tracks with measurements from your own runs.

## Labs

### Lab 9.1 — Small, safe images

`starter/docker/cost-api.Dockerfile` works but is not production-ready (single stage, runs as root, copies the whole repo). Rewrite it following the comments, then write the `mcp-finops` and `agents` images. Compare with `docker/`.

```bash
docker build -f phases/09-devops-and-delivery/starter/docker/cost-api.Dockerfile -t cost-api:naive .    # from the repo root
docker build -f phases/09-devops-and-delivery/docker/cost-api.Dockerfile -t cost-api:hardened .
docker images | grep cost-api            # compare sizes
hadolint phases/09-devops-and-delivery/starter/docker/*.Dockerfile
docker run --rm -e COST_API_AUTH_ENABLED=false -p 8000:8000 cost-api:hardened
docker compose -f phases/09-devops-and-delivery/docker/compose.yaml up --build    # the whole stack
```

Then add lock files: `uv lock` in each Python package, and install from the lock in the build stage, so an image built next month has the same dependencies as today's. For Java, `mvn jib:build` (Phase 7's POM) builds a distroless image without a Dockerfile.

### Lab 9.2 — Infrastructure as code with OpenTofu

Write the three missing modules in `starter/infra/tofu/modules` (`bigquery`, `iam`, `artifact_registry`) so that `envs/dev` creates everything Phases 1–8 run on. Each module's header comment says what it must create. Compare with `infra/tofu/modules`. Every resource gets `team`, `service` and `env` labels through the provider's `default_labels`, so its cost lands in FOCUS `Tags` (Phase 8, Lab 8.5).

```bash
gcloud storage buckets create gs://$PROJECT-tofu-state --location=US --uniform-bucket-level-access
gcloud storage buckets update gs://$PROJECT-tofu-state --versioning
cd infra/tofu/envs/dev
tofu init -backend-config="bucket=$PROJECT-tofu-state"
tofu plan -var project_id=$PROJECT -out plan.out
```

Practice the full cycle once by hand on a throwaway project, then never again: `tofu apply`, deploy (Lab 9.3), `tofu destroy`, and rebuild from scratch to prove it is reproducible. From then on, plans run in pull requests and applies run from CI (`ci/github-workflows/infra.yml`) after an approver signs off.

### Lab 9.3 — GKE deployment patterns

Read `deploy/k8s/base`. Every workload gets the same hardened baseline: its own Kubernetes service account bound to its Google service account (Workload Identity), requests and limits sized from Phase 8, readiness and liveness probes, an HPA, a PDB, a non-root read-only container with every capability dropped, and the namespace enforces the *restricted* Pod Security Standard.

1. Fill in the allow rules in `starter/deploy/k8s/base/networkpolicies.yaml`. Start from default-deny and open exactly the calls in the architecture: agents → gateway, agents → MCP, MCP → cost-api, plus Google APIs and the metadata server.
2. Set your project id once in each overlay (`project_id`, `sa_domain`). Kustomize `replacements` push it into every Workload Identity annotation and env value, so no `sed` step is needed.
3. Deploy dev by hand once to see it work:

```bash
gcloud container clusters get-credentials costpilot --region us-central1
kubectl create secret generic agent-gateway-keys -n costpilot \
  --from-literal=COORDINATOR_VKEY=... --from-literal=COST_ANALYST_VKEY=... \
  --from-literal=ANOMALY_DETECTOR_VKEY=... --from-literal=RECOMMENDER_VKEY=... --from-literal=OPENAI_API_KEY=...
kubectl create secret generic litellm -n costpilot --from-literal=master-key=... --from-literal=database-url=...
kustomize build deploy/k8s/overlays/dev | kubectl apply -f -
kubectl -n costpilot get pods
```

Prove the network policy works: `kubectl -n costpilot exec deploy/agents -- python -c "import urllib.request; urllib.request.urlopen('http://cost-api:8000/healthz', timeout=3)"` must time out (agents may not call `cost-api` directly), while the same call from `mcp-finops` succeeds. For real deployments, move the secrets into Secret Manager and mount them with the Secret Manager CSI driver.

### Lab 9.4 — CI/CD without keys

1. Create a Workload Identity Federation pool for GitHub, restricted to your repository:

```bash
gcloud iam workload-identity-pools create github --location=global
gcloud iam workload-identity-pools providers create-oidc github --location=global \
  --workload-identity-pool=github --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='YOUR_ORG/YOUR_REPO'"
# then allow the pool to impersonate a CI service account:
gcloud iam service-accounts add-iam-policy-binding ci@$PROJECT.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/YOUR_ORG/YOUR_REPO"
```

2. Set repository variables `GCP_PROJECT`, `WIF_PROVIDER`, `CI_SERVICE_ACCOUNT`, `EVAL_SERVICE_ACCOUNT`, `TOFU_PLAN_SERVICE_ACCOUNT`, `TOFU_APPLY_SERVICE_ACCOUNT`.
3. Complete `starter/ci/github-workflows/app-ci.yml` with the `build-sign-push` and `promote-dev` jobs, then compare with `ci/github-workflows/`. Copy the workflows into `.github/workflows/`.

The pipeline: lint and unit tests (Python and Java, with Java's contract fixtures refreshed from the Python API) → build with SBOM and provenance → Trivy scan fails on critical vulnerabilities → cosign keyless signature → Binary Authorization attestation → the new digests are committed to the dev overlay, and Argo CD deploys them.

**The eval gate** (`eval-gate.yml`) runs on any PR that touches prompts, agent instructions, MCP tool descriptions or the gateway config. It starts a LiteLLM gateway inside the job (with short-lived credentials from WIF), runs Phase 4's eval set twice, and fails below 85% accuracy. A prompt change is a code change: tested, reviewed and gated.

### Lab 9.5 — GitOps and progressive delivery

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
kubectl apply -f deploy/argocd/applications.yaml    # edit repoURL first
kubectl apply -f deploy/rollouts/agents-canary.yaml
```

- **GitOps:** dev syncs automatically from `main`; prod syncs when a human reviews Argo CD's diff and clicks Sync. Nobody runs `kubectl apply` against prod. `promote-prod.yml` copies the exact digests running in dev into the prod overlay.
- **Canary judged by evals:** the agents Rollout shifts 10% → 50% → 100%, and between steps an AnalysisRun runs the Phase 5 agent evals *against the canary*. If accuracy drops below 0.8, the rollout aborts and traffic returns to the stable version. In dev, `cost-api` serves the course's sample data so the eval set's expected answers hold; for prod, point canary evals at a frozen eval dataset (for example a BigQuery snapshot) or limit them to trajectory checks.
- **Prompts as releases:** prompts and model aliases ship inside images and config, so they canary exactly like code. Try it: change the cost analyst's instruction to something worse, push, and watch the canary abort.

### Lab 9.6 — Secure the software supply chain

1. Inspect what the build attached: `docker buildx imagetools inspect $IMAGE --format '{{json .SBOM}}'` and `--format '{{json .Provenance}}'`.
2. Verify a signature: `cosign verify $IMAGE@$DIGEST --certificate-identity-regexp 'https://github.com/YOUR_ORG/YOUR_REPO/.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com`.
3. Turn on Binary Authorization: apply `infra` with `enable_binary_authorization=true` (it creates a KMS key, an attestor and an enforcing policy), set `BINAUTHZ_ENABLED=true` and `BINAUTHZ_KEY_VERSION` in the repo variables, and redeploy. Then try `kubectl run test --image=nginx -n costpilot`: it must be rejected.
4. Pin every GitHub Action by commit SHA and let Renovate or Dependabot open update PRs. Your tests and the eval gate decide whether they merge.

### Lab 9.7 — Observability and delivery metrics

1. Call `observability/otel_setup.configure_tracing("<service>", app)` at startup in each Python service (cost-api, mcp-finops, and the agents' API server), redeploy, ask CostPilot a question, and find the single trace in Cloud Trace spanning agents → gateway → MCP → cost-api → BigQuery.
2. Create the two SLOs from `observability/slos.md` with fast- and slow-burn alerts.
3. Build one dashboard with the four DORA metrics (`python dora/dora_metrics.py deployments.csv`) next to the AI signals: tokens per question, cost per question, eval accuracy per release, guardrail block rate.

## Done when

- [ ] A fresh project goes from empty to a working CostPilot through the pipelines alone
- [ ] No human holds a service-account key; CI authenticates through Workload Identity Federation
- [ ] A failing eval blocks a prompt change in CI, and a bad canary rolls itself back
- [ ] Every production change is a Git commit that was tested, signed, attested and canaried
- [ ] An unsigned image is rejected by the cluster
- [ ] One question produces one trace across all services, and your SLO and DORA dashboards are live
- [ ] `pytest -q starter/tests` passes

## Write it down (ADRs)

- `0014-delivery-pipeline.md`: GitOps versus push deploys; canary analysis with evals; what blocks a release
- `0015-supply-chain.md`: which SLSA level you claim and why; signing and admission policy
- `0016-delivery-platform.md` (if you did Track B): Track A or Track B for your team, backed by Lab 9.H7's measurements

## Teach it (5 minutes)

Make a deliberately bad prompt change and let the audience watch the eval gate fail the PR. Then ask: what stops a bad prompt from reaching production in your team today?

## Stretch goals

- Replace standard NetworkPolicy egress to Google APIs with GKE FQDN network policies naming only the API hostnames.
- Add a staging overlay and a promotion workflow with an automatic canary-to-staging step.
- Use Cloud Deploy instead of Argo CD for the delivery pipeline (it has canary support and native GKE integration) and compare.
- Run `tofu plan` nightly and open an issue when it finds drift.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Pods rejected: `violates PodSecurity "restricted"` | A container is missing `runAsNonRoot`, `seccompProfile`, `allowPrivilegeEscalation: false` or `capabilities.drop: [ALL]`. |
| Pod can't reach Google APIs | Check the `allow-google-apis` policy and that the KSA annotation names an existing GSA with `roles/iam.workloadIdentityUser`. |
| `google-github-actions/auth` fails | The attribute condition must match `OWNER/REPO` exactly, and the job needs `permissions: id-token: write`. |
| Every image rejected after enabling Binary Authorization | CI attestations aren't being created yet; keep `enable_binary_authorization=false` until they are. |
| Canary analysis fails immediately | The eval job needs `agent-gateway-keys` (including `OPENAI_API_KEY` for answer extraction) and network access to `litellm`. |
| `tofu destroy` blocked | Dev sets `deletion_protection=false` on the cluster; the BigQuery table keeps protection on. Delete it deliberately first. |

## Teardown

```bash
cd infra/tofu/envs/dev && tofu destroy -var project_id=$PROJECT
```

A running Autopilot cluster with these workloads costs a few dollars a day. Destroy it whenever you stop for more than a day; Lab 9.2 proved you can rebuild it from scratch.
