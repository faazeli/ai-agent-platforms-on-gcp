# Phase 4 — Vertex AI, a LiteLLM gateway, prompts and structured output

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 9–11 (≈ 30 h) | ≈ $5–20 in model calls if you keep budgets low | Phases 1–3 | A model gateway with per-agent budgets; versioned prompts; an eval harness; Vertex AI field notes |

## Why this phase matters

In CostPilot, every model call goes through one gateway that routes, retries, budgets and logs it, and every model output is parsed into a validated object or rejected. Two things follow. You can swap models without touching agents, and you can see and cap what AI costs, per agent, in the same FOCUS format as the rest of your bill. The other half of this phase is learning Vertex AI beyond "call a model": quotas, caching, grounding, batch, evaluation. Those determine what your platform can do and what it costs.

## You will learn

- Calling Gemini on Vertex AI with Application Default Credentials and a response schema
- Running the LiteLLM proxy as a gateway: role aliases, fallbacks, retries, virtual keys, budgets, spend logs
- Prompt engineering as code: structured prompts, versioned files, changelogs
- Building an eval set from ground truth and comparing prompt versions with numbers
- Parsing LLM output safely: schema-constrained output, validation, a bounded repair loop, Problem Details on failure
- The wider Vertex AI platform: Model Garden, quotas versus Provisioned Throughput, context caching, RAG Engine, the evaluation service, batch prediction

## Before you start

1. Phases 1–3 done, Docker installed, a GCP project with billing.
2. Enable the API and log in:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud auth application-default login
   ```
3. **Set a budget alert** if you haven't (see [SETUP.md](../../SETUP.md)). Model calls are the first real spend in this course.
4. Read (about 2 hours):
   - [Vertex AI Gemini quickstart](https://cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart) and [model versions](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)
   - [Structured output on Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output)
   - LiteLLM proxy: [quick start](https://docs.litellm.ai/docs/proxy/quick_start), [virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys), [fallbacks](https://docs.litellm.ai/docs/proxy/reliability)

> **Model ids change often.** This folder was written in October 2026 with `gemini-3.5-flash` (GA) behind the `fast` alias and `gemini-3.1-pro-preview` behind `smart`. Check the model versions page and edit `gateway/config.yaml`; nothing else in the course hardcodes a model id.

## What's in this folder

```
gateway/config.yaml               LiteLLM config: aliases fast/smart, fallbacks, retries
gateway/docker-compose.yml        LiteLLM + Postgres locally
gateway/scripts/create_virtual_keys.sh   one budgeted key per agent
vertex/hello_vertex.py            Lab 4.1: direct Vertex AI call with a response schema
vertex/context_cache.py           Lab 4.5: caching a large prompt prefix
vertex/batch_summaries.py         Lab 4.5: batch prediction for monthly reports
vertex/rag_search_docs.py         Lab 4.5: RAG Engine over your docs
vertex/load_test_gateway.py       Lab 4.5: hit quotas, watch fallbacks
vertex/quotas.md, field-notes-template.md
starter/llm-toolkit, solution/llm-toolkit
   costpilot_llm/structured.py    ask_structured: parse → validate → repair → fail
   costpilot_llm/prompts.py       versioned prompt files
   costpilot_llm/prompts/         cost_analyst.v1.md (v2 is yours to write)
   costpilot_llm/evals/           ground truth, eval set builder, scorer, runner
   costpilot_llm/spend_to_focus.py   gateway spend → FOCUS rows
   evals/evalset.jsonl            25 cases with expected answers
