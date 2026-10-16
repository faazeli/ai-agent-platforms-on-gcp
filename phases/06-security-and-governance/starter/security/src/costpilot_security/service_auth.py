"""Service-to-service authentication with Google-signed ID tokens.

On GKE with Workload Identity, a pod's Kubernetes service account maps to a
Google service account. The pod asks the metadata server for an ID token whose
audience is the service it is about to call, and sends it as a bearer token.
No key file exists anywhere, and tokens expire within the hour.

    http = httpx.AsyncClient(base_url=COST_API_URL, auth=GoogleIdTokenAuth(COST_API_URL))

The receiving service verifies the token with Google's public keys (issuer
https://accounts.google.com, audience = its own URL) using
``costpilot_security.identity.TokenVerifier`` with
jwks_uri="https://www.googleapis.com/oauth2/v3/certs".
"""

from __future__ import annotations

import time

import httpx

GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"


class GoogleIdTokenAuth(httpx.Auth):
    """httpx auth that attaches a cached Google ID token for ``audience``."""

    def __init__(self, audience: str, refresh_margin_seconds: int = 300) -> None:
        self.audience, self.margin = audience, refresh_margin_seconds
        self._token: str | None = None
        self._expires_at = 0.0

    def _fetch(self) -> str:
        import google.auth.transport.requests
        import google.oauth2.id_token
        import jwt

        token = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), self.audience)
        self._expires_at = jwt.decode(token, options={"verify_signature": False})["exp"]
        return token

    def auth_flow(self, request: httpx.Request):
        if not self._token or time.time() > self._expires_at - self.margin:
            self._token = self._fetch()
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request
