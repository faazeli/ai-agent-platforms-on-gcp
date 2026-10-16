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
    # TODO Lab 6.2: turn credentials into a Principal.
    #   1. No bearer -> SecurityProblem(401, "unauthorized", ...).
    #   2. Peek at the unverified "iss" (jwt.decode(..., options={"verify_signature": False}));
    #      a malformed token must become a 401, not a crash.
    #   3. Issuer == workload_verifier.issuer -> verify with workload_verifier.
    #      - No delegation header: return a Principal(kind="workload", role="workload").
    #      - Delegation from a workload NOT in trusted_delegators -> 403.
    #      - Otherwise decode the base64 JSON user and return it with via=<workload email>.
    #   4. Any other issuer: a delegation header is a 403 (users can't delegate);
    #      else return principal_from_claims(user_verifier.verify(bearer)).
    raise NotImplementedError