```

```bash
cd phases/04-llm-gateway-and-vertex-ai/starter/llm-toolkit
pip install -e ".[dev,vertex]"
pytest -q
```

## Labs

### Lab 4.1 — Call Gemini on Vertex AI directly

Run the `vertex/` scripts from this phase's folder (`phases/04-llm-gateway-and-vertex-ai`); run the `costpilot_llm` commands from `starter/llm-toolkit`.

```bash
PROJECT=$PROJECT LOCATION=global MODEL=gemini-3.5-flash python vertex/hello_vertex.py
```

The script asks for a `CostInsight` object using a Pydantic model as `response_schema`, validates the response anyway, and prints latency and token counts. Run it three times and note the variance. Then change `temperature` to 1.0 and compare. Start your field notes (`vertex/field-notes-template.md`) with these numbers.

### Lab 4.2 — Stand up the gateway

```bash
cd gateway
cp .env.example .env              # set VERTEX_PROJECT and a long random LITELLM_MASTER_KEY
docker compose up -d
curl -s localhost:4000/health/liveliness
set -a; source .env; set +a
./scripts/create_virtual_keys.sh  # prints one export line per agent key
```

Agents ask for an alias (`fast`, `smart`), never a vendor model id. Each agent gets its own virtual key with a budget, so one runaway agent cannot spend another's money. Try it:

```bash
curl -s localhost:4000/v1/chat/completions -H "Authorization: Bearer $COST_ANALYST_VKEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "fast", "messages": [{"role": "user", "content": "Say hi in 3 words"}]}'
curl -s localhost:4000/v1/chat/completions -H "Authorization: Bearer $ANOMALY_DETECTOR_VKEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "smart", "messages": [{"role": "user", "content": "hi"}]}'   # rejected: key isn't allowed "smart"
```

**FinOps for your own AI:** after a few calls, export spend logs and convert them to FOCUS rows:

```bash
curl -s "localhost:4000/spend/logs" -H "Authorization: Bearer $LITELLM_MASTER_KEY" > spend.json
python -m costpilot_llm.spend_to_focus spend.json --out ai_spend_focus.csv
```

Load the CSV with Phase 2's staging + `MERGE` and query AI spend per agent with the same SQL you use for the cloud bill. Look at one row of `spend.json` first: field names vary slightly between LiteLLM versions.

### Lab 4.3 — Prompt engineering as code

Prompts live in `costpilot_llm/prompts/<name>.v<N>.md` with a header (version, owner, changelog). `cost_analyst.v1.md` is deliberately terse. Write `cost_analyst.v2.md` with a fixed structure: role, context (explaining `EffectiveCost` vs `BilledCost`), task, constraints, output rules, and two worked examples. Remember that literal braces in examples must be doubled (`{{` and `}}`).

Implement `is_correct` in `evals/scorer.py` (`TODO Lab 4.3`), then look at the eval set: 25 cases whose expected answers are computed from the sample CSV with exact decimals, never by a model.

```bash
export OPENAI_API_KEY=$EVAL_RUNNER_VKEY        # the runner talks to the gateway
python -m costpilot_llm.evals.run_eval --prompt-version 1 --model fast --runs 3
python -m costpilot_llm.evals.run_eval --prompt-version 2 --model fast --runs 3
```

Compare accuracy, accuracy by tag, parse failures and repairs. The rule from now on: no prompt change without an eval run attached to the pull request.

### Lab 4.4 — Parse, validate, repair, or fail

Implement `ask_structured` in `structured.py` (`TODO Lab 4.4`):

1. Ask for JSON with `response_format` built from the Pydantic schema (the gateway translates it for Vertex AI).
2. Strip Markdown fences locally (a free repair).
3. Validate with `model_validate_json`. On failure, send the validation errors back and ask for a corrected answer, at most `max_repairs` times.
4. If it still fails, raise `StructuredOutputError`, whose `.problem` is an RFC 9457 body (status 502).

Never `eval` model output, and never return unvalidated data "just this once".

**Check:** `pytest -q` passes. Then measure: run the eval 3 times with `response_format` and 3 times with it removed (edit a copy of the runner), and record parse failures and repairs in an ADR.

Structured output guarantees the *shape* of an answer, not whether its numbers are trustworthy. When the output is a decision (pick a category, yes or no) with a confidence attached, accuracy isn't enough: you also need to know whether the confidence means anything. Phase 5's Lab 5.9 compares this repair loop with a model that returns real probabilities, and measures calibration for both.

### Lab 4.5 — The wider Vertex AI platform

Six short exercises. Record everything in `vertex/field-notes-template.md`; Phase 8 sizes the platform from it.

1. **Model Garden.** Run 10 eval questions on Gemini Flash and on an open model (for example Gemma) deployed from Model Garden to a Vertex endpoint. Endpoints bill per hour while deployed: undeploy right after.
2. **Quotas and throughput.** Find your per-model, per-region quotas ([vertex/quotas.md](vertex/quotas.md)). Then `python vertex/load_test_gateway.py --model smart --requests 100 --concurrency 30` and look for 429s, retries and the `smart` → `fast` fallback. Read about Provisioned Throughput and note the traffic level at which it beats pay-as-you-go.
3. **Context caching.** `python vertex/context_cache.py` caches the long system context and compares token counts with and without the cache.
4. **Grounding.** `python vertex/rag_search_docs.py "Why did we partition by day?"` indexes your ADRs with RAG Engine. Then add a `search_docs(question)` tool to Phase 3's MCP server that calls `rag.retrieval_query` and returns the top 3 passages with their sources. Delete the corpus when finished.
5. **Evaluation service.** Run 10 eval cases through the Gen AI evaluation service and compare its judgments with your scorer. Where they disagree, decide who is right.
6. **Batch prediction.** `BUCKET=gs://... python vertex/batch_summaries.py` generates every team's monthly summary as one batch job. Compare cost and wall time against live calls.

