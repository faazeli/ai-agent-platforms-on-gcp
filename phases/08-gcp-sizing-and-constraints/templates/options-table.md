# CostPilot resource options (Lab 8.1)

Fill in the last two columns for *your* design. "Decide by" lists the questions that usually settle it; the evidence column should point at a number (load test, quota, price) or a constraint (security, team skills).

| Component | GCP options | Decide by | Your choice | Evidence |
| --- | --- | --- | --- | --- |
| Agent runtime | Vertex AI Agent Engine · Cloud Run · GKE Autopilot · GKE Standard | Ops effort vs control; long-lived streaming connections; NetworkPolicy and sidecar needs; cold start tolerance; existing platform | | |
| Model serving | Gemini pay-as-you-go · Provisioned Throughput · open model on a Vertex endpoint · open model on GKE GPUs | Steady vs spiky tokens; model choice; data residency; fine-tuning; utilization you can sustain | | |
| Gateway (LiteLLM) | Cloud Run · GKE | Needs Postgres for keys/spend; private networking to agents; scale with agents | | |
| Tool and API services | Cloud Run · GKE | Scale to zero vs always warm; mesh / NetworkPolicy; shared ingress | | |
| Analytics | BigQuery on-demand · BigQuery editions with slot reservations | Monthly bytes scanned; predictability; concurrency | | |
| Agent state & checkpoints | Agent Engine sessions · Firestore · Cloud SQL / AlloyDB (Postgres) · Memorystore | What the framework expects (LangGraph → Postgres); latency; consistency | | |
| Async and scheduled work | Pub/Sub · Cloud Tasks · Workflows · Cloud Scheduler · BigQuery scheduled queries | Fan-out; retries; schedules; exactly-once needs | | |
| Secrets | Secret Manager · Kubernetes Secrets (with Secret Manager CSI) | Rotation; audit; who can read | | |
| Ingress & identity-aware access | Cloud Load Balancing + IAP · API Gateway · internal-only | Who calls it (humans, other agents); Zero Trust requirements | | |
