"""CostRepository backed by BigQuery.

Same methods as InMemoryCostRepository, so cost-api's endpoints do not change.
Rules this file follows, which you should keep in your own version:

1. Every query filters on ChargePeriodStart (the partition column). The table
   enforces this with require_partition_filter, so a missing filter fails fast.
2. Every value from a request is a query *parameter*, never string formatting.
   This is your SQL-injection defense, and later your prompt-injection defense
   when an agent supplies the arguments.
3. Every job sets maximum_bytes_billed, a hard ceiling on what one query may
   cost. A bad query fails instead of quietly scanning terabytes.
4. Aggregation happens in BigQuery, not in Python. Only small results travel.
5. The BigQuery client is synchronous, so calls run in a worker thread to keep
   the event loop free.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .models import CostRecord, DailyCost, ResourceCost, ServiceCost, TeamCostSummary
from .repository import month_bounds
from .settings import Settings

try:  # imported lazily so Phase 1 installs don't need the BigQuery client
    from google.cloud import bigquery
except ImportError:  # pragma: no cover
    bigquery = None  # type: ignore[assignment]


def _param(name: str, value: Any) -> Any:
    kind = {str: "STRING", int: "INT64", date: "DATE"}.get(type(value))
    if kind is None:
        kind = "TIMESTAMP"  # datetimes
    return bigquery.ScalarQueryParameter(name, kind, value)


class BigQueryCostRepository:
    def __init__(self, client: Any, table: str, dim_team_table: str, max_bytes_billed: int) -> None:
        self._client = client
        self._table = table
        self._dim_team = dim_team_table
        self._max_bytes = max_bytes_billed

    @classmethod
    def from_settings(cls, settings: Settings) -> "BigQueryCostRepository":
        if bigquery is None:
            raise RuntimeError("Install the BigQuery extra: pip install -e '.[bigquery]'")
        client = bigquery.Client(project=settings.gcp_project)  # uses Application Default Credentials
        project = settings.gcp_project or client.project
        return cls(
            client,
            table=f"`{project}.{settings.bq_dataset}.{settings.bq_table}`",
            dim_team_table=f"`{project}.{settings.bq_dataset}.dim_team`",
            max_bytes_billed=settings.bq_max_bytes_billed,
        )

    async def _query(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        config = bigquery.QueryJobConfig(
            query_parameters=[_param(k, v) for k, v in params.items()],
            maximum_bytes_billed=self._max_bytes,
            labels={"service": "cost-api", "team": "finops"},  # shows up in your own FOCUS data
        )

        def run() -> list[dict[str, Any]]:
            return [dict(row.items()) for row in self._client.query(sql, job_config=config).result()]

        return await asyncio.to_thread(run)

    async def list_teams(self) -> list[str]:
        rows = await self._query(f"SELECT team_id FROM {self._dim_team} ORDER BY team_id")
        return [r["team_id"] for r in rows]

    async def cost_records(self, team_id, month, service, limit, offset):
        # TODO Lab 2.6 (a): SELECT * for one team and month, optional service filter,
        #   ordered, with LIMIT/OFFSET. Filter on ChargePeriodStart >= @start AND < @end
        #   (use month_bounds). Pass every value as a parameter: self._query(sql, team_id=..., ...).
        #   Tip: pass service="" when it's None and test `(@service = '' OR ServiceName = @service)`.
        #   Validate each row with CostRecord.model_validate(row).
        raise NotImplementedError

    async def team_summary(self, team_id, month, top_n=5):
        # TODO Lab 2.6 (b): ONE query that returns row_count, total_effective_cost,
        #   total_billed_cost, currency and an ARRAY of STRUCT(service_name, effective_cost)
        #   for the top_n services. Return None when row_count is 0.
        #   Hint: a CTE `team_rows`, scalar subqueries, and ARRAY(SELECT AS STRUCT ...).
        raise NotImplementedError

    async def top_resources(self, team_id, month, limit):
        # TODO Lab 2.6 (c): GROUP BY ResourceId, ServiceName; skip NULL ResourceId;
        #   alias columns to resource_id/service_name/effective_cost so ResourceCost(**row) works.
        raise NotImplementedError

    async def daily_costs(self, team_id, end, days):
        # TODO Lab 2.6 (d): zero-filled daily series. Build the calendar with
        #   UNNEST(GENERATE_DATE_ARRAY(@first, @last)) and LEFT JOIN the daily sums.
        #   Count only ChargeCategory = 'Usage'.
        raise NotImplementedError
