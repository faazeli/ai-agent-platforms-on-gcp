"""MCP server tests using FastMCP's in-memory Client: no network, no ports.

Unit tests fake cost-api with httpx.MockTransport. The integration test at the
bottom runs the real Phase 1 cost-api in-process (via ASGI) when it's available.
"""

import json
import sys
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from mcp_finops.cost_api_client import CostApiClient
from mcp_finops.server import build_server

SUMMARY = {
    "team_id": "payments", "month": "2026-09", "currency": "USD",
    "total_effective_cost": "1000.5000", "total_billed_cost": "1100.0000",
    "top_services": [{"service_name": "Cloud Run", "effective_cost": "1000.5000"}],
}
NOT_FOUND = {"type": "https://example.com/problems/team-not-found", "title": "Unknown team", "status": 404,
             "detail": "No cost data exists for team 'marketing'.", "instance": "/v1/teams/marketing/summary"}


def fake_cost_api(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/v1/teams":
        return httpx.Response(200, json=[{"team_id": "payments"}, {"team_id": "search"}])
    if path == "/v1/teams/payments/summary":
        return httpx.Response(200, json=SUMMARY)
    if path.startswith("/v1/teams/marketing"):
        return httpx.Response(404, json=NOT_FOUND, headers={"content-type": "application/problem+json"})
    if path == "/v1/teams/payments/resources":
        limit = int(request.url.params["limit"])
        rows = [{"resource_id": f"r{i}", "service_name": "Cloud Run", "effective_cost": str(100 - i)}
                for i in range(limit)]
        return httpx.Response(200, json=rows)
    return httpx.Response(500, text="boom")


def server_with(handler):
    http = httpx.AsyncClient(base_url="http://cost-api", transport=httpx.MockTransport(handler))
    return build_server(CostApiClient(http))


@pytest.fixture
def mcp():
    return server_with(fake_cost_api)


async def test_tools_are_listed_read_only_with_output_schemas(mcp):
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) == {"list_teams", "get_team_cost", "top_resources", "detect_anomalies"}
    for tool in tools.values():
        assert tool.annotations.readOnlyHint is True
        assert tool.outputSchema is not None, f"{tool.name} has no output schema"
        assert len(tool.description) > 40, f"{tool.name} needs a description a model can use"


async def test_get_team_cost_returns_structured_content(mcp):
    async with Client(mcp) as client:
        result = await client.call_tool("get_team_cost", {"team_id": "payments", "month": "2026-09"})
    assert result.structured_content["total_effective_cost"] == "1000.5000"
    assert result.data.top_services[0].service_name == "Cloud Run"


async def test_bad_arguments_are_rejected_before_any_call(mcp):
    async with Client(mcp) as client:
        bad_month = await client.call_tool("get_team_cost", {"team_id": "payments", "month": "Sept"},
                                           raise_on_error=False)
        too_many = await client.call_tool("top_resources", {"team_id": "payments", "month": "2026-09",
                                                            "limit": 500}, raise_on_error=False)
        injected = await client.call_tool("get_team_cost", {"team_id": "payments/../../admin",
                                                            "month": "2026-09"}, raise_on_error=False)
    assert bad_month.is_error and too_many.is_error and injected.is_error


async def test_upstream_problem_becomes_tool_error_with_hint(mcp):
    async with Client(mcp) as client:
        result = await client.call_tool("get_team_cost", {"team_id": "marketing", "month": "2026-09"},
                                        raise_on_error=False)
    assert result.is_error
    problem = json.loads(result.content[0].text)
    assert problem["type"].endswith("/team-not-found") and problem["status"] == 404
    assert "list_teams" in problem["hint"]


async def test_upstream_down_is_reported_not_crashed():
    def down(request):
        raise httpx.ConnectError("refused")

    async with Client(server_with(down)) as client:
        result = await client.call_tool("list_teams", {}, raise_on_error=False)
    problem = json.loads(result.content[0].text)
    assert problem["status"] == 503 and "do not retry" in problem["hint"]


async def test_non_json_upstream_errors_do_not_leak(mcp):
    async with Client(mcp) as client:
        result = await client.call_tool("detect_anomalies", {"team_id": "payments", "end_date": "2026-09-30"},
                                        raise_on_error=False)
    assert result.is_error and "boom" not in result.content[0].text


async def test_resource_and_prompt_are_published(mcp):
    async with Client(mcp) as client:
        glossary = await client.read_resource("focus://glossary")
        prompt = await client.get_prompt("monthly_review", {"team_id": "payments", "month": "2026-09"})
    assert "EffectiveCost" in glossary[0].text
    assert "get_team_cost" in prompt.messages[0].content.text


# ---------------------------------------------------------------- integration
PHASE1_SRC = Path(__file__).resolve().parents[4] / "01-fastapi-pydantic-problem-details/solution/cost-api/src"


@pytest.fixture
def real_cost_api_server():
    if not PHASE1_SRC.exists():
        pytest.skip("Phase 1 solution not found next to this phase")
    sys.path.insert(0, str(PHASE1_SRC))
    from cost_api.main import create_app
    from cost_api.repository import InMemoryCostRepository
    from cost_api.settings import Settings

    settings = Settings()
    app = create_app(settings)
    app.state.repository = InMemoryCostRepository.from_csv(settings.sample_csv)
    http = httpx.AsyncClient(base_url="http://cost-api", transport=httpx.ASGITransport(app=app))
    return build_server(CostApiClient(http))


async def test_finds_the_planted_anomaly_end_to_end(real_cost_api_server):
    async with Client(real_cost_api_server) as client:
        result = await client.call_tool("detect_anomalies",
                                        {"team_id": "ml-research", "end_date": "2026-09-30", "days": 30})
    days = [a["day"] for a in result.structured_content["anomalies"]]
    assert days[0] == "2026-09-18"
