# Track B — the CostPilot pipeline in Harness

Track A (Labs 9.4–9.6) delivers CostPilot with **GitHub Actions + Argo CD + Argo Rollouts**: three tools, each doing one job, glued together by Git. Track B delivers the **same platform, through the same gates**, with **Harness**: one product that builds, deploys, verifies, approves and audits.

Do Track A first. Then build Track B and compare the two with numbers, not opinions (Lab 9.H7). The aim is not to crown a winner. It is to be the engineer who can explain what each approach costs and buys, which is what your leadership will ask.

| Time | Cost | Needs |
| --- | --- | --- |
| ≈ 10–12 h | Your dev cluster (as in Track A); a Harness account (check Harness's current free-plan limits for CI and CD) | Labs 9.1–9.6 done; the dev cluster and Artifact Registry from Lab 9.2 |

> **Verification note.** The pipeline and trigger were validated against [Harness's published JSON schema](https://github.com/harness/harness-schema); the tests below re-run that check. The kustomize layers render with kustomize 5.7.1, the policies pass `opa test`, and the scripts pass `shellcheck`. Connector, service, environment and infrastructure YAML follow Harness's [example apps](https://github.com/harness-community/harnesscd-example-apps) but have no published schema to validate against. Nothing here was executed against a live Harness account, so expect to adjust small details. Harness's UI shows the YAML of anything you create, so diffing that against these files is the fastest fix. Please open an issue when you do.

## The same pipeline, mapped

```
                   Track A (GitHub + Argo)                    Track B (Harness)
build + test       app-ci.yml jobs on GitHub runners          CI stage "build", pods in YOUR cluster (harness-builds)
identity to GCP    GitHub OIDC → Workload Identity Fed.       build pods and delegate: KSA → GSA (Workload Identity)
scan / SBOM        trivy-action, buildx SBOM                  Trivy step, CycloneDX SBOM
sign               cosign keyless (Fulcio, workflow identity) cosign with a Cloud KMS key only CI's GSA can use
attest             Binary Authorization attestation           same attestor, same KMS key, same command
deploy dev         commit digests to overlay → Argo CD sync   Deployment stage → delegate applies (push from inside)
canary             Argo Rollout 10% → 50% → 100%              K8sCanaryDeploy (1 pod) → K8sRollingDeploy
canary judged by   AnalysisRun Job: agent evals ≥ 0.8         ShellScript step: SAME Job, SAME evals, SAME bar
                                                              + optional Harness CV (metrics and logs, ML baseline)
bad canary         Rollout aborts, traffic to stable          step fails → StageRollback → canary deleted
promote to prod    promote-prod.yml + GitHub environment      Approval stage (not the person who ran it) → prod stage
                   approver + manual Argo sync
guardrails         branch protection, CODEOWNERS              OPA policies on the pipeline itself (policies/)
audit              Git history + Actions logs + Argo events   Harness audit trail + Git history (pipelines as code)
```

`tests/test_harness.py` enforces the middle of that table: the Harness eval Job must equal the Argo AnalysisTemplate's Job (image, command, threshold, identity, labels, secrets, hardening), Harness must deploy every object Argo deploys, and the eval pods must be allowed through the default-deny NetworkPolicy.

## What's in this folder

```
pipelines/costpilot.yaml   the pipeline: build → deploy_dev → approve_prod → deploy_prod
triggers/push_main.yaml    run on every push to main
services/                  costpilot_agents: Kustomize manifests + Artifact Registry artifact
environments/, infrastructure/   dev and prod, each a GKE cluster reached through its own delegate
connectors/                GitHub, two Kubernetes connectors and a GCP connector, all inheriting the delegate's identity
kustomize/dev|prod         Harness's view of Track A's overlays (+ patches/images.yaml: digests)
delegate/                  Dockerfile (adds kustomize 5), rbac.yaml (least privilege), install.sh
infra/main.tf              OpenTofu: GSAs for the delegate and build pods, the cosign KMS key
scripts/                   resolve digests, scan + SBOM, sign + attest (called by CI steps)
policies/                  OPA: prod needs approval, deploys roll back, canaries are judged
```

```bash
cd phases/09-devops-and-delivery
pip install pytest pyyaml jsonschema
pytest -q tests/test_harness.py     # uses kustomize, opa, shellcheck, hadolint when installed
```

## Design decisions worth noticing

- **The delegate runs inside your cluster and calls out.** Harness never holds a kubeconfig, cluster token or GCP key. The Kubernetes and GCP connectors say `InheritFromDelegate`. This is the same "no standing credentials" rule as Track A, reached differently: Argo CD also runs in the cluster and pulls from Git, while the delegate pulls *tasks* from Harness.
- **Deploy digests, not tags.** Binary Authorization admits images by digest. The CI stage resolves each tag to a digest once (`digests` step), scans, signs and attests *those* digests, and both deploy stages patch exactly them into the manifests (`kustomize/patches/images.yaml`). Dev and prod pull from one registry, so the attestation, which is bound to the image URL, holds in both.
- **One managed workload.** A Harness canary manages one Deployment per release. The `agents` Deployment is that workload, because agents are where behaviour changes with prompts and models. The other Deployments carry `harness.io/direct-apply: "true"` and are applied as they are, which is what Argo CD does with them in Track A.
- **Same overlays.** `kustomize/<env>` points at `../../../deploy/k8s/overlays/<env>`, so both tracks deploy the same hardened manifests. Harness bundles kustomize 3.5.4, which can't build them (`labels`, `replacements`), so the delegate image ships kustomize 5.7.1 and points `KUSTOMIZE_PATH` at it.
- **Harness expressions only in patches.** Harness resolves `<+...>` in Kustomize patch files, never in `kustomization.yaml` or base manifests. That keeps the overlays usable by plain kustomize and Argo CD.
- **The eval gate is a step, CV is a second opinion.** The eval Job checks *correctness* against known answers (only meaningful where cost-api serves the sample data: dev). Harness Continuous Verification checks *health* by comparing the canary's metrics and logs with the stable version using ML. Prod uses CV, because prod data has no expected answers. Both run with `failureStrategies: StageRollback`.
- **Signing differs, on purpose.** Track A signs keylessly with the workflow's GitHub OIDC identity, recorded in Sigstore's public log. Harness has no identity that Sigstore's Fulcio trusts, so Track B signs with a Cloud KMS key only the CI service account can use (`--tlog-upload=false` keeps private image names out of the public log). Verify with `cosign verify --key gcpkms://... --insecure-ignore-tlog`.

## Labs

### Lab 9.H1 — A Harness project from Git

1. Create a Harness account, an organization `default` (already there) and a project `costpilot`. Turn on **Git Experience** and connect your fork.
2. Create a secret `github_pat` (a fine-grained token, read-only on your fork). Then import the connectors in this order: `connectors/github.yaml` (fix the URL and username), `dockerhub.yaml`, `gcp_delegate.yaml`, `gke_delegate_dev.yaml` and `gke_delegate_prod.yaml`.
3. Import `environments/*`, `infrastructure/*`, `services/costpilot_agents.yaml` and, last, the pipeline as a **remote** pipeline stored at `phases/09-devops-and-delivery/harness/pipelines/costpilot.yaml`. From now on, editing the pipeline in the UI produces a commit, and a commit changes the pipeline.
4. Create a user group `costpilot_approvers` with at least one person who is **not** you.

### Lab 9.H2 — A delegate on GKE with Workload Identity

```bash
# The identities (once): add the module from infra/main.tf to infra/tofu/envs/dev, then
tofu apply -var project_id=$PROJECT                      # harness-delegate and harness-builder GSAs, cosign KMS key

# The delegate image: Harness → Project settings → Delegates → New delegate shows the current tag
docker build --build-arg DELEGATE_TAG=$TAG -t $REGISTRY/harness-delegate:$TAG-k5 harness/delegate
docker push $REGISTRY/harness-delegate:$TAG-k5
# Binary Authorization admits only attested images, so attest this one once by hand
# (the same gcloud command as scripts/sign_and_attest.sh).

PROJECT_ID=$PROJECT ENV=dev HARNESS_ACCOUNT_ID=... HARNESS_DELEGATE_TOKEN=... \
  DELEGATE_IMAGE=$REGISTRY/harness-delegate:$TAG-k5 harness/delegate/install.sh
```

Read `delegate/rbac.yaml` before you run it. The delegate is a namespace admin of its own namespace, and of `costpilot` and `harness-builds` through RoleBindings. It can't create namespaces, CRDs or cluster roles. Prove it: from the delegate pod, `kubectl auth can-i create clusterrolebinding` must answer `no`. Harness's default install grants cluster-admin. Ask yourself why that default exists, and why you don't want it.

### Lab 9.H3 — CI: build, scan, sign, attest

Run the pipeline with only the `build` stage selected. Watch the build pod appear in `harness-builds` (`kubectl -n harness-builds get pods -w`) and notice it runs as `harness-builder`, with no key mounted. Then confirm the outputs: `gcloud container binauthz attestations list --attestor=built-by-ci` shows three new attestations, and `cosign verify --key $COSIGN_KEY --insecure-ignore-tlog $REGISTRY/agents@$DIGEST` succeeds.

Compare the wall-clock time with Track A's `app-ci` run on the same commit, and write both numbers down for Lab 9.H7.

### Lab 9.H4 — A canary gated by agent evals

Run the whole pipeline. In dev, Harness starts one canary pod of the new agents version beside the stable ones. The `canary_evals` step then runs the Phase 5 evals from the canary image inside the cluster, through the same gateway and MCP server the agents use. At 0.8 or above, the canary is deleted and the rolling deploy proceeds. Below 0.8, the step fails, the stage rolls back, and prod is never offered for approval.

Break it on purpose, as in Lab 9.5:

1. Make the cost analyst's instruction worse (for example, tell it to round every amount to the nearest thousand), commit, and push.
2. Watch `canary_evals` print the eval log and fail, then watch the rollback steps delete the canary. `kubectl -n costpilot get deploy` shows only the stable version.
3. Revert, push, and see it pass. Then try to approve your own run: `disallowPipelineExecutor` stops you.

### Lab 9.H5 — Continuous Verification (optional)

1. Create a **monitored service** for `costpilot_agents` in `dev` with a **Google Cloud Operations** health source. Use metrics for request latency and 5xx rate (from Lab 9.7's OpenTelemetry metrics or the load balancer), and log errors from the `agents` container.
2. Set the pipeline variable `cv_enabled` to `"true"`. The Verify step now runs after the eval gate for 10 minutes. It compares the canary pod's metrics and logs with the stable pods' (sensitivity MEDIUM in dev, HIGH in prod).
3. Inject a fault that evals *don't* catch, such as a 2-second sleep in the agents' health handler, and watch CV fail the canary on latency. Evals check whether answers are right; CV checks whether the service is healthy. You want both.

Argo Rollouts can do the second half too, with a Prometheus or Cloud Monitoring AnalysisTemplate. The difference is who writes the thresholds: you (Argo) or a learned baseline (Harness CV).

### Lab 9.H6 — Governance as code

1. Install the policies: Harness → Project settings → Policies → New policy (paste `policies/costpilot_delivery.rego`), then a policy set on **Pipeline** for **On Save** and **On Run**, with severity *Error*.
2. Try to break a rule: delete the `approve_prod` stage and save. Harness refuses with "stage 'deploy_prod' deploys to prod without an earlier Approval stage". Remove `canary_evals` from dev, and it refuses again.
3. Run the policy tests locally: `opa test harness/policies -v`. Add a rule of your own, with a test, such as "prod canaries must run Verify with sensitivity HIGH".
4. Open **Account settings → Audit trail** and find who changed the pipeline, who approved the last prod deploy, and when. In Track A, you assemble the same story from Git, Actions and Argo CD.

### Lab 9.H7 — Compare, with numbers

Fill this in from your own runs, then write `0016-delivery-platform.md` recommending one approach for *your* team.

| Measure | Track A | Track B |
| --- | --- | --- |
| Commit → running in dev (median of 3 runs) | | |
| Bad prompt → canary rolled back (time) | | |
| Lines of delivery config you maintain | `wc -l ci/github-workflows/* deploy/argocd/* deploy/rollouts/*` | `wc -l harness/**/*.yaml harness/scripts/*` |
| Components you operate in-cluster | Argo CD, Argo Rollouts | Delegate (+ build pods) |
| Standing credentials outside GCP | | |
| Who can bypass the eval gate, and how | | |
| Monthly cost at your team's size | | |
| Skills a new hire needs | | |

Things to weigh that a table hides: lock-in (Harness pipelines are Harness YAML; GitHub Actions and Argo are portable but you assemble them yourself), the operational cost of running Argo, the value of one audit trail, ML-based verification versus thresholds you understand, and what your organization already pays for.

## Done when

- [ ] The dev and prod delegates run with least-privilege RBAC and Workload Identity, and no Harness connector holds a key
- [ ] One push builds, scans, signs and attests all three images, and deploys exactly those digests
- [ ] A bad prompt fails `canary_evals` and the canary rolls itself back; a good one reaches the approval stage
- [ ] Nobody can approve their own production deploy, and the OPA policies reject a pipeline without the gates
- [ ] `pytest -q tests/test_harness.py` passes, and your comparison ADR is written

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `kustomize build` fails on `labels` or `replacements` | The delegate uses its bundled kustomize 3.5.4. Check that the delegate runs your image and that `KUSTOMIZE_PATH` is set in the pod (`kubectl exec ... -- env`). |
| Build pod stuck `Pending` on Autopilot | Autopilot doesn't allow privileged pods. Use the `BuildAndPushGAR` step (it builds without privileges) rather than Docker-in-Docker, and keep resource requests modest. |
| `BuildAndPushGAR` gets 403 | The build pod isn't using `harness-builder`, or its GSA lacks `artifactregistry.writer`, or the Workload Identity binding names the wrong `namespace/ksa`. |
| Eval job forbidden | The delegate lacks the `costpilot` RoleBinding (re-run `install.sh`), or the namespace's Pod Security rejected the Job. Read `kubectl -n costpilot describe job agent-evals-<n>`. |
| Eval job runs but can't reach the gateway | It must carry `app: agent-evals`, which the NetworkPolicies allow. |
| Canary deploy says more than one managed workload | A Deployment lost its `harness.io/direct-apply` annotation. `kustomize build harness/kustomize/dev` shows which. |
| Pods rejected by Binary Authorization | The patch didn't apply, so an image tag got through instead of a digest. Check the rendered manifest in the step log for `@sha256:`. |
| Expression shows up literally, `<+...>` in a manifest | You put it in `kustomization.yaml` or a base file. Harness resolves expressions only in patch files. |

## Teardown

`helm uninstall costpilot-gke-dev -n harness-delegate-ng`, `kubectl delete -f harness/delegate/rbac.yaml` (after substituting the names), then remove the `harness` module from your OpenTofu env and apply. Track A's teardown removes the cluster itself.
