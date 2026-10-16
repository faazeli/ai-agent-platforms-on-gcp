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
        start, end = month_bounds(month)
        rows = await self._query(
            f"""
            SELECT * FROM {self._table}
            WHERE ChargePeriodStart >= @start AND ChargePeriodStart < @end
              AND x_TeamId = @team_id
              AND (@service = '' OR ServiceName = @service)
            ORDER BY ChargePeriodStart, ServiceName, ResourceId
            LIMIT @limit OFFSET @offset
            """,
            start=start, end=end, team_id=team_id, service=service or "", limit=limit, offset=offset,
        )
        return [CostRecord.model_validate(r) for r in rows]

    async def team_summary(self, team_id, month, top_n=5):
        start, end = month_bounds(month)
        rows = await self._query(
            f"""
            WITH team_rows AS (
              SELECT ServiceName, EffectiveCost, BilledCost, BillingCurrency
              FROM {self._table}
              WHERE ChargePeriodStart >= @start AND ChargePeriodStart < @end
                AND x_TeamId = @team_id
            )
            SELECT
              (SELECT COUNT(*) FROM team_rows)                AS row_count,
              (SELECT SUM(EffectiveCost) FROM team_rows)      AS total_effective_cost,
              (SELECT SUM(BilledCost) FROM team_rows)         AS total_billed_cost,
              (SELECT ANY_VALUE(BillingCurrency) FROM team_rows) AS currency,
              ARRAY(
                SELECT AS STRUCT ServiceName AS service_name, SUM(EffectiveCost) AS effective_cost
                FROM team_rows GROUP BY ServiceName
                ORDER BY effective_cost DESC LIMIT @top_n
              ) AS top_services
            """,
            start=start, end=end, team_id=team_id, top_n=top_n,
        )
        row = rows[0]
        if not row["row_count"]:
            return None
        return TeamCostSummary(
            team_id=team_id,
            month=month,
            currency=row["currency"],
            total_effective_cost=row["total_effective_cost"],
            total_billed_cost=row["total_billed_cost"],
            top_services=[ServiceCost(**s) for s in row["top_services"]],
        )

    async def top_resources(self, team_id, month, limit):
        start, end = month_bounds(month)
        rows = await self._query(
            f"""
            SELECT ResourceId AS resource_id, ServiceName AS service_name,
                   SUM(EffectiveCost) AS effective_cost
            FROM {self._table}
            WHERE ChargePeriodStart >= @start AND ChargePeriodStart < @end
              AND x_TeamId = @team_id AND ResourceId IS NOT NULL
            GROUP BY resource_id, service_name
            ORDER BY effective_cost DESC
            LIMIT @limit
            """,
            start=start, end=end, team_id=team_id, limit=limit,
        )
        return [ResourceCost(**r) for r in rows]

    async def daily_costs(self, team_id, end, days):
        first = end - timedelta(days=days - 1)
        rows = await self._query(
            f"""
            WITH days AS (SELECT day FROM UNNEST(GENERATE_DATE_ARRAY(@first, @last)) AS day),
            costs AS (
              SELECT DATE(ChargePeriodStart) AS day, SUM(EffectiveCost) AS cost
              FROM {self._table}
              WHERE ChargePeriodStart >= TIMESTAMP(@first)
                AND ChargePeriodStart <  TIMESTAMP(DATE_ADD(@last, INTERVAL 1 DAY))
                AND x_TeamId = @team_id AND ChargeCategory = 'Usage'
              GROUP BY day
            )
            SELECT days.day AS day, IFNULL(costs.cost, 0) AS effective_cost
            FROM days LEFT JOIN costs USING (day)
            ORDER BY day
            """,
            first=first, last=end, team_id=team_id,
        )
        return [DailyCost(day=r["day"], effective_cost=Decimal(r["effective_cost"])) for r in rows]
