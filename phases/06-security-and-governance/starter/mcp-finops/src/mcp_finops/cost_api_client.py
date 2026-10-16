"""A small typed client for cost-api, used by the MCP tools.

The MCP server never touches BigQuery directly: it calls cost-api over HTTP.
That keeps one place for data access rules (and, in Phase 6, for RBAC), and it
means the MCP server's service account needs no BigQuery permissions at all.

Errors from cost-api arrive as RFC 9457 Problem Details. We turn them into
``ToolError``s whose message *is* a problem document, plus a ``hint`` telling the
model what to do next. One error vocabulary spans HTTP and MCP.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

from .models import DailyCost, ResourceCost, TeamCostSummary

# What the model should do next for each problem type. Keep these actionable.
HINTS = {
    "team-not-found": "Call list_teams to get valid team ids, then retry with one of them.",
    "no-cost-data": "Try a more recent month, or ask the user which period they mean.",
    "invalid-request": "Fix the arguments listed in invalid_params and retry.",
    "forbidden": "The user is not allowed to see this team. Tell the user; do not retry.",
    "upstream-unavailable": "The cost service is unavailable. Tell the user and stop; do not retry in a loop.",
}


def tool_error(problem: dict[str, Any]) -> ToolError:
    slug = str(problem.get("type", "")).rstrip("/").rsplit("/", 1)[-1]
    body = {k: problem[k] for k in ("type", "title", "status", "detail", "invalid_params") if k in problem}
    if slug in HINTS:
        body["hint"] = HINTS[slug]
    return ToolError(json.dumps(body))


class CostApiClient:
    def __init__(self, http: httpx.AsyncClient, problem_base_url: str = "https://example.com/problems") -> None:
        self._http = http
        self._problem_base = problem_base_url.rstrip("/")

    async def _get(self, path: str, **params: Any) -> Any:
        try:
            response = await self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        except httpx.HTTPError as exc:
            raise tool_error({
                "type": f"{self._problem_base}/upstream-unavailable", "title": "Cost service unavailable",
                "status": 503, "detail": f"Could not reach cost-api ({type(exc).__name__}).",
            }) from exc
        if response.is_success:
            return response.json()
        try:
            problem = response.json()
        except ValueError:
            problem = {"type": f"{self._problem_base}/upstream-error", "title": "Unexpected upstream response",
                       "status": response.status_code, "detail": "cost-api returned a non-JSON error."}
        raise tool_error(problem)

    async def list_teams(self) -> list[str]:
        return [t["team_id"] for t in await self._get("/v1/teams")]

    async def team_summary(self, team_id: str, month: str) -> TeamCostSummary:
        return TeamCostSummary.model_validate(await self._get(f"/v1/teams/{team_id}/summary", month=month))

    async def top_resources(self, team_id: str, month: str, limit: int) -> list[ResourceCost]:
        rows = await self._get(f"/v1/teams/{team_id}/resources", month=month, limit=limit)
        return [ResourceCost.model_validate(r) for r in rows]

    async def daily_costs(self, team_id: str, end: date, days: int) -> list[DailyCost]:
        rows = await self._get(f"/v1/teams/{team_id}/daily", end=end.isoformat(), days=days)
        return [DailyCost.model_validate(r) for r in rows]
