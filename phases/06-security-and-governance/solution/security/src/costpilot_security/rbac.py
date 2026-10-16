"""Role-based access control: roles grant permissions; team scope limits data.

Enforce the same rules at three layers so no single bug exposes data:
  1. cost-api endpoints (this module)
  2. MCP tools (the MCP server checks before calling cost-api)
  3. BigQuery row access policies on x_TeamId (gcp/row_access_policies.sql)
"""

from __future__ import annotations

from .identity import Principal
from .problems import SecurityProblem

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"costs:read"}),
    "team_lead": frozenset({"costs:read", "recommendations:read", "tickets:approve"}),
    "finops_admin": frozenset({"costs:read", "costs:read_all", "recommendations:read",
                               "tickets:approve", "audit:read"}),
    "workload": frozenset(),  # a workload without a delegated user can do nothing on its own
}


def permissions(principal: Principal) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(principal.role, frozenset())


def check(principal: Principal, permission: str) -> None:
    if permission not in permissions(principal):
        raise SecurityProblem(403, "forbidden", "Not allowed", f"Your role lacks the {permission} permission.")


def check_team(principal: Principal, team_id: str) -> None:
    if "costs:read_all" in permissions(principal) or team_id in principal.teams:
        return
    # 403, not 404: the caller is authenticated; hiding existence is a separate choice (see README).
    raise SecurityProblem(403, "forbidden", "Not allowed", "You are not a member of this team.")


def visible_teams(principal: Principal, teams: list[str]) -> list[str]:
    if "costs:read_all" in permissions(principal):
        return teams
    return [t for t in teams if t in principal.teams]
