"""mcp-finops: CostPilot's FinOps tools, exposed over the Model Context Protocol.

Three MCP primitives are used, each for what it is for:

* **Tools** — actions the model decides to call (all read-only here).
* **Resources** — reference material the client can attach (the FOCUS glossary).
* **Prompts** — reusable, parameterized instructions a user picks (a monthly review).

Design rules for tools that a model will call:

1. The docstring and parameter descriptions ARE the prompt the model reads. Say
   when to use the tool, what it returns, and what the units are.
2. Bound every input server-side (patterns, ranges). The model will eventually
   ask for a million rows.
3. Return typed models so clients get structured output with a schema.
4. Fail with Problem Details plus a hint about what to do next. Never leak
   stack traces or internals (``mask_error_details=True``).
"""

from __future__ import annotations

from datetime import date, timedelta  # noqa: F401 (used in Lab 3.4)
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .anomalies import find_anomalies
from .cost_api_client import CostApiClient
from .models import AnomalyReport, ResourceList, TeamCostSummary, TeamList

TeamId = Annotated[str, Field(pattern=r"^[a-z0-9-]{2,40}$",
                              description="Team id exactly as returned by list_teams, e.g. 'payments'")]
Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                             description="Calendar month as YYYY-MM, e.g. '2026-09'")]

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

INSTRUCTIONS = """\
FinOps tools for CostPilot. All costs are FOCUS EffectiveCost (amortized, after
commitments) in the currency returned, unless a field says otherwise.
Start with list_teams if you don't know the exact team id. Prefer get_team_cost
for "how much" questions, top_resources for "what is driving it", and
detect_anomalies for "did anything unusual happen". All tools are read-only.
"""

GLOSSARY = """\
# FOCUS columns used by CostPilot
- BilledCost: what the invoice charges for the row, in the billing period it is invoiced.
- EffectiveCost: amortized cost after commitments and discounts; what teams should see.
- ListCost: cost at public list prices; ListCost - EffectiveCost = savings.
- ChargeCategory: Usage, Purchase, Tax, Credit or Adjustment.
- ServiceCategory: a provider-neutral grouping such as Compute, Storage, Analytics,
  or AI and Machine Learning.
- x_TeamId: CostPilot's owning team for a row (a custom column).
"""


def build_server(cost_api: CostApiClient) -> FastMCP:
    mcp = FastMCP("finops", instructions=INSTRUCTIONS, mask_error_details=True)

    @mcp.tool(annotations=READ_ONLY, timeout=20)
    async def list_teams() -> TeamList:
        """List the team ids that have cost data. Use this first when a user names a team loosely."""
        return TeamList(teams=await cost_api.list_teams())

    # TODO Lab 3.1: add get_team_cost(team_id: TeamId, month: Month) -> TeamCostSummary.
    #   Decorate with @mcp.tool(annotations=READ_ONLY, timeout=20). Write a docstring a
    #   model can act on: when to use it, what it returns, the units.

    # TODO Lab 3.4 (b): add top_resources(team_id, month, limit) -> ResourceList,
    #   with limit an Annotated[int, Field(ge=1, le=20, ...)] defaulting to 10.

    # TODO Lab 3.4 (c): add detect_anomalies(team_id, end_date: date, days 7-60 = 30,
    #   threshold 2.0-6.0 = 3.0) -> AnomalyReport. Fetch days + 7 days from
    #   cost_api.daily_costs so the first checked day has a full 7-day lookback,
    #   then call find_anomalies.

    @mcp.resource("focus://glossary", mime_type="text/markdown")
    def glossary() -> str:
        """Definitions of the FOCUS columns CostPilot reports on."""
        return GLOSSARY

    @mcp.prompt
    def monthly_review(team_id: str, month: str) -> str:
        """A structured monthly cost review for one team."""
        return (
            f"Review {team_id}'s cloud costs for {month}. Use get_team_cost, then top_resources, "
            f"then detect_anomalies for the last 30 days of that month. Report: total EffectiveCost, "
            f"the top 3 drivers, any anomalies with dates, and one concrete saving to investigate. "
            f"If BilledCost exceeds EffectiveCost, mention unused commitments."
        )

    return mcp
