"""cost-api's Zero Trust wiring: who is calling, may they, and a record of it.

Every endpoint depends on ``Caller``: it authenticates the request (user token,
or a workload token plus a delegation header), and ``authorize_team`` applies
RBAC and team scope *before* the data layer is touched. Every authorization
decision lands in the hash-chained audit log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from costpilot_security.audit import AuditLog
from costpilot_security.identity import DELEGATION_HEADER, Principal, TokenVerifier, resolve_principal
from costpilot_security.problems import SecurityProblem
from costpilot_security.rbac import check, check_team
from costpilot_security.service_auth import GOOGLE_ISSUER, GOOGLE_JWKS

from .settings import Settings

log = logging.getLogger("cost_api.security")
LOCAL_DEV = Principal("local-developer", role="finops_admin")


@dataclass
class SecurityContext:
    users: TokenVerifier
    workloads: TokenVerifier | None
    trusted_delegators: frozenset[str]


def build_security(settings: Settings) -> SecurityContext | None:
    if not settings.auth_enabled:
        log.warning("AUTH DISABLED: every request is treated as a local finops_admin. Never do this outside dev.")
        return None
    if not settings.oidc_jwks_uri:
        raise RuntimeError("Set COST_API_OIDC_JWKS_URI, or COST_API_AUTH_ENABLED=false for local development.")
    return SecurityContext(
        users=TokenVerifier(issuer=settings.oidc_issuer, audience=settings.oidc_audience,
                            jwks_uri=settings.oidc_jwks_uri),
        workloads=TokenVerifier(issuer=GOOGLE_ISSUER, audience=settings.workload_audience, jwks_uri=GOOGLE_JWKS),
        trusted_delegators=frozenset(settings.trusted_delegators),
    )


def _bearer(header: str | None) -> str | None:
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def caller(request: Request) -> Principal:
    security: SecurityContext | None = request.app.state.security
    if security is None:
        return LOCAL_DEV
    try:
        return resolve_principal(_bearer(request.headers.get("authorization")),
                                 request.headers.get(DELEGATION_HEADER),
                                 user_verifier=security.users, workload_verifier=security.workloads,
                                 trusted_delegators=security.trusted_delegators)
    except SecurityProblem as exc:
        audit(request).record(action="authenticate", decision="denied", resource=request.url.path,
                              reason=exc.title)
        raise


Caller = Annotated[Principal, Depends(caller)]


def audit(request: Request) -> AuditLog:
    return request.app.state.audit


def authorize(request: Request, principal: Principal, permission: str, team_id: str | None = None) -> None:
    try:
        check(principal, permission)
        if team_id is not None:
            check_team(principal, team_id)
    except SecurityProblem:
        audit(request).record(action=permission, decision="denied", actor=principal.describe(), resource=team_id)
        raise
    audit(request).record(action=permission, decision="allowed", actor=principal.describe(), resource=team_id)
