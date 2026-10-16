from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from cost_api.main import create_app
from cost_api.settings import Settings

PROBLEM = "application/problem+json"


@pytest.fixture(scope="module")
def client():
    app = create_app(Settings())
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def assert_problem(response, status: int, slug: str):
    assert response.status_code == status
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert body["status"] == status
    assert body["type"].endswith(f"/{slug}")
    assert {"type", "title", "status", "detail", "instance"} <= body.keys()
    return body


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_lists_teams(client):
    teams = [t["team_id"] for t in client.get("/v1/teams").json()]
    assert teams == ["data-platform", "ml-research", "payments", "search"]


def test_summary_totals_add_up(client):
    body = client.get("/v1/teams/payments/summary", params={"month": "2026-09"}).json()
    assert body["currency"] == "USD"
    assert len(body["top_services"]) <= 5
    services_total = sum(Decimal(s["effective_cost"]) for s in body["top_services"])
    assert services_total == Decimal(body["total_effective_cost"])  # payments uses 4 services


def test_commitment_makes_billed_and_effective_differ(client):
    body = client.get("/v1/teams/payments/summary", params={"month": "2026-09"}).json()
    # The CUD purchase is billed up front; usage it covers is amortized into EffectiveCost.
    assert Decimal(body["total_billed_cost"]) != Decimal(body["total_effective_cost"])


def test_costs_are_paginated(client):
    first = client.get("/v1/teams/search/costs", params={"month": "2026-09", "limit": 50}).json()
    assert len(first["items"]) == 50 and first["next_offset"] == 50
    second = client.get("/v1/teams/search/costs",
                        params={"month": "2026-09", "limit": 50, "offset": 50}).json()
    assert first["items"][0] != second["items"][0]


def test_costs_filter_by_service(client):
    body = client.get("/v1/teams/search/costs",
                      params={"month": "2026-09", "service": "BigQuery", "limit": 1000}).json()
    assert body["items"] and {i["service_name"] for i in body["items"]} == {"BigQuery"}


def test_top_resources_sorted_desc(client):
    body = client.get("/v1/teams/data-platform/resources", params={"month": "2026-08", "limit": 3}).json()
    costs = [Decimal(r["effective_cost"]) for r in body]
    assert len(body) == 3 and costs == sorted(costs, reverse=True)


def test_daily_series_shows_the_planted_anomaly(client):
    body = client.get("/v1/teams/ml-research/daily", params={"end": "2026-09-20", "days": 7}).json()
    peak = max(body, key=lambda d: Decimal(d["effective_cost"]))
    assert peak["day"] == "2026-09-18"


def test_unknown_team_is_a_problem(client):
    body = assert_problem(client.get("/v1/teams/marketing/summary", params={"month": "2026-09"}),
                          404, "team-not-found")
    assert body["instance"] == "/v1/teams/marketing/summary"


def test_bad_month_lists_invalid_params(client):
    body = assert_problem(client.get("/v1/teams/payments/summary", params={"month": "2026-13"}),
                          422, "invalid-request")
    assert body["invalid_params"][0]["name"] == "month"


def test_limit_is_capped(client):
    assert_problem(client.get("/v1/teams/payments/resources", params={"month": "2026-09", "limit": 500}),
                   422, "invalid-request")


def test_period_without_data(client):
    assert_problem(client.get("/v1/teams/payments/summary", params={"month": "2025-01"}),
                   404, "no-cost-data")


def test_unknown_route_is_still_problem_json(client):
    assert_problem(client.get("/v2/nope"), 404, "not-found")


def test_unexpected_errors_hide_internals():
    class Exploding:
        async def list_teams(self):
            raise RuntimeError("SELECT * FROM secrets")

    with TestClient(create_app(Settings(), repository=Exploding()), raise_server_exceptions=False) as c:
        body = assert_problem(c.get("/v1/teams"), 500, "internal-error")
    assert "SELECT" not in body["detail"] and len(body["trace_id"]) == 32


def test_openapi_documents_the_contract(client):
    spec = client.get("/openapi.json").json()
    assert "/v1/teams/{team_id}/summary" in spec["paths"]
