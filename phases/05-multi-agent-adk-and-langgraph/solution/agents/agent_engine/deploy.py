"""Lab 5.8 — deploy the CostPilot coordinator to Vertex AI Agent Engine.

Agent Engine is Vertex AI's managed runtime for agents; it supports ADK,
LangChain and LangGraph agents and provides managed sessions and memory.

    pip install "google-cloud-aiplatform[agent_engines,adk]"
    export PROJECT=... LOCATION=us-central1 STAGING_BUCKET=gs://...
    python agent_engine/deploy.py deploy
    python agent_engine/deploy.py ask  --engine <resource name> "How much did payments spend in 2026-09?"
    python agent_engine/deploy.py delete --engine <resource name>

Networking: the deployed agent must reach your gateway and mcp-finops. Locally
they are on localhost, which Agent Engine cannot see. Expose them on an internal
URL first (Phase 9 runs them on GKE), set COSTPILOT_GATEWAY_URL / COSTPILOT_MCP_URL
in env_vars below, and keep the keys in Secret Manager.

The Agent Engine SDK surface changes between releases. This script follows the
`vertexai.Client(...).agent_engines` style; if a call has moved, check the
"Deploy an agent" page in the Agent Engine docs. The flow stays the same:
wrap the agent in AdkApp → create → query → delete.
"""

import os
import sys
import time

import vertexai
from vertexai import agent_engines

PROJECT, LOCATION = os.environ["PROJECT"], os.environ.get("LOCATION", "us-central1")
client = vertexai.Client(project=PROJECT, location=LOCATION)


def deploy() -> None:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from costpilot_agents.adk.live import live_models, mcp_tools
    from costpilot_agents.adk.team import build_team

    app = agent_engines.AdkApp(agent=build_team(live_models(), mcp_tools))
    started = time.time()
    remote = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "costpilot-coordinator",
            "requirements": ["google-cloud-aiplatform[agent_engines,adk]", "litellm", "pydantic>=2.11"],
            "extra_packages": [os.path.join(os.path.dirname(__file__), "..", "src", "costpilot_agents")],
            "staging_bucket": os.environ["STAGING_BUCKET"],
            "env_vars": {k: os.environ[k] for k in (
                "COSTPILOT_GATEWAY_URL", "COSTPILOT_MCP_URL", "COORDINATOR_VKEY", "COST_ANALYST_VKEY",
                "ANOMALY_DETECTOR_VKEY", "RECOMMENDER_VKEY") if k in os.environ},
        },
    )
    print(f"deployed in {time.time() - started:.0f}s: {remote.api_resource.name}")


def ask(engine: str, question: str) -> None:
    remote = client.agent_engines.get(name=engine)
    started = time.perf_counter()
    for event in remote.stream_query(user_id="lab-user", message=question):
        for part in event.get("content", {}).get("parts", []):
            if part.get("text"):
                print(part["text"])
    print(f"\nlatency {time.perf_counter() - started:.2f}s")


def delete(engine: str) -> None:
    client.agent_engines.delete(name=engine, force=True)
    print("deleted", engine)


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "deploy":
        deploy()
    elif command == "ask":
        ask(sys.argv[sys.argv.index("--engine") + 1], sys.argv[-1])
    elif command == "delete":
        delete(sys.argv[sys.argv.index("--engine") + 1])
