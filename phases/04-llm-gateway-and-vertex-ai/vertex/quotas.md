# Finding Vertex AI quotas and limits (Lab 4.5, step 2)

Quotas are per project, per region, per model, and they change. Always read your own values.

**Console:** IAM & Admin → Quotas & System Limits → filter by service "Vertex AI API" and the model name. Note the metric (requests per minute, tokens per minute), the region, and the current usage.

**CLI (Cloud Quotas API):**

```bash
gcloud services enable cloudquotas.googleapis.com
gcloud beta quotas info list --service=aiplatform.googleapis.com --project=$PROJECT \
  --format="table(quotaId, dimensions, quotaDisplayName)" | grep -i -E "generate|token|gemini" | head -40
```

**What to record for Phase 8:** requests per minute and tokens per minute for each model alias in each region you use, and whether your traffic can use the `global` location.

**Remember:** a quota is a ceiling, not a reservation. Shared pay-as-you-go capacity can still return 429 below your quota at busy times. Provisioned Throughput reserves capacity for a fixed fee.