## Done when

- [ ] No code outside `gateway/` names a vendor model id; agents use `fast` / `smart`
- [ ] Each agent has its own budgeted virtual key, and you have queried AI spend as FOCUS rows
- [ ] `cost_analyst.v2.md` exists with a changelog, and you have eval numbers for v1 versus v2
- [ ] Every LLM output in your code goes through `ask_structured` (or an equivalent validator)
- [ ] `pytest -q` passes in your starter
- [ ] Your Vertex AI field notes record quotas, caching savings, batch costs and the open-model comparison

## Write it down (ADR)

`docs/adr/0004-model-gateway.md`: why a gateway; alias names; fallback order; budget per agent and how you chose it; schema-constrained output plus repair versus free text, with your measured parse-failure rates.

## Teach it (5 minutes)

Show v1 versus v2 eval results side by side. Ask your audience how they currently decide a prompt change is safe to ship.

## Stretch goals

- Add a third alias, `cheap`, routed to the smallest model, and route the anomaly detector's summaries to it. Measure the accuracy you lose against the money you save.
- Add LiteLLM's caching for identical requests and measure the hit rate on your eval runs.
- Add an "LLM-as-judge" scorer for the `explanation` field and check its agreement with your own judgment on 20 cases.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `404 ... model ... not found` from Vertex AI | The model id is retired or not available in that location. Check model versions and try `VERTEX_LOCATION=global`. |
| `PermissionDenied: aiplatform.endpoints.predict` | Grant yourself `roles/aiplatform.user`; locally the gateway uses your ADC file. |
| Gateway returns `401` | Use a virtual key (or the master key for admin calls) as `Authorization: Bearer ...`. |
| Gateway can't start: database errors | `docker compose logs db`; wait for Postgres to be healthy, then `docker compose restart litellm`. |
| Every eval answer fails on numbers | Look at one raw answer: the model may be adding currency symbols. Your scorer and prompt rules must agree. |
| Context cache creation fails on size | Caches have a minimum token count; the script already includes all months of data to pass it. |

## Teardown

```bash
cd gateway && docker compose down          # add -v to also delete the key database
```

Undeploy any Model Garden endpoints and delete any RAG corpora. Both bill while they exist.
