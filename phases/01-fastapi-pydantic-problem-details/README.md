# Phase 1 — Typed APIs with Pydantic, FastAPI and RFC 9457 errors

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 1–3 (≈ 25 h) | $0 (runs locally) | Nothing | `cost-api`: a typed HTTP API over FOCUS cost data |

## Why this phase matters

Every later layer of CostPilot talks to something through a contract: agents call MCP tools, MCP tools call this API, Java calls this API, and LLMs return JSON you must validate. If the contracts are loose, every layer above inherits the looseness. This phase teaches you to make contracts explicit: typed models on the way in, typed models on the way out, and errors that are just as structured as successes.

## You will learn

- Pydantic v2: field types, aliases, `Decimal` for money, field and model validators, JSON Schema export
- Configuration with `pydantic-settings` (environment variables, no secrets in code)
- FastAPI: path and query validation, dependency injection, lifespan, generated OpenAPI
- RFC 9457 Problem Details (which replaced RFC 7807) as the single error format
- Testing an API with `pytest` and FastAPI's `TestClient`
- Why an interface (`CostRepository`) matters more than its first implementation

## Before you start

1. Finish [SETUP.md](../../SETUP.md) (Python 3.11+, `uv` or `pip`).
2. Generate the sample data once from the repo root: `python data/generate_sample.py`.
3. Read, in this order (about 2 hours):
   - Pydantic: [Models](https://docs.pydantic.dev/latest/concepts/models/), [Validators](https://docs.pydantic.dev/latest/concepts/validators/), [Aliases](https://docs.pydantic.dev/latest/concepts/alias/)
   - FastAPI: [Tutorial up to "Dependencies"](https://fastapi.tiangolo.com/tutorial/), [Handling errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)
   - [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457), sections 3 and 4 only

## How this folder works

```
starter/cost-api/    ← you work here: the structure is done, lab parts are TODOs
solution/cost-api/   ← the reference answer; peek only after trying
```

Both folders share the same tests. Your starter is finished when `pytest` passes.

```bash
cd phases/01-fastapi-pydantic-problem-details/starter/cost-api
uv venv && source .venv/bin/activate        # or: python -m venv .venv
uv pip install -e ".[dev]"                   # or: pip install -e ".[dev]"
pytest -q                                    # most tests fail at first; that's the point
```

## Concepts in five minutes

**Aliases separate the wire format from your code.** FOCUS columns are PascalCase (`EffectiveCost`). Python is snake_case. A `validation_alias` lets the model accept `EffectiveCost` from a CSV or BigQuery row while your code and your API use `effective_cost`.

**Money is `Decimal`.** `0.1 + 0.2 != 0.3` with floats. Pydantic serializes `Decimal` as a JSON string, which is what you want for money: no client silently rounds it.

**Problem Details** is a tiny standard JSON shape for errors:

```json
{
  "type": "https://example.com/problems/team-not-found",
  "title": "Unknown team",
  "status": 404,
  "detail": "No cost data exists for team 'marketing'. Call GET /v1/teams for valid ids.",
  "instance": "/v1/teams/marketing/summary"
}
```

`type` is a stable identifier clients can branch on; `detail` is for humans. You can add your own members (`invalid_params`, `trace_id`).

**Dependency injection** means endpoints ask for what they need (`repo: CostRepository = Depends(...)`) instead of building it. Tests swap in a fake; Phase 2 swaps in BigQuery.

## Labs

### Lab 1.1 — Model a FOCUS cost record

Open `starter/cost-api/src/cost_api/models.py`. `CostRecord` already declares its fields with FOCUS aliases. Add the three validators marked `TODO Lab 1.1`:

1. Empty strings become `None` (CSV exports use `""` for missing values).
2. `tags` accepts a JSON string and parses it into a dict.
3. A model validator rejects a charge period whose end is not after its start.

Then experiment in a Python shell:

```python
from cost_api.models import CostRecord
import csv
rows = list(csv.DictReader(open("../../../../data/sample/focus_costs.csv")))
r = CostRecord.model_validate(rows[0]); print(r.model_dump())
CostRecord.model_validate(rows[0] | {"BillingCurrency": "usd"})   # read the error
print(CostRecord.model_json_schema(mode="serialization"))          # what an LLM tool will see later
```

**Check:** `pytest tests/test_models.py -q` passes.

> Notice that validation errors name the field the way the caller sent it (`BillingCurrency`), not your Python name. That is what you want when the caller is a data pipeline.

### Lab 1.2 — Configuration with `pydantic-settings`

Read `settings.py` (already complete). Every value comes from an environment variable with the prefix `COST_API_`, or from a `.env` file. Try it:

```bash
COST_API_PROBLEM_BASE_URL=https://errors.mycompany.dev pytest -q tests/test_api.py -k unknown_team
```

**Exercise:** add a setting `max_page_size: int = 1000` and use it as the `le=` bound of the `limit` query parameter. Ask yourself why the bound belongs in configuration rather than in code (or why it doesn't); you will write that down in your ADR.

### Lab 1.3 — Endpoints and the repository interface

`repository.py` defines `CostRepository`, a `Protocol`. Endpoints only ever see this protocol. `InMemoryCostRepository` implements it over the sample CSV.

1. Implement `team_summary`, `top_resources` and `daily_costs` in `InMemoryCostRepository` (the TODOs explain each).
2. In `main.py`, add the three endpoints listed in `TODO Lab 1.3 (d)`. Copy the pattern of `team_costs`: typed `Annotated` parameters, `KnownTeam` to reject unknown teams, a `response_model`.
3. Run the server and explore the generated docs:

```bash
uvicorn cost_api.main:app --reload --app-dir src
# open http://127.0.0.1:8000/docs
curl -s "localhost:8000/v1/teams/payments/summary?month=2026-09" | python -m json.tool
```

Look at the payments summary: `total_billed_cost` is higher than `total_effective_cost`. The team bought a commitment (billed up front) but used only about 88% of it. You just found your first FinOps insight; keep it in mind for Phase 2.

**Check:** the summary, resources and daily tests in `tests/test_api.py` pass.

### Lab 1.4 — Every error is Problem Details

Open `problems.py`. `ProblemError` and its handler are done. Add the three handlers marked `TODO Lab 1.4`:

1. **Validation errors** (bad `month`, `limit` too high) → 422 `invalid-request` with an `invalid_params` list.
2. **Framework HTTP errors** (unknown route, wrong method) → 404 `not-found` / 405 `method-not-allowed`.
3. **Anything unexpected** → 500 `internal-error` with a `trace_id`, and nothing from the exception in the body.

Then write `errors.md` next to `pyproject.toml`: one row per `type` with its status, meaning, extension members and whether a client should retry. Compare with [the reference catalog](solution/cost-api/errors.md) only after writing yours.

**Check:**

```bash
curl -si "localhost:8000/v1/teams/payments/summary?month=2026-13" | head -20
# HTTP/1.1 422 ... content-type: application/problem+json ... "invalid_params":[{"name":"month",...
```

### Lab 1.5 — Tests as the contract

Read `tests/test_api.py` end to end; it is the specification of this phase. Then add three tests of your own:

1. `GET /v1/teams/payments/costs` with `limit=0` returns a 422 problem.
2. The `daily` endpoint returns exactly `days` items, zero-filled where there is no data.
3. A `405` problem for `POST /v1/teams`.

**Check:** `pytest -q` is fully green.

## Done when

- [ ] `pytest -q` passes in `starter/cost-api` with your code
- [ ] `GET /v1/teams/{id}/summary` returns validated data, and every bad request returns `application/problem+json`
- [ ] `/docs` shows every endpoint with its parameters and response models
- [ ] `errors.md` documents every `type` your API can return

## Write it down (ADR)

Copy [the ADR template](../../docs/adr-template.md) to `docs/adr/0001-error-format.md` in your own repo. Decide and justify: Problem Details vs a custom error envelope; snake_case output vs FOCUS names in the API. Keep it to one page.

## Teach it (5 minutes)

Show a colleague a request that fails three different ways (unknown team, bad month, unknown route) and how each response has the same shape. Ask them how their current services report errors. You will reuse this conversation in Phase 10.

## Stretch goals

- Add an `ETag` header to `summary` responses and honor `If-None-Match`.
- Add `X-Request-Id` middleware and copy it into `trace_id` in error bodies.
- Use [Schemathesis](https://schemathesis.readthedocs.io/) to fuzz the OpenAPI spec and see which edge cases you missed.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `FileNotFoundError: Sample data not found` | Run `python data/generate_sample.py` from the repo root, or set `COST_API_SAMPLE_CSV` to the CSV path. |
| Almost every API test errors with a `ValidationError` on startup | Lab 1.1 isn't done yet: the CSV has empty strings that only your validator can turn into `None`. |
| 500 errors in tests show a stack trace instead of a problem | Create `TestClient(app, raise_server_exceptions=False)`; by default it re-raises server errors. |
| Decimals look like strings in JSON | That is intentional: Pydantic serializes `Decimal` as a string to avoid float rounding. |

## Teardown

Nothing to tear down: this phase runs entirely on your machine.
