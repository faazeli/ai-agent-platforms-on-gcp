"""CostPilot's coordinator + specialists, wired to the gateway and mcp-finops."""

from costpilot_agents.adk.live import live_models, mcp_tools
from costpilot_agents.adk.team import build_team

root_agent = build_team(live_models(), mcp_tools)
