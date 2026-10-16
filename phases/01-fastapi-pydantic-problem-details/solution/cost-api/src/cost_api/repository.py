"""Data access behind an interface.

Endpoints depend on the ``CostRepository`` protocol, never on a concrete store.
Phase 1 uses ``InMemoryCostRepository`` (reads the sample CSV). Phase 2 adds a
BigQuery implementation with the same methods, and nothing else changes.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from .models import CostRecord, DailyCost, ResourceCost, ServiceCost, TeamCostSummary


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """'2026-09' -> (2026-09-01T00:00Z, 2026-10-01T00:00Z). Raises ValueError if invalid."""
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


class CostRepository(Protocol):
    async def list_teams(self) -> list[str]: ...

    async def cost_records(
        self, team_id: str, month: str, service: str | None, limit: int, offset: int
    ) -> list[CostRecord]: ...

    async def team_summary(self, team_id: str, month: str, top_n: int = 5) -> TeamCostSummary | None: ...

    async def top_resources(self, team_id: str, month: str, limit: int) -> list[ResourceCost]: ...

    async def daily_costs(self, team_id: str, end: date, days: int) -> list[DailyCost]: ...


class InMemoryCostRepository:
    """Loads the whole CSV into memory. Fine for 3,000 rows; not for production."""

    def __init__(self, records: list[CostRecord]) -> None:
        self._records = records

    @classmethod
    def from_csv(cls, path: Path) -> "InMemoryCostRepository":
        if not path.exists():
            raise FileNotFoundError(
                f"Sample data not found at {path}. Run `python data/generate_sample.py` "
                "from the repo root or set COST_API_SAMPLE_CSV."
            )
        with path.open(newline="") as f:
            return cls([CostRecord.model_validate(row) for row in csv.DictReader(f)])

    def _team_month(self, team_id: str, month: str) -> list[CostRecord]:
        start, end = month_bounds(month)
        return [r for r in self._records
                if r.team_id == team_id and start <= r.charge_period_start < end]

    async def list_teams(self) -> list[str]:
        return sorted({r.team_id for r in self._records if r.team_id})

    async def cost_records(self, team_id, month, service, limit, offset):
        rows = [r for r in self._team_month(team_id, month) if service is None or r.service_name == service]
        rows.sort(key=lambda r: (r.charge_period_start, r.service_name, r.resource_id or ""))
        return rows[offset: offset + limit]

    async def team_summary(self, team_id, month, top_n=5):
        rows = self._team_month(team_id, month)
        if not rows:
            return None
        by_service: dict[str, Decimal] = defaultdict(Decimal)
        for r in rows:
            by_service[r.service_name] += r.effective_cost
        top = sorted(by_service.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        return TeamCostSummary(
            team_id=team_id,
            month=month,
            currency=rows[0].billing_currency,
            total_effective_cost=sum((r.effective_cost for r in rows), Decimal(0)),
            total_billed_cost=sum((r.billed_cost for r in rows), Decimal(0)),
            top_services=[ServiceCost(service_name=s, effective_cost=c) for s, c in top],
        )

    async def top_resources(self, team_id, month, limit):
        totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for r in self._team_month(team_id, month):
            if r.resource_id:
                totals[(r.resource_id, r.service_name)] += r.effective_cost
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [ResourceCost(resource_id=rid, service_name=svc, effective_cost=cost)
                for (rid, svc), cost in ranked]

    async def daily_costs(self, team_id, end, days):
        first = end - timedelta(days=days - 1)
        totals: dict[date, Decimal] = {first + timedelta(days=i): Decimal(0) for i in range(days)}
        for r in self._records:
            day = r.charge_period_start.date()
            if r.team_id == team_id and r.charge_category == "Usage" and first <= day <= end:
                totals[day] += r.effective_cost
        return [DailyCost(day=d, effective_cost=c) for d, c in sorted(totals.items())]
