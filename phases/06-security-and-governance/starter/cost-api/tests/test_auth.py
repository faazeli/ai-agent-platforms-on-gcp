"""cost-api with Zero Trust on: real RS256 tokens, RBAC, team scope, delegation, audit."""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cost_api.main import create_app
from cost_api.security import SecurityContext
from cost_api.settings import Settings
from costpilot_security.audit import AuditLog, verify_chain
from costpilot_security.identity import Principal, TokenVerifier, encode_delegation

IDP, GOOGLE = "https://idp.example.com", "https://accounts.google.com"
USER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
MCP_SA = "mcp-finops@demo.iam.gserviceaccount.com"
SEPT = {"month": "2026-09"}


def token(key, iss, aud, sub, **claims):
    now = int(time.time())
    return jwt.encode({"iss": iss, "aud": aud, "sub": sub, "iat": now, "exp": now + 300, **claims}, key, "RS256")


def user(role, teams=()):
    return {"Authorization": "Bearer " + token(USER_KEY, IDP, "cost-api", f"{role}-1", role=role, teams=list(teams))}


@pytest.fixture
def secured():
    settings = Settings(auth_enabled=True, oidc_jwks_uri="https://idp.example.com/jwks")
    app = create_app(settings)
    # Swap the JWKS-backed verifiers for static test keys.
    app.state.security = SecurityContext(
        users=TokenVerifier(issuer=IDP, audience="cost-api", public_key=USER_KEY.public_key()),
        workloads=TokenVerifier(issuer=GOOGLE, audience=settings.workload_audience,
                                public_key=GOOGLE_KEY.public_key()),
        trusted_delegators=frozenset({MCP_SA}),
    )
    lines = []
    app.state.audit = AuditLog("test", sink=lines.append)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.audit_lines = lines
        yield client


def test_no_token_is_401_problem_with_challenge(secured):
    r = secured.get("/v1/teams")
    assert r.status_code == 401 and r.headers["content-type"].startswith("application/problem+json")
    assert r.headers["www-authenticate"].startswith("Bearer")


def test_viewer_reads_own_team_only(secured):
    viewer = user("viewer", ["payments"])
    assert secured.get("/v1/teams/payments/summary", params=SEPT, headers=viewer).status_code == 200
    denied = secured.get("/v1/teams/search/summary", params=SEPT, headers=viewer)
    assert denied.status_code == 403 and denied.json()["type"].endswith("/forbidden")


def test_outsiders_cannot_probe_which_teams_exist(secured):
    viewer = user("viewer", ["payments"])
    # 403 for a real team and a made-up one alike: no existence oracle.
    assert secured.get("/v1/teams/search/summary", params=SEPT, headers=viewer).status_code == 403
    assert secured.get("/v1/teams/marketing/summary", params=SEPT, headers=viewer).status_code == 403


def test_team_list_is_filtered_by_scope(secured):
    assert [t["team_id"] for t in secured.get("/v1/teams", headers=user("viewer", ["search"])).json()] == ["search"]
    assert len(secured.get("/v1/teams", headers=user("finops_admin")).json()) == 4


def test_trusted_mcp_server_acts_for_a_user(secured):
    headers = {
        "Authorization": "Bearer " + token(GOOGLE_KEY, GOOGLE, "https://cost-api.internal", "123", email=MCP_SA),
        "X-Costpilot-On-Behalf-Of": encode_delegation(Principal("ana", role="viewer", teams=frozenset({"payments"}))),
    }
    assert secured.get("/v1/teams/payments/summary", params=SEPT, headers=headers).status_code == 200
    assert secured.get("/v1/teams/search/summary", params=SEPT, headers=headers).status_code == 403


def test_every_decision_is_audited_in_an_intact_chain(secured):
    secured.get("/v1/teams/payments/summary", params=SEPT, headers=user("viewer", ["payments"]))
    secured.get("/v1/teams/search/summary", params=SEPT, headers=user("viewer", ["payments"]))
    secured.get("/v1/teams")
    decisions = [(json.loads(line)["action"], json.loads(line)["decision"]) for line in secured.audit_lines]
    assert decisions == [("costs:read", "allowed"), ("costs:read", "denied"), ("authenticate", "denied")]
    assert verify_chain(secured.audit_lines)["ok"]


def test_trusted_delegators_come_from_a_comma_list(monkeypatch):
    monkeypatch.setenv("COST_API_TRUSTED_DELEGATORS", "a@p.iam.gserviceaccount.com, b@p.iam.gserviceaccount.com")
    assert Settings().trusted_delegators == ["a@p.iam.gserviceaccount.com", "b@p.iam.gserviceaccount.com"]


def test_auth_cannot_be_half_configured():
    with pytest.raises(RuntimeError, match="JWKS"):
        create_app(Settings(auth_enabled=True, oidc_jwks_uri=None))
