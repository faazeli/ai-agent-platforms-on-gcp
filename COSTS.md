# What this course costs, and how to keep it near zero

Prices change; the figures below are rough guides from when the course was written (October 2026). Your budget alert (SETUP.md) is the real safety net.

| Phase | What bills | Typical spend | Keep it low by |
| --- | --- | --- | --- |
| 1 | nothing (local) | $0 | |
| 2 | BigQuery storage and queries | ≈ $0, within the free tier | Always filter on the partition column; keep `maximum_bytes_billed` |
| 3 | nothing (local) | $0 | |
| 4 | Vertex AI model calls; optional Model Garden endpoint, RAG corpus, batch | $5–20 | Low virtual-key budgets; small eval runs; **undeploy endpoints and delete corpora right after** |
| 5 | model calls; Agent Engine while deployed | $5–15 | Short drills; **delete the Agent Engine deployment** after measuring. Lab 5.9 (optional) makes 18 TypeSafe AI calls per eval run on your own account: check its pricing first |
| 6 | Model Armor calls; a small bucket | $1–5 | Short retention on the lab audit bucket (locking is permanent) |
| 7 | a few model calls | ≈ $1 | |
| 8 | load tests (model calls) | $5–20 | 10-minute runs with few simulated users |
| 9 | GKE Autopilot pods, load balancer, Artifact Registry | ≈ $3–6 per day while running | **`tofu destroy` whenever you stop for more than a day**. Track B adds a Harness account (check the current free-plan limits) and a delegate pod; uninstall the delegate with the cluster |
| 10 | nothing | $0 | |

## Things that keep billing after you stop

- Model Garden endpoints (per hour while deployed)
- Agent Engine deployments
- RAG Engine corpora
- A running GKE cluster
- Provisioned Throughput, if you buy any (don't, for the course)

Check once a week: Billing → Reports, grouped by service, for the course project.

## End-of-course teardown

```bash
cd phases/09-devops-and-delivery/infra/tofu/envs/dev && tofu destroy -var project_id=$PROJECT
bq rm -r -f -d $PROJECT:finops
# then delete any remaining endpoints, engines, corpora and buckets, or shut the whole project down:
gcloud projects delete $PROJECT
```
