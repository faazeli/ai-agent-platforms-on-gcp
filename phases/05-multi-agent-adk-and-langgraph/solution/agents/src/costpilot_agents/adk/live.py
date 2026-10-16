"""Production wiring: models through the LiteLLM gateway, tools from mcp-finops.

Each agent gets its own gateway virtual key (Phase 4), so budgets and spend are
tracked per agent. Tools come from the MCP server with a ``tool_filter`` that
matches the agent's policy, so an agent never even *sees* tools outside its
allow-list; the policy guard is the second line of defense.
"""

from __future__ import annotations

import os

from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

GATEWAY = os.environ.get("COSTPILOT_GATEWAY_URL", "http://localhost:4000")
MCP_URL = os.environ.get("COSTPILOT_MCP_URL", "http://localhost:8001/mcp")

# agent -> (model alias, env var holding that agent's virtual key)
AGENT_MODELS = {
    "coordinator": ("fast", "COORDINATOR_VKEY"),
    "cost_analyst": ("smart", "COST_ANALYST_VKEY"),
    "anomaly_detector": ("fast", "ANOMALY_DETECTOR_VKEY"),
    "recommender": ("smart", "RECOMMENDER_VKEY"),
    "cost_gatherer": ("fast", "COST_ANALYST_VKEY"),
    "anomaly_gatherer": ("fast", "ANOMALY_DETECTOR_VKEY"),
    "report_writer": ("smart", "COST_ANALYST_VKEY"),
}
TEAM = ("coordinator", "cost_analyst", "anomaly_detector", "recommender")
REPORT = ("cost_gatherer", "anomaly_gatherer", "report_writer")


def gateway_model(agent: str) -> LiteLlm:
    alias, key_env = AGENT_MODELS[agent]
    # "openai/<alias>" tells LiteLLM to speak the OpenAI protocol to our gateway.
    return LiteLlm(model=f"openai/{alias}", api_base=GATEWAY, api_key=os.environ[key_env])


def mcp_tools(names: list[str]) -> list:
    if not names:
        return []
    return [McpToolset(connection_params=StreamableHTTPConnectionParams(url=MCP_URL), tool_filter=names)]


def live_models(agents: tuple[str, ...] = TEAM) -> dict[str, LiteLlm]:
    return {agent: gateway_model(agent) for agent in agents}
