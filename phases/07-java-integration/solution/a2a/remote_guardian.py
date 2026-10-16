"""Lab 7.5 — let the Python coordinator delegate to the Java agent over A2A.

The Java agent runs as its own service and publishes an *agent card* (a JSON
description of what it can do and where to reach it). ADK Python's
RemoteA2aAgent reads that card and looks like any other sub-agent to the
coordinator, so routing works unchanged across languages.

    export GUARDIAN_AGENT_CARD=http://localhost:8090/.well-known/agent-card.json   # from the Java server
    python a2a/remote_guardian.py "Is payments on budget for 2026-09?"

Install the A2A extra first:  pip install "google-adk[a2a]"
"""

import asyncio
import os
import sys
from pathlib import Path

PHASE5 = Path(__file__).resolve().parents[3] / "05-multi-agent-adk-and-langgraph/solution/agents/src"
sys.path.insert(0, str(PHASE5))

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent  # noqa: E402

from costpilot_agents.adk.live import live_models, mcp_tools  # noqa: E402
from costpilot_agents.adk.team import build_team  # noqa: E402
from costpilot_agents.evals import run_agent  # noqa: E402


def build_team_with_guardian():
    team = build_team(live_models(), mcp_tools)
    guardian = RemoteA2aAgent(
        name="budget_guardian",
        description="Checks whether a team is on track against its monthly budget (Java, via A2A).",
        agent_card=os.environ.get("GUARDIAN_AGENT_CARD", "http://localhost:8090/.well-known/agent-card.json"),
    )
    team.sub_agents.append(guardian)
    guardian.parent_agent = team
    team.instruction += "\n- Budget questions (\"on budget\", \"over budget\", forecasts) → budget_guardian\n"
    return team


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "Is payments on budget for 2026-09?"
    run = asyncio.run(run_agent(build_team_with_guardian(), question))
    print("agents:", run.agents, "\n" + run.final_text)
