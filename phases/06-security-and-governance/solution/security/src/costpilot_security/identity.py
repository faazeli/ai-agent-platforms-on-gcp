"""Who is calling? Zero Trust means every request proves it, every time.

Two kinds of callers reach cost-api:

1. **Users**, with an OIDC access token from your identity provider
   (audience = cost-api). Their roles and teams come from token claims.
2. **Workloads**, with a Google-signed ID token for their service account
   (audience = cost-api's URL). On GKE they get it through Workload Identity,
   so no key files exist anywhere.

The MCP server is a workload acting *for* a user. The MCP authorization spec
forbids passing the user's token through to upstream APIs, so instead the MCP
server authenticates as itself and states whom it acts for in a delegation
header. cost-api honours that header only from workloads on an explicit
allow-list. (OAuth 2.0 Token Exchange, RFC 8693, is the heavier-weight
standard for the same problem; see the README.)
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

import jwt

from .problems import SecurityProblem

DELEGATION_HEADER = "X-Costpilot-On-Behalf-Of"


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str | None = None
    role: str = "viewer"
    teams: frozenset[str] = field(default_factory=frozenset)
    kind: str = "user"                    # "user" or "workload"
    via: str | None = None                # the workload that delegated, if any

    def describe(self) -> dict[str, Any]:
        return {"subject": self.subject, "email": self.email, "role": self.role,
                "teams": sorted(self.teams), "kind": self.kind, "via": self.via}


class TokenVerifier:
    """Verifies RS256 JWTs: signature (via JWKS or a static key), issuer, audience, expiry."""

    def __init__(self, *, issuer: str, audience: str, jwks_uri: str | None = None,
                 public_key: Any | None = None, leeway_seconds: int = 30) -> None:
        if not (jwks_uri or public_key):
            raise ValueError("Provide jwks_uri (production) or public_key (tests)")
        self.issuer, self.audience, self.leeway = issuer, audience, leeway_seconds
        self._public_key = public_key
        self._jwks = jwt.PyJWKClient(jwks_uri, cache_keys=True) if jwks_uri else None

    def verify(self, token: str) -> dict[str, Any]:
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key if self._jwks else self._public_key
            return jwt.decode(token, key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer,
                              leeway=self.leeway, options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        except jwt.ExpiredSignatureError as exc:
            raise SecurityProblem(401, "unauthorized", "Token expired", "The access token has expired.") from exc
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
            # Don't echo why in detail: it helps attackers more than callers.
            raise SecurityProblem(401, "unauthorized", "Invalid token",
                                  "The access token could not be verified.") from exc


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    teams = claims.get("teams") or []
    return Principal(subject=claims["sub"], email=claims.get("email"), role=claims.get("role", "viewer"),
                     teams=frozenset(teams if isinstance(teams, list) else [teams]))


def encode_delegation(user: Principal) -> str:
    payload = {"sub": user.subject, "email": user.email, "role": user.role, "teams": sorted(user.teams)}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def resolve_principal(
    bearer: str | None,
    delegation: str | None,
    *,
    user_verifier: TokenVerifier,
    workload_verifier: TokenVerifier | None,
    trusted_delegators: frozenset[str],
) -> Principal:
    """Turn the request's credentials into the principal that RBAC will judge."""
    if not bearer:
        raise SecurityProblem(401, "unauthorized", "Authentication required", "Send a bearer token.")

    try:
        # Peek at the issuer only to pick a verifier; the chosen verifier checks everything.
        unverified_issuer = jwt.decode(bearer, options={"verify_signature": False}).get("iss")
    except jwt.InvalidTokenError as exc:
        raise SecurityProblem(401, "unauthorized", "Invalid token",
                              "The access token could not be verified.") from exc
    if workload_verifier and unverified_issuer == workload_verifier.issuer:
        claims = workload_verifier.verify(bearer)  # the issuer was only a hint; this verifies everything
        workload = claims.get("email") or claims["sub"]
        if not delegation:
            return Principal(subject=workload, email=claims.get("email"), role="workload", kind="workload")
        if workload not in trusted_delegators:
            raise SecurityProblem(403, "forbidden", "Delegation not allowed",
                                  "This workload may not act on behalf of users.")
        try:
            user = json.loads(base64.urlsafe_b64decode(delegation.encode()))
        except (ValueError, json.JSONDecodeError) as exc:
            raise SecurityProblem(401, "unauthorized", "Bad delegation header", "Malformed delegation.") from exc
        return Principal(subject=user["sub"], email=user.get("email"), role=user.get("role", "viewer"),
                         teams=frozenset(user.get("teams", [])), kind="user", via=workload)

    if delegation:
        raise SecurityProblem(403, "forbidden", "Delegation not allowed", "Only workloads may delegate.")
    return principal_from_claims(user_verifier.verify(bearer))
