# ADR 00NN: Runtime and capacity for CostPilot

- **Status:** proposed | accepted | superseded by ADR 00XX
- **Date:**
- **Deciders:**

## Context

What we're sizing and why now. Link the workload model (`docs/sizing/model.md`) and the constraints register.

## Workload model (summary)

| Assumption | Value | Source |
| --- | --- | --- |
| Users | | |
| Questions per user per day | | |
| Peak-hour share | | |
| Model calls per question (fast / smart) | | |
| Tokens per call (in / out) | | |

Result: peak ___ requests/min and ___ tokens/min on `fast`; ___ on `smart`; ___ /month; ___ per 1,000 questions.

## Options considered

| Option | p50 / p95 latency | Error rate at peak | Cost per 1,000 questions | Ops effort | Notes |
| --- | --- | --- | --- | --- | --- |
| Agent Engine | | | | | |
| Cloud Run | | | | | |
| GKE Autopilot | | | | | |

## Decision

We will run ___ on ___ because ___.

## Consequences

- What becomes easier:
- What becomes harder:
- Cost we accept:

## Revisit when

Name the signal: "peak tokens/min on `smart` exceeds 70% of quota for a week", "cost per 1,000 questions rises above ___", "a second team adopts CostPilot".
