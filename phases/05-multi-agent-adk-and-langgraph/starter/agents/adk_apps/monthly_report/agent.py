"""The deterministic monthly report workflow (gather in parallel, then write)."""

from costpilot_agents.adk.live import REPORT, live_models, mcp_tools
from costpilot_agents.adk.team import build_monthly_report

root_agent = build_monthly_report(live_models(REPORT), mcp_tools)
