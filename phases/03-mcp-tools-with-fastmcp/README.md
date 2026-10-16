# Phase 3 — MCP tools with FastMCP

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 7–8 (≈ 16 h) | $0 (local) | Phase 1 `cost-api` (Phase 2 optional) | `mcp-finops`: four read-only, typed MCP tools, a resource and a prompt |

## Why this phase matters

The Model Context Protocol (MCP) is how agents discover and call tools, regardless of which framework or model they run on. The tools you build here are used unchanged by ADK agents and LangGraph graphs in Phase 5, and by any MCP client (IDE assistants, chat apps, the MCP Inspector).

A tool is an API whose caller is a language model. Models read descriptions literally, guess at formats, retry when confused, and occasionally ask for absurd amounts of data. This phase teaches you to design tools for that caller: precise descriptions, bounded inputs, typed outputs, and errors that say what to do next.

FastMCP is on its 3.x line (3.4.x in mid-to-late 2026, per its [changelog](https://gofastmcp.com/v3/updates.md)). This folder was tested with FastMCP 3.4.8; pin the version you use.

## You will learn

- MCP's three primitives: tools, resources, prompts, and when to use each
- FastMCP servers: typed tools, structured output with output schemas, tool annotations, timeouts
- Designing tool names, descriptions and parameter schemas for a model
- Two MCP error channels, and carrying RFC 9457 Problem Details through tool errors
- Testing MCP servers in-memory, and inspecting them interactively
- Generated tools (from OpenAPI) versus hand-written tools

## Before you start

1. Phase 1 done. Your `cost-api` should be running locally on port 8000 for the manual steps.
2. Node.js 18+ (only for the MCP Inspector).
3. Read (about 2 hours):
   - [MCP introduction](https://modelcontextprotocol.io/) and the [server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts) (tools, resources, prompts)
   - FastMCP: [Quickstart](https://gofastmcp.com/getting-started/quickstart), [Tools](https://gofastmcp.com/servers/tools), [Testing](https://gofastmcp.com/patterns/testing)

## Architecture of this phase

```
MCP client (Inspector, agent) ──MCP over HTTP──▶ mcp-finops ──HTTP──▶ cost-api ──▶ CSV or BigQuery
```

The MCP server never queries BigQuery itself. It calls `cost-api`, so data-access rules live in one place, and in Phase 6 the MCP server's identity needs no BigQuery permissions at all.

```
starter/mcp-finops/   ← you work here
solution/mcp-finops/  ← reference answer
bonus/                ← Lab 3.5: tools generated from OpenAPI
tool-description-checklist.md
```

```bash
cd phases/03-mcp-tools-with-fastmcp/starter/mcp-finops
pip install -e ".[dev]"
pytest -q
```

## Concepts in five minutes

**Tools, resources, prompts.** A *tool* is something the model decides to call (`get_team_cost`). A *resource* is reference data the client application attaches (`focus://glossary`). A *prompt* is a reusable instruction template the user picks (`monthly_review`). Putting a glossary behind a tool forces the model to spend a call on it; making it a resource lets the client include it when relevant.

**Structured output.** When a tool returns a Pydantic model, FastMCP publishes an `outputSchema` and returns `structuredContent` alongside the text. Clients get typed JSON instead of parsing prose.

**Two error channels.** *Protocol errors* (JSON-RPC errors) mean the request itself was malformed. *Tool execution errors* come back as a normal result flagged `isError`, which the model sees and can react to. Raise `ToolError` for the second kind; its message is shown to the model. Everything else is masked (`mask_error_details=True`).

**Annotations** such as `readOnlyHint` tell clients what a tool does. They are hints, not enforcement; Phase 5 enforces boundaries in code.

## Labs

### Lab 3.1 — Your first tool, with structured output

In `src/mcp_finops/server.py`, `list_teams` is done. Add `get_team_cost` following its pattern (see the `TODO Lab 3.1` comment). Use the `TeamId` and `Month` annotated types already defined: they enforce formats in the input schema.

Run it against your live `cost-api`:

```bash
# terminal 1 (Phase 1 folder)
uvicorn cost_api.main:app --app-dir src --port 8000
# terminal 2
python -m mcp_finops                      # serves MCP at http://localhost:8001/mcp
# terminal 3
npx @modelcontextprotocol/inspector       # connect with transport "Streamable HTTP", URL http://localhost:8001/mcp
```

In the Inspector, open **Tools**, call `get_team_cost` with `payments` / `2026-09`, and look at both the text and the structured content. Then try `month = "September"` and see the call rejected before your code runs.

### Lab 3.2 — Write descriptions for a model, not a human

Go through [tool-description-checklist.md](tool-description-checklist.md) for each tool. Then rewrite the `get_team_cost` docstring three ways (terse, detailed, detailed with "when not to use it") and keep all three in a scratch file. In Phase 4 you will measure which version makes an agent pick the right tool most often; for now, predict the winner and write down why.

### Lab 3.3 — Errors that agents and humans both understand

Implement `tool_error` in `cost_api_client.py` (`TODO Lab 3.3`). It turns a cost-api problem document into a `ToolError` whose message is itself a problem document, minus internal fields, plus a `hint`.

```json
{"type": "https://example.com/problems/team-not-found", "title": "Unknown team", "status": 404,
 "detail": "No cost data exists for team 'marketing'.",
 "hint": "Call list_teams to get valid team ids, then retry with one of them."}
```

The `type` URIs are the same ones in Phase 1's `errors.md`. A good hint either names the next tool to call or tells the model to stop; "an error occurred" helps nobody.

**Check:** `pytest -q -k "problem or upstream"` passes.

### Lab 3.4 — Three more tools, bounded

1. Implement `find_anomalies` in `anomalies.py` (a trailing 7-day z-score: the Python twin of Phase 2's q06).
2. Add `top_resources` with `limit` bounded to 1–20.
3. Add `detect_anomalies` with `days` bounded to 7–60 and `threshold` to 2.0–6.0.

Every bound is enforced in the schema, so the server rejects bad input before your code runs. Defaults are small and cheap.

**Check:** `pytest -q` passes, including `test_finds_the_planted_anomaly_end_to_end`, which runs the real Phase 1 API in-process and must find the 2026-09-18 spike.

### Lab 3.5 — Test it two ways, then compare with generated tools

You already have in-memory tests (`tests/test_server.py` uses `Client(mcp)`, no ports). Add two of your own:

1. `get_team_cost` for a month with no data returns a `no-cost-data` problem with a hint.
2. The `monthly_review` prompt mentions every tool it asks the model to use.

Then run the bonus, which generates MCP tools straight from cost-api's OpenAPI spec:

```bash
cd phases/03-mcp-tools-with-fastmcp
PYTHONPATH=../01-fastapi-pydantic-problem-details/solution/cost-api/src python bonus/generated_from_openapi.py
```

You'll see names like `team_costs_v1_teams` and descriptions like "Team Costs". Write an ADR: when are generated tools good enough (internal prototypes, broad API coverage), and when do you hand-write them (anything a model must choose correctly)?

## Done when

- [ ] Four read-only tools with output schemas, bounded inputs and model-oriented descriptions
- [ ] Tool errors are Problem Details with hints, and nothing internal leaks
- [ ] A resource (`focus://glossary`) and a prompt (`monthly_review`) are published
- [ ] `pytest -q` passes, including the end-to-end anomaly test
- [ ] You have called every tool from the MCP Inspector against your running `cost-api`

## Write it down (ADR)

`docs/adr/0003-mcp-tool-design.md`: hand-written versus generated tools, why the MCP server calls `cost-api` instead of BigQuery, and your rule for which data becomes a tool versus a resource.

## Teach it (5 minutes)

Demo the Inspector: call a tool with a bad team id and show the hint. Ask your audience what their internal APIs return on error and whether a model could recover from it.

## Stretch goals

- Add a `compare_months(team_id, month_a, month_b)` tool and decide whether it should exist or whether the agent should call `get_team_cost` twice.
- Add FastMCP middleware that logs tool name, duration and outcome as JSON (you'll reuse it for audit logging in Phase 6).
- Expose a resource template `focus://teams/{team_id}/budget` and think about when a resource template beats a tool.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Inspector can't connect | Use transport "Streamable HTTP" and the URL ending in `/mcp`. Check that `python -m mcp_finops` is running. |
| Every tool call returns `upstream-unavailable` | `cost-api` isn't reachable. Start it, or set `MCP_FINOPS_COST_API_URL`. |
| `ToolError` details show "Error calling tool" only | Raise `ToolError` for anything the model should see; other exceptions are masked by design. |
| The end-to-end test is skipped | It needs the Phase 1 solution next to this folder (it is, in the course repo). |

## Teardown

Nothing in the cloud. Stop the local processes.
