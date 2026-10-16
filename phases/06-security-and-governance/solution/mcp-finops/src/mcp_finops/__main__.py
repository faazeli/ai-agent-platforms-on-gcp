"""Run the MCP server over Streamable HTTP:  python -m mcp_finops
The MCP endpoint is http://HOST:PORT/mcp

With auth on (the default), clients must present an OIDC access token minted for
this server (audience MCP_FINOPS_OIDC_AUDIENCE), and calls to cost-api carry this
workload's own Google ID token plus a delegation header.
"""

import logging

import httpx
from fastmcp.server.auth.providers.jwt import JWTVerifier

from costpilot_security.service_auth import GoogleIdTokenAuth

from .cost_api_client import CostApiClient
from .server import build_server
from .settings import Settings


def main() -> None:
    settings = Settings()
    auth, upstream_auth = None, None
    if settings.auth_enabled:
        if not settings.oidc_jwks_uri:
            raise SystemExit("Set MCP_FINOPS_OIDC_JWKS_URI, or MCP_FINOPS_AUTH_ENABLED=false for local development.")
        auth = JWTVerifier(jwks_uri=settings.oidc_jwks_uri, issuer=settings.oidc_issuer,
                           audience=settings.oidc_audience)
        upstream_auth = GoogleIdTokenAuth(settings.cost_api_audience)
    else:
        logging.warning("AUTH DISABLED for mcp-finops. Never do this outside local development.")
    http = httpx.AsyncClient(base_url=settings.cost_api_url, timeout=settings.cost_api_timeout_seconds,
                             auth=upstream_auth)
    server = build_server(CostApiClient(http, settings.problem_base_url), auth=auth)
    server.run(transport="http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
