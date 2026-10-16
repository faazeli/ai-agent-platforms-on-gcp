"""Evaluate the agent team: right answer AND right path.

For each case of Phase 4's eval set, the coordinator answers the question with
tools (no data in the prompt). We record which tools were called, score the
trajectory against the tools that case needs, extract a typed Answer from the
final text with Phase 4's ``ask_structured``, and score it with Phase 4's scorer.

    export COORDINATOR_VKEY=... COST_ANALYST_VKEY=... ANOMALY_DETECTOR_VKEY=... RECOMMENDER_VKEY=...
    export OPENAI_API_KEY=$EVAL_RUNNER_VKEY
    python -m costpilot_agents.evals --evalset ../../04-llm-gateway-and-vertex-ai/solution/llm-toolkit/evals/evalset.jsonl

`adk eval` (ADK's built-in evaluator) is the other option: it scores tool
trajectories and responses from an .evalset.json you can record in `adk web`.
Try both and keep the one your team will actually maintain.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai import types

# Which tools a correct path must include, per eval tag. Tags whose questions no
# tool can answer are expected to end in an honest "unknown".
EXPECTED_TOOLS: dict[str, set[str]] = {
    "total": {"get_team_cost"}, "billed": {"get_team_cost"}, "commitment": {"get_team_cost"},
    "top_service": {"get_team_cost"}, "count": {"get_team_cost"}, "ranking": {"get_team_cost"},
    "anomaly": {"detect_anomalies"}, "untagged": set(),
}
UNANSWERABLE_WITH_TOOLS = {"untagged"}  # cost-api only reports per team


@dataclass
class AgentRun:
    final_text: str
    tool_calls: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)


async def run_agent(agent: Any, question: str, app_name: str = "costpilot-eval") -> AgentRun:
    sessions = InMemorySessionService()
    # Agents run as `agent=`; ADK 2.x workflows run as `node=`.
    target = {"node": agent} if isinstance(agent, Workflow) else {"agent": agent}
    runner = Runner(app_name=app_name, session_service=sessions, **target)
    session = await sessions.create_session(app_name=app_name, user_id="eval", session_id=uuid.uuid4().hex)
    run = AgentRun(final_text="")
    message = types.Content(role="user", parts=[types.Part(text=question)])
    async for event in runner.run_async(user_id="eval", session_id=session.id, new_message=message):
        if event.author not in run.agents:
            run.agents.append(event.author)
        for part in (event.content.parts if event.content else []) or []:
            if part.function_call and part.function_call.name != "transfer_to_agent":
                run.tool_calls.append(part.function_call.name)
            if part.text and event.is_final_response():
                run.final_text = part.text
    return run


def trajectory_ok(tag: str, tool_calls: list[str]) -> bool:
    return EXPECTED_TOOLS.get(tag, set()) <= set(tool_calls)


async def evaluate(agent: Any, cases: list[dict[str, Any]], extract) -> dict[str, Any]:
    """``extract(final_text) -> Answer``; injected so tests can avoid the gateway."""
    from costpilot_llm.evals.scorer import is_correct

    rows = []
    for case in cases:
        run = await run_agent(agent, case["question"])
        expected = case["expected"]
        if case["tag"] in UNANSWERABLE_WITH_TOOLS:
            expected = {"answer_type": "text", "value": "unknown"}
        answer = await extract(run.final_text)
        rows.append({"id": case["id"], "tag": case["tag"], "correct": is_correct(expected, answer),
                     "trajectory_ok": trajectory_ok(case["tag"], run.tool_calls),
                     "tool_calls": run.tool_calls, "agents": run.agents})
    n = len(rows) or 1
    return {"cases": len(rows), "accuracy": round(sum(r["correct"] for r in rows) / n, 3),
            "trajectory_accuracy": round(sum(r["trajectory_ok"] for r in rows) / n, 3),
            "avg_tool_calls": round(sum(len(r["tool_calls"]) for r in rows) / n, 2), "rows": rows}


async def _main(args: argparse.Namespace) -> None:
    from openai import AsyncOpenAI
    from costpilot_llm.evals.scorer import Answer
    from costpilot_llm.structured import ask_structured

    from .adk.live import live_models, mcp_tools
    from .adk.team import build_team

    gateway = AsyncOpenAI(base_url=args.gateway)

    async def extract(text: str):
        parsed = await ask_structured(gateway, model="fast", schema=Answer, messages=[{"role": "user", "content": (
            "Extract the single answer from this assistant reply. If it says it cannot answer, "
            f"use answer_type text and value unknown.\n\nReply:\n{text}")}])
        return parsed.value

    cases = [json.loads(line) for line in args.evalset.read_text().splitlines() if line.strip()]
    report = await evaluate(build_team(live_models(), mcp_tools), cases[: args.limit], extract)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    Path(args.out).write_text(json.dumps(report, indent=2))
    if args.min_accuracy is not None and report["accuracy"] < args.min_accuracy:
        raise SystemExit(f"FAIL: accuracy {report['accuracy']} < required {args.min_accuracy}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evalset", type=Path, required=True)
    parser.add_argument("--gateway", default="http://localhost:4000")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--out", default="agent_eval_report.json")
    parser.add_argument("--min-accuracy", type=float, default=None,
                        help="exit non-zero below this accuracy (a CI / canary gate)")
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
