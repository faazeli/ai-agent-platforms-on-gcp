# Vertex AI field notes (Lab 4.5)

Fill this in as you go. Phase 8 sizes the platform from these numbers, so record units and dates.

| Date | Project / region | Model ids checked |
| --- | --- | --- |
| | | |

## 1. Model Garden comparison (same 10 eval questions)

| Model | Accuracy (of 10) | p50 latency (s) | Input $/1M tokens | Output $/1M tokens | Notes |
| --- | --- | --- | --- | --- | --- |
| Gemini Flash | | | | | |
| Open model (e.g. Gemma) on a Vertex endpoint | | | | | endpoint $/hour while deployed |

When would self-hosting be worth it for CostPilot? (sustained volume, data residency, fine-tuning)

## 2. Quotas and throughput

| Model | Region | Quota metric | Limit | Where I found it |
| --- | --- | --- | --- | --- |
| | | requests/min | | |
| | | tokens/min | | |

- 429s observed at concurrency: ___
- Did the `smart` → `fast` fallback work? Evidence:
- Provisioned Throughput: minimum purchase, unit, monthly price, and the traffic level at which it beats pay-as-you-go:

## 3. Context caching

| | Prompt tokens | Cached tokens | Latency (s) | Cost per question |
| --- | --- | --- | --- | --- |
| Without cache | | 0 | | |
| With cache | | | | |

Break-even number of questions per cache TTL:

## 4. Grounding (RAG Engine or Vertex AI Search)

- Corpus size, chunking settings:
- 3 questions answered correctly only with retrieval:
- Monthly cost of keeping the corpus:

## 5. Evaluation service vs homemade scorer

- Cases where they disagreed, and who was right:

## 6. Batch prediction

| | Requests | Wall time | Cost |
| --- | --- | --- | --- |
| Live calls | | | |
| Batch job | | | |
