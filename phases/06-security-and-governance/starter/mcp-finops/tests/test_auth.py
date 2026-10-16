"""mcp-finops with auth: the user's identity is checked here (layer 2) and passed
to cost-api as a delegation, never as the user's own token."""

import json

import httpx
import pytest
from fastmcp import Client
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair

import mcp_finops.server as server_module
from costpilot_security.identity import DELEGATION_HEADER
from mcp_finops.cost_api_client import CostApiClient
from mcp_finops.server import build_server

SUMMARY = {"team_id": "payments", "month": "2026-09", "currency": "USD", "total_effective_cost": "1",
           "total_billed_cost": "1", "top_services": []}


@pytest.fixture
def upstream():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=SUMMARY)

    http = httpx.AsyncClient(base_url="http://cost-api", transport=httpx.MockTransport(handler),
                             headers={"Authorization": "Bearer workload-id-token"})
    return build_server(CostApiClient(http)), seen


def signed_in_as(monkeypatch, **claims):
    token = AccessToken(token="user-token-for-mcp", client_id="chat-app", scopes=[], claims=claims)
    monkeypatch.setattr(server_module, "get_access_token", lambda: token)


async def test_forbidden_team_is_refused_before_calling_upstream(upstream, monkeypatch):
    mcp, seen = upstream
    signed_in_as(monkeypatch, sub="ana", role="viewer", teams=["payments"])
    async with Client(mcp) as client:
        result = await client.call_tool("get_team_cost", {"team_id": "search", "month": "2026-09"},
                                        raise_on_error=False)
    assert result.is_error and json.loads(result.content[0].text)["status"] == 403
    assert seen == []  # cost-api never saw the request


async def test_upstream_call_carries_delegation_not_the_user_token(upstream, monkeypatch):
    mcp, seen = upstream
    signed_in_as(monkeypatch, sub="ana", role="viewer", teams=["payments"])
    async with Client(mcp) as client:
        await client.call_tool("get_team_cost", {"team_id": "payments", "month": "2026-09"})
    request = seen[0]
    assert request.headers["Authorization"] == "Bearer workload-id-token"   # our own identity
    assert "user-token-for-mcp" not in str(request.headers)                 # no token passthrough
    assert DELEGATION_HEADER.lower() in {k.lower() for k in request.headers}


async def test_jwt_verifier_accepts_only_tokens_minted_for_this_server():
    keys = RSAKeyPair.generate()
    verifier = JWTVerifier(public_key=keys.public_key, issuer="https://idp.example.com", audience="mcp-finops")
    good = keys.create_token(subject="ana", issuer="https://idp.example.com", audience="mcp-finops")
    for_cost_api = keys.create_token(subject="ana", issuer="https://idp.example.com", audience="cost-api")
    assert (await verifier.verify_token(good)) is not None
    assert (await verifier.verify_token(for_cost_api)) is None  # a cost-api token can't be replayed here
