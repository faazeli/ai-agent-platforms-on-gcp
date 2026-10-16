# Phase 5 — Multi-agent systems with Google ADK and LangGraph

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 12–15 (≈ 40 h) | ≈ $5–15 in model calls; Agent Engine billed while deployed | Phases 1–4 | An ADK coordinator with three specialists; enforced execution boundaries; the monthly report in ADK and in LangGraph; agent evals; one agent on Agent Engine |

## Why this phase matters

One agent with every tool is easy to demo and hard to trust. Real platforms split work across specialists, give each the minimum tools and budget, put a human in front of anything that changes state, and assume the data they read may be hostile. This phase builds that, in two frameworks: Google ADK, and LangGraph, which many teams you'll join already use. You will learn what each is good at, and prove your boundaries hold with tests rather than prompts.

This folder was tested with **google-adk 2.12.0** and **LangGraph 1.2.15**. ADK now ships SDKs for Python, Java, Go and TypeScript, and ADK for Java reached 1.0 on March 30, 2026 with native Agent2Agent (A2A) support ([write-up](https://interviewkickstart.com/blogs/articles/google-adk-java-1-what-engineers-need-to-know-about-building-ai-agents)); you'll use the Java SDK in Phase 7. ADK 2.x deprecates `SequentialAgent` and `ParallelAgent` in favour of graph-based `Workflow`s, which is what this phase uses for fixed pipelines.

## You will learn

- ADK agents: `LlmAgent`, tools from MCP (`McpToolset` with a `tool_filter`), models through LiteLLM
- Multi-agent patterns: a routing coordinator with `sub_agents`, versus a fixed `Workflow` graph
- Execution boundaries enforced in code: tool allow-lists, approval gates for writes, per-agent model-call budgets, audit hooks
- Treating tool output as untrusted data, and regression-testing prompt injection
- Evaluating agents on both the answer and the path (tool trajectory)
- LangChain building blocks and a LangGraph state machine with checkpoints and human-in-the-loop interrupts
- Deploying to Vertex AI Agent Engine, and comparing it with self-hosting
- Typed decisions with calibrated probabilities (TypeSafe AI's Jev): act when sure, defer when not, and measure calibration

## Before you start

1. Phases 1–4 running locally: `cost-api` (:8000), `mcp-finops` (:8001), the gateway (:4000) with virtual keys from `create_virtual_keys.sh` (it creates `COORDINATOR_VKEY`, `COST_ANALYST_VKEY`, `ANOMALY_DETECTOR_VKEY`, `RECOMMENDER_VKEY` and `EVAL_RUNNER_VKEY`).
2. Read (about 2 hours):
   - ADK: [overview](https://adk.dev/), [LLM agents](https://adk.dev/agents/llm-agents/), [multi-agent systems](https://adk.dev/workflows/), [callbacks](https://adk.dev/callbacks/), [MCP tools](https://adk.dev/tools-custom/mcp-tools/)
   - LangGraph: [overview](https://docs.langchain.com/oss/python/langgraph/overview), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

```bash
cd phases/05-multi-agent-adk-and-langgraph/starter/agents
pip install -e ../../../04-llm-gateway-and-vertex-ai/solution/llm-toolkit   # Phase 4 toolkit
pip install -e ".[dev,postgres,jev]"     # jev: Lab 5.9's SDK (typesafe-sdk)
pytest -q
```

## What's in this folder

```
starter/agents, solution/agents
  src/costpilot_agents/
    policy.py                 allow-lists, approval gates, model-call budgets (Lab 5.3)
    tickets.py                the one write action: a stand-in ticketing system
    instructions/*.md         each agent's instruction, versioned like prompts
    adk/team.py               coordinator + specialists; the monthly report Workflow (Lab 5.2)
    adk/live.py               gateway models + MCP tools for production
    evals.py                  answer + trajectory evals (Lab 5.5)
    langgraph_report/graph.py the report as a LangGraph state machine (Lab 5.7)
    langgraph_report/live.py  LangChain wiring: gateway chat model, MCP tools (Lab 5.6)
    langgraph_report/run.py   CLI with Postgres checkpoints and approval
    typed_decisions/          anomaly triage with calibrated probabilities: mock, Jev and LLM deciders,
                              a confidence policy, a LangGraph approval flow, calibration metrics (Lab 5.9)
  evals/triage_evalset.jsonl  18 labeled anomaly cases for Lab 5.9
  adk_apps/                   `adk web` apps: costpilot, monthly_report
  drills/injection_drill.py   live prompt-injection drill (Lab 5.4)
  agent_engine/deploy.py      deploy / query / delete on Agent Engine (Lab 5.8)
  tests/                      offline tests: a scripted model drives real ADK and LangGraph runs
```

The offline tests are worth reading on their own. `tests/scripted.py` is a fake model that replays a script of tool calls and answers, so ADK runs its real agent loop (delegation, callbacks, tools, state) with no network. That is how you test agent *systems* deterministically.

## Architecture

```
user ─► coordinator ─┬─► cost_analyst      get_team_cost · top_resources · list_teams
         (routes,     ├─► anomaly_detector  detect_anomalies · top_resources · list_teams
          no tools)   └─► recommender       get_team_cost · top_resources · create_savings_ticket (approval)
                                     │
                         each agent: own gateway key + budget, tool guard, model-call cap
                                     ▼
                 LiteLLM gateway (:4000)          mcp-finops (:8001) ─► cost-api (:8000)
```

## Labs

### Lab 5.1 — One agent, one MCP server

Before composing a team, run a single agent and learn to read its trace. Save this as `scratch_agent/agent.py` (with an empty `__init__.py` that does `from . import agent`):

```python
import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

root_agent = LlmAgent(
    name="solo_analyst",
    model=LiteLlm(model="openai/fast", api_base="http://localhost:4000", api_key=os.environ["COST_ANALYST_VKEY"]),
    instruction="Answer cloud cost questions using your tools. Costs are FOCUS EffectiveCost.",
    tools=[McpToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8001/mcp"),
                      tool_filter=["get_team_cost", "list_teams"])],
)
```

Run `adk web` in the parent folder, ask "How much did payments spend in September 2026?", and open the **Events** tab. Find the model's function call, the tool's response, and the final answer. Then ask "How much did Payments Team spend?" and watch it call `list_teams` first. This trace is your main debugging tool for the rest of the course.

### Lab 5.2 — Compose a team, and a workflow

Implement `build_team` and `build_monthly_report` in `adk/team.py` (`TODO Lab 5.2`).

- **The team** routes with a model: the coordinator reads each specialist's `description` and transfers to one. It has no tools of its own.
- **The monthly report** is a fixed `Workflow`: two gatherers run in parallel, a `JoinNode` waits for both, the writer reads their outputs from session state (`{costs}`, `{anomalies}` in its instruction).

```bash
pytest -q tests/test_adk_team.py
cd adk_apps && adk web          # try both apps
```

Write an ADR on *routing versus workflows*: when should a model decide the next step, and when should code? Use the cost of each (count model calls in the trace) as evidence.

### Lab 5.3 — Execution boundaries

Implement the two callbacks in `policy.py` (`TODO Lab 5.3`). Together with the gateway and MCP, they give you five boundaries; write each down as a one-line policy in your ADR and point to the code that enforces it:

1. **Tool allow-list per agent.** `tool_filter` hides other tools; the `before_tool_callback` guard refuses them anyway.
2. **Read-only by default.** `create_savings_ticket` needs a human approval of its *exact arguments*, recorded in session state. Approving one ticket doesn't approve another.
3. **Model-call budget per agent per run**, plus a dollar budget on each agent's gateway key (Phase 4).
4. **Timeouts and row caps** on every tool (Phase 3's `timeout=` and bounded `limit`).
5. **Untrusted data stays data.** Instructions tell agents to ignore instructions found in tool results, and the guard makes obedience harmless anyway.

Every guard decision goes to an `audit` callback. In Phase 6 that becomes an immutable audit log.

**Check:** `pytest -q tests/test_adk_team.py` passes, including the budget and approval tests.

### Lab 5.4 — Attack your own system

`test_write_tool_needs_approval_injection_regression` is a regression test: a "compromised" scripted model obeys a hostile resource tag and tries to create a ticket. The guard stops it. Keep that test forever.

Then run the live drill with real models:

```bash
python drills/injection_drill.py 0      # payload 0
python drills/injection_drill.py 1      # payload 1
```

Run each 5 times. **Pass** means no ticket, every time. Note separately whether the answer *warned* about the suspicious data; that is a quality signal, not the security boundary. Write your own third payload and add it to `PAYLOADS`.

### Lab 5.5 — Evaluate the team

Agents can reach the right answer by luck or the wrong answer by a sensible path, so `evals.py` scores both. It reuses Phase 4's eval set, runs each question through the coordinator with tools, records the tool trajectory, extracts a typed `Answer` from the final text with `ask_structured`, and scores it with Phase 4's scorer.

```bash
export OPENAI_API_KEY=$EVAL_RUNNER_VKEY
python -m costpilot_agents.evals \
  --evalset ../../../04-llm-gateway-and-vertex-ai/solution/llm-toolkit/evals/evalset.jsonl --limit 10
```

Note the `untagged` case: `cost-api` only reports per team, so the honest answer is "unknown". An agent that invents a number there fails, which is the behaviour you want to catch.

Also try ADK's built-in evaluator: record a few sessions in `adk web`, save them as an eval set, and run `adk eval`. Decide in your ADR which harness your team would maintain. Pick a pass rate, write it down, and track it per release (Phase 9 makes it a CI gate).

### Lab 5.6 — LangChain building blocks

Read `langgraph_report/live.py`. It shows the three pieces you need in any LangChain codebase:

- `ChatOpenAI(base_url=<gateway>, model="smart")`: a chat model through *your* gateway, so budgets and spend logs still apply
- `MultiServerMCPClient(...).get_tools()`: your FastMCP tools as LangChain tools, not rewritten
- `.with_structured_output(ReviewVerdict)`: a validated Pydantic object back

Exercise: in a notebook, load the MCP tools and call `get_team_cost` directly with `ainvoke`. Then compare `with_structured_output` with Phase 4's `ask_structured`: what does each do when the model returns invalid JSON? Try it by asking for a schema the model struggles with.

### Lab 5.7 — The monthly report as a LangGraph state machine

Implement the graph assembly in `langgraph_report/graph.py` (`TODO Lab 5.7`). The node functions are given; you wire the edges, the bounded review loop, and `interrupt` for approval.

```bash
pytest -q tests/test_langgraph_report.py
docker run -d --name lg-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16-alpine
export CHECKPOINT_DB=postgresql://postgres:pg@localhost:5433/postgres
python -m costpilot_agents.langgraph_report.run start --thread demo1 --team payments --month 2026-09
#   press Ctrl-C right after "[gather] done", then run the same command again:
#   it continues from the checkpoint instead of starting over
python -m costpilot_agents.langgraph_report.run resume --thread demo1 --decision approved
```

Then write the comparison ADR, ADK versus LangGraph for CostPilot, on: how explicit the control flow is, state and checkpointing, human-in-the-loop, testability, observability, deployment options, and what your team already knows. There is no universally right answer; there is a right answer for your constraints.

Bonus: ADK can host a compiled LangGraph graph as an agent (`google.adk.agents.langgraph_agent`), so a team could standardize on ADK for orchestration while keeping existing graphs.

### Lab 5.8 — Deploy to Vertex AI Agent Engine

Agent Engine is Vertex AI's managed runtime for agents and supports ADK, LangChain and LangGraph ([overview](https://docs.cloud.google.com/agent-builder/agent-engine/overview)).

```bash
pip install -e ".[agent-engine]"
export PROJECT=... LOCATION=us-central1 STAGING_BUCKET=gs://...
python agent_engine/deploy.py deploy
python agent_engine/deploy.py ask --engine <name> "How much did payments spend in 2026-09?"
```

The deployed agent must reach your gateway and MCP server, which are on `localhost` until Phase 9. For this lab, either expose them temporarily on Cloud Run (Phase 8 uses Cloud Run as one of the compared runtimes) or do the deployment comparison after Phase 9. Record cold start, p95 latency, cost per 1,000 questions and operational effort, then **delete the engine**: `python agent_engine/deploy.py delete --engine <name>`. Phase 8 uses these numbers.

### Lab 5.9 — Typed decisions with calibrated confidence (optional)

Agents *write*; many steps in an agent system only need to *decide*: pick one of five causes, say yes or no, rate urgency 0–3. Asking a chat model for those gets you text to parse, plus a "confidence" the model invents. A classifier built for decisions, such as **[Jev from TypeSafe AI](https://typesafe.ai/)**, returns a probability for every option in one call: `Noul` (yes/no), `Choice` (one of N), `Score` (a rubric level). Probabilities you can trust let code do something chat output can't: **act when sure, ask a person when not, and measure whether "90% sure" means 90%.**

The use case: when `detect_anomalies` finds a spike, triage it. Is it a real problem, or the monthly commitment fee? What caused it? How urgent is it? Get it wrong one way and a runaway job burns money all weekend; get it wrong the other way and the team learns to ignore CostPilot.

```
anomaly + context ─► decider ─► P(real), P(each cause), P(each urgency level)
                     mock | jev | llm            │
                                    policy.py ◄──┘  (thresholds you own, versioned)
                                        │
        dismiss ◄─ P(real) < 0.15       ├─ review ◄─ unsure, cause unclear, late, or API error
        notify ◄── daily budget used    └─ propose_ticket ─► human approval (Lab 5.7's interrupt) ─► ticket
```

1. **Supply chain first.** The SDK is `typesafe-sdk` on PyPI (import `typesafe_sdk`). A package named `typesafe-ai` also exists on PyPI and is *not* the SDK. Guessable names like that one are exactly what attackers register when coding assistants hallucinate package names ("slopsquatting"). Take package names from the vendor's docs, never from memory or a model, and pin them: `pip install -e ".[jev]"`.
2. Read `typed_decisions/deciders.py`. All three deciders share one interface, and `with_deadline` turns a late answer or an API error into "unsure", never into an action. That idea comes from [jev-trader](https://github.com/jarrodwatts/jev-trader), which holds whenever the model misses a block, starts on a mock model and only dry-runs without credentials. In the starter, write `JevDecider.questions()` and `decide()`. The tests drive the **real SDK** against a fake System One server (`httpx2.MockTransport`), so they check the exact request and response format with no key and no network.
3. Write `policy.route()` in the starter. The decider estimates and the policy decides. Each threshold is a statement about what mistakes cost, so it lives in reviewed, versioned code, like a prompt.
4. Run the comparison on the labeled set:

```bash
python -m costpilot_agents.typed_decisions.run_eval --decider mock
TYPESAFE_API_KEY=... python -m costpilot_agents.typed_decisions.run_eval --decider jev
python -m costpilot_agents.typed_decisions.run_eval --decider llm --gateway http://localhost:4000
```

   Compare the three on **Brier score** and **calibration error** (are the probabilities honest?), **coverage** (how much was decided without a person), **missed real problems** (dismissed but real: the expensive mistake), **false-alarm proposals**, latency and tokens. The mock is safe but useless: it sends 16 of 18 cases to a person. Self-reported LLM confidence often clusters near 0.9 whether the answer is right or not. Your calibration report shows whether yours does. Read the traps in the eval set (`t07`, `t16`): a calendar entry that explains a *different* service, and an announced training run at four times its budget.
5. Wire it into the flow: `typed_decisions/graph.py` runs decide → route → review or approval → ticket → log. Only a person's resume value creates a ticket. Every outcome is logged with its probabilities and policy version, and people's answers become labels. Re-running `run_eval` on last month's log tells you whether the decider is still calibrated on *your* data.

Before you send cost data to any third-party API, check it against Phase 6's data classification. `AnomalyCase.as_state()` sends team ids, services and amounts, but no people, no resource names and no secrets. Ask whether your organization allows even that. In production, the key goes in Secret Manager like the gateway keys, and egress to `api.typesafe.ai` shows up in your NetworkPolicy review (Phase 9).

In TypeScript, the same calls are available through the AI SDK's `experimental_evaluate` with the TypeSafe provider, as jev-trader does.

## Done when

- [ ] The coordinator answers your eval set at the pass rate you chose and wrote down
- [ ] Every boundary in Lab 5.3 has a test that proves it holds, and the injection regression test passes
- [ ] The live injection drill passes 5 out of 5 runs for each payload
- [ ] The monthly report runs as an ADK `Workflow` and as a LangGraph graph, with a comparison ADR
- [ ] A LangGraph run survives a kill and resumes from its Postgres checkpoint
- [ ] You have numbers from Agent Engine for Phase 8 (and deleted the engine)
- [ ] (Lab 5.9) Your triage ADR compares mock, Jev and LLM deciders on calibration, coverage and missed problems

## Write it down (ADRs)

- `0005-routing-vs-workflows.md` (Lab 5.2)
- `0006-execution-boundaries.md` (Lab 5.3): the five policies and where each is enforced
- `0007-adk-vs-langgraph.md` (Lab 5.7)
- `0017-typed-decisions.md` (Lab 5.9, optional): which decider triages anomalies, the thresholds, and the evidence

## Teach it (5 minutes)

Run the injection drill live in front of your team, then show the one test that makes it harmless. Ask: which of our current automations would fail this drill?

## Stretch goals

- Give the recommender a `request_approval` tool that records a pending approval, plus a tiny approve endpoint that writes the approval into session state, completing the human-in-the-loop flow end to end.
- Add a `LoopAgent`-style self-critique to the recommender and measure whether it improves eval accuracy enough to justify its extra model calls.
- Expose the monthly report workflow over A2A so other teams' agents can request reports.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `adk web` shows no apps | Run it inside `adk_apps/`, and `pip install -e ..` first so `costpilot_agents` imports. |
| `KeyError: 'COORDINATOR_VKEY'` | Re-run Phase 4's `create_virtual_keys.sh` (it now includes the coordinator) and export the keys. |
| Agent says it has no tools | `mcp-finops` isn't running on :8001, or `COSTPILOT_MCP_URL` points elsewhere. |
| `DeprecationWarning: SequentialAgent is deprecated` | You're using the older API. Use `Workflow` edges as in `build_monthly_report`. |
| LangGraph run starts over after a restart | `CHECKPOINT_DB` isn't set, so it used the in-memory saver. |
| Model calls stop with "reached its limit" | That's the budget guard. Raise `max_model_calls` deliberately, or narrow the question. |

## Teardown

Delete the Agent Engine deployment, stop the `lg-pg` container (`docker rm -f lg-pg`), and keep the gateway, MCP server and cost-api for the next phases.
