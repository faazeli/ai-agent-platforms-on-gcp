# Constraints register (Lab 8.2)

One row per constraint that could break CostPilot. Look up **your** value, don't copy a number from a blog: limits differ by project, region and model, and change over time.

| # | Constraint | Where to look it up | Your value (date) | What breaks when hit | Mitigation |
| --- | --- | --- | --- | --- | --- |
| 1 | Vertex AI requests/min per model per region | Console → IAM & Admin → Quotas, filter "Vertex AI API"; or `gcloud beta quotas info list --service=aiplatform.googleapis.com` | | 429s; agents fail mid-run | Gateway retries + fallback; request a quota increase; Provisioned Throughput |
| 2 | Vertex AI tokens/min per model per region | same | | 429s on long prompts | Context caching; shorter tool outputs; batch for reports |
| 3 | Model availability in your region (and `global`) | Vertex AI model versions page | | 404 model not found | Use `global`; pick a model available where your data may go |
| 4 | Model retirement dates | Vertex AI model versions page | | Calls fail after retirement | Aliases in the gateway; a calendar reminder; eval before switching |
| 5 | GKE Autopilot pod resource minimums/maximums and restrictions (no privileged pods, limited node access) | GKE Autopilot "resource requests" and "security capabilities" docs | | Pods rejected at admission | Right-size requests; avoid privileged sidecars |
| 6 | Cloud Run request timeout and max concurrency | Cloud Run quotas and limits page | | Long agent runs cut off | Async jobs; stream; or run agents on GKE |
| 7 | BigQuery on-demand concurrency / slot availability | BigQuery quotas page; INFORMATION_SCHEMA.JOBS | | Queries queue at peak | Materialized views; reservations; cache |
| 8 | `maximum_bytes_billed` you set (Phase 2) | cost-api settings | | A query fails instead of scanning | Narrow queries; raise deliberately |
| 9 | Org policy: service-account key creation disabled | `gcloud org-policies describe iam.disableServiceAccountKeyCreation --project=$PROJECT` | | Anything that needs a key file | Workload Identity everywhere (Phase 6) |
| 10 | Org policy: allowed resource locations | `gcloud org-policies describe gcp.resourceLocations --project=$PROJECT` | | Resource creation fails in a region | Choose regions inside the policy |
| 11 | VPC Service Controls perimeter around BigQuery and Vertex AI | Access Context Manager | | Calls from outside the perimeter denied | Put runtimes inside; use ingress rules deliberately |
| 12 | Data residency (where prompts and cost data may be processed) | Your legal/compliance team; Vertex AI data residency docs | | Non-compliant processing | Regional endpoints instead of `global` |
| 13 | LiteLLM virtual key budgets (Phase 4) | Gateway `/key/info` | | Agent stops with budget error | Budgets sized from the workload model |
| 14 | Model Armor quotas and latency (Phase 6) | Model Armor quotas page | | Guardrail adds latency or rejects at peak | Fail-closed policy; screen only what needs it |
