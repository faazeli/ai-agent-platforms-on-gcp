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

from datetime import date, timedelta
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.dependencies import get_access_token
from pydantic import Field

from costpilot_security.identity import Principal, principal_from_claims
from costpilot_security.problems import SecurityProblem
from costpilot_security.rbac import check, check_team

from .anomalies import find_anomalies
from .cost_api_client import CostApiClient, tool_error
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


def current_user(team_id: str | None = None) -> Principal | None:
    """The authenticated user for this MCP request, checked against RBAC.

    This is the second of three enforcement layers (cost-api and BigQuery are the
    others). Checking here means a forbidden request never even leaves the MCP server.
    Returns None when the server runs without auth (local development).
    """
    token = get_access_token()
    if token is None:
        return None
    user = principal_from_claims(token.claims or {"sub": token.client_id})
    try:
        check(user, "costs:read")
        if team_id is not None:
            check_team(user, team_id)
    except SecurityProblem as exc:
        raise tool_error(exc.body("https://example.com/problems", "mcp-finops")) from exc
    return user


def build_server(cost_api: CostApiClient, auth: AuthProvider | None = None) -> FastMCP:
    mcp = FastMCP("finops", instructions=INSTRUCTIONS, mask_error_details=True, auth=auth)

    @mcp.tool(annotations=READ_ONLY, timeout=20)
    async def list_teams() -> TeamList:
        """List the team ids that have cost data. Use this first when a user names a team loosely."""
        return TeamList(teams=await cost_api.list_teams(current_user()))

    @mcp.tool(annotations=READ_ONLY, timeout=20)
    async def get_team_cost(team_id: TeamId, month: Month) -> TeamCostSummary:
        """Total FOCUS EffectiveCost and BilledCost for one team in one calendar month,
        with its top 5 services by EffectiveCost. Use for "how much did X spend" questions.
        BilledCost higher than EffectiveCost usually means unused commitments."""
        return await cost_api.team_summary(team_id, month, current_user(team_id))

    @mcp.tool(annotations=READ_ONLY, timeout=20)
    async def top_resources(
        team_id: TeamId,
        month: Month,
        limit: Annotated[int, Field(ge=1, le=20, description="How many resources, 1-20")] = 10,
    ) -> ResourceList:
        """The most expensive individual resources (by EffectiveCost) for a team in a month.
        Use to explain what is driving a team's cost."""
        resources = await cost_api.top_resources(team_id, month, limit, current_user(team_id))
        return ResourceList(team_id=team_id, month=month, resources=resources)

    @mcp.tool(annotations=READ_ONLY, timeout=30)
    async def detect_anomalies(
        team_id: TeamId,
        end_date: Annotated[date, Field(description="Last day to check, YYYY-MM-DD (usually yesterday)")],
        days: Annotated[int, Field(ge=7, le=60, description="How many days to check, 7-60")] = 30,
        threshold: Annotated[float, Field(ge=2.0, le=6.0,
                                          description="Z-score above the trailing 7-day mean that counts")] = 3.0,
    ) -> AnomalyReport:
        """Find days when a team's daily usage cost jumped well above its trailing 7-day average.
        Returns an empty list when nothing is unusual; say so plainly rather than guessing."""
        lookback = 7
        series = await cost_api.daily_costs(team_id, end_date, days + lookback, current_user(team_id))
        anomalies = find_anomalies(series, threshold=threshold, lookback=lookback)
        return AnomalyReport(
            team_id=team_id,
            window_start=end_date - timedelta(days=days - 1),
            window_end=end_date,
            threshold=threshold,
            anomalies=anomalies,
        )

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
