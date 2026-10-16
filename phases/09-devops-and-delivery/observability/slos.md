# CostPilot SLOs (Lab 9.7)

Two SLOs are enough to start. Each one is a promise a user would notice breaking.

| SLO | SLI (good events / valid events) | Objective | Window |
| --- | --- | --- | --- |
| **Answer latency** | agent `/run` requests answered in < 20 s / all `/run` requests | 95% | 28 days |
| **Tool reliability** | `mcp-finops` tool calls without an upstream 5xx or timeout / all tool calls | 99.5% | 28 days |

## Error budget and burn-rate alerts

Error budget = 1 − objective. For tool reliability that is 0.5% of tool calls in 28 days.

Page on fast burn, ticket on slow burn (the multi-window approach from the Google SRE workbook):

| Alert | Burn rate | Long window | Short window | Action |
| --- | --- | --- | --- | --- |
| Fast burn | 14.4× | 1 h | 5 min | Page: 2% of the monthly budget gone in an hour |
| Slow burn | 6× | 6 h | 30 min | Ticket: 5% of the budget gone in six hours |

## Where the numbers come from

- Request latency and status: Cloud Monitoring's built-in load balancer metrics for the agents' ingress, or OpenTelemetry metrics from each service exported to Google Cloud Managed Service for Prometheus.
- Tool outcomes: the audit log (Phase 6) already records every tool call with its decision; a log-based metric counting `decision="error"` gives the bad-event count.

Create the SLOs in Cloud Monitoring (Services → Define service → Create SLO) or as code with the `google_monitoring_slo` resource once you've confirmed which metric your setup emits. Then add the AI-specific signals next to them on one dashboard:

- tokens per question and cost per question (gateway spend logs, Phase 4)
- agent eval accuracy per release (Phase 5, recorded by CI)
- guardrail block rate (Model Armor audit entries, Phase 6)
