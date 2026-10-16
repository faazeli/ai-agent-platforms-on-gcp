"""Wire the report graph to real services with LangChain building blocks.

* Chat model: ``ChatOpenAI`` pointed at the LiteLLM gateway, so Phase 4's
  budgets, fallbacks and spend logs still apply. Never a vendor key here.
* Tools: loaded from mcp-finops with ``langchain-mcp-adapters``, not rewritten.
* Review: ``with_structured_output`` returns a validated Pydantic object.
"""

from __future__ import annotations

import calendar
import json
import os
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .graph import ReportDeps, ReportState, Review

GATEWAY = os.environ.get("COSTPILOT_GATEWAY_URL", "http://localhost:4000")
MCP_URL = os.environ.get("COSTPILOT_MCP_URL", "http://localhost:8001/mcp")


class ReviewVerdict(BaseModel):
    passed: bool = Field(description="True if every number in the draft appears in the facts")
    feedback: str = Field(description="What to fix, or empty if passed")


def gateway_chat(alias: str = "fast") -> ChatOpenAI:
    return ChatOpenAI(base_url=GATEWAY, model=alias, api_key=os.environ["COST_ANALYST_VKEY"], temperature=0)


async def build_live_deps() -> ReportDeps:
    client = MultiServerMCPClient({"finops": {"url": MCP_URL, "transport": "streamable_http"}})
    tools = {t.name: t for t in await client.get_tools()}
    writer_model = gateway_chat("fast")
    reviewer = gateway_chat("smart").with_structured_output(ReviewVerdict)

    async def gather(team_id: str, month: str) -> dict[str, Any]:
        year, mon = map(int, month.split("-"))
        last_day = f"{month}-{calendar.monthrange(year, mon)[1]:02d}"
        summary = await tools["get_team_cost"].ainvoke({"team_id": team_id, "month": month})
        resources = await tools["top_resources"].ainvoke({"team_id": team_id, "month": month, "limit": 5})
        anomalies = await tools["detect_anomalies"].ainvoke({"team_id": team_id, "end_date": last_day, "days": 30})
        return {"summary": summary, "top_resources": resources, "anomalies": anomalies}

    async def write(state: ReportState) -> str:
        feedback = f"\nA reviewer rejected the last draft: {state['feedback']}\nFix that." \
            if state.get("feedback") else ""
        prompt = (f"Write a monthly cost report (under 150 words) for {state['team_id']} in {state['month']} "
                  f"using only these facts:\n{json.dumps(state['facts'], default=str)}{feedback}")
        return (await writer_model.ainvoke(prompt)).content

    async def review(state: ReportState) -> Review:
        verdict = await reviewer.ainvoke(
            f"Facts:\n{json.dumps(state['facts'], default=str)}\n\nDraft:\n{state['draft']}\n\n"
            "Does every number in the draft appear in, or follow directly from, the facts?")
        return Review(verdict.passed, verdict.feedback)

    return ReportDeps(gather=gather, write=write, review=review)
