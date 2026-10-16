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
    # TODO Lab 6.3 (a): allow if the principal has "costs:read_all" or the team is in
    #   principal.teams; otherwise raise SecurityProblem(403, "forbidden", ...).
    raise NotImplementedError


def visible_teams(principal: Principal, teams: list[str]) -> list[str]:
    # TODO Lab 6.3 (b): everything for "costs:read_all", else only the principal's teams.
    raise NotImplementedError
