"""Offline tests for the BigQuery repository.

A fake client records every query and returns canned rows, so these tests run
without a GCP project. They check the rules that matter most: partition filters,
parameters instead of string formatting, and a bytes-billed ceiling. Run the
real thing against BigQuery with scripts/load_sample.sh + the Lab 2.6 checks.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip("google.cloud.bigquery")

from cost_api.bigquery_repository import BigQueryCostRepository  # noqa: E402


class FakeJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def query(self, sql, job_config):
        self.calls.append((sql, job_config))
        return FakeJob(self.responses.pop(0))


def repo_with(*responses):
    client = FakeClient(responses)
    return BigQueryCostRepository(client, "`p.finops.focus_costs`", "`p.finops.dim_team`", 10**9), client


def params(job_config):
    return {p.name: p.value for p in job_config.query_parameters}


async def test_summary_maps_rows_and_filters_on_partition():
    repo, client = repo_with([{
        "row_count": 120, "total_effective_cost": Decimal("1000.50"), "total_billed_cost": Decimal("1200"),
        "currency": "USD",
        "top_services": [{"service_name": "BigQuery", "effective_cost": Decimal("600.25")},
                         {"service_name": "Cloud Run", "effective_cost": Decimal("400.25")}],
    }])
    summary = await repo.team_summary("payments", "2026-09")
    assert summary.total_effective_cost == Decimal("1000.50")
    assert [s.service_name for s in summary.top_services] == ["BigQuery", "Cloud Run"]

    sql, config = client.calls[0]
    assert "ChargePeriodStart >= @start" in sql and "ChargePeriodStart < @end" in sql
    p = params(config)
    assert p["start"] == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert p["end"] == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert config.maximum_bytes_billed == 10**9


async def test_summary_returns_none_without_rows():
    repo, _ = repo_with([{"row_count": 0, "total_effective_cost": None, "total_billed_cost": None,
                          "currency": None, "top_services": []}])
    assert await repo.team_summary("payments", "2025-01") is None


async def test_request_values_are_parameters_never_sql_text():
    hostile = "x' OR '1'='1"
    repo, client = repo_with([], [], [])
    await repo.cost_records(hostile, "2026-09", None, 10, 0)
    await repo.top_resources(hostile, "2026-09", 5)
    await repo.daily_costs(hostile, date(2026, 9, 30), 7)
    for sql, config in client.calls:
        assert hostile not in sql
        assert params(config)["team_id"] == hostile


async def test_every_fact_query_has_a_partition_filter():
    repo, client = repo_with([], [], [])
    await repo.cost_records("payments", "2026-09", "BigQuery", 10, 0)
    await repo.top_resources("payments", "2026-09", 5)
    await repo.daily_costs("payments", date(2026, 9, 30), 7)
    for sql, _ in client.calls:
        assert "ChargePeriodStart >=" in sql and "ChargePeriodStart <" in sql


async def test_daily_costs_window():
    repo, client = repo_with([{"day": date(2026, 9, 29), "effective_cost": Decimal("1")},
                              {"day": date(2026, 9, 30), "effective_cost": 0}])
    out = await repo.daily_costs("payments", date(2026, 9, 30), 2)
    assert [d.effective_cost for d in out] == [Decimal("1"), Decimal("0")]
    assert params(client.calls[0][1])["first"] == date(2026, 9, 29)


async def test_cost_records_validate_through_the_phase1_model():
    row = {"BillingAccountId": "A", "ServiceName": "BigQuery", "ChargeCategory": "Usage",
           "ChargePeriodStart": datetime(2026, 9, 1, tzinfo=timezone.utc),
           "ChargePeriodEnd": datetime(2026, 9, 2, tzinfo=timezone.utc),
           "BilledCost": Decimal("1"), "EffectiveCost": Decimal("1"), "BillingCurrency": "USD",
           "Tags": {"team": "payments"}, "x_TeamId": "payments"}
    repo, client = repo_with([row])
    records = await repo.cost_records("payments", "2026-09", "BigQuery", 10, 0)
    assert records[0].tags == {"team": "payments"}
    assert params(client.calls[0][1])["service"] == "BigQuery"


async def test_same_interface_as_in_memory_repository():
    from cost_api.repository import InMemoryCostRepository

    def public(cls):
        return {n for n in vars(cls) if not n.startswith("_") and callable(getattr(cls, n))}

    assert public(InMemoryCostRepository) - {"from_csv"} <= public(BigQueryCostRepository)
