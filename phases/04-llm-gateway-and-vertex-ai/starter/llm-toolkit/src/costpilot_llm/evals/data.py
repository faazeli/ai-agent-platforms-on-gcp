"""Facts computed straight from the sample CSV: the ground truth for evals.

Everything here uses only the standard library and exact Decimal arithmetic, so
expected answers never depend on a model, a database or rounding luck.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

SAMPLE_RELATIVE = Path("data/sample/focus_costs.csv")


def find_sample_csv() -> Path:
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for folder in (start, *start.parents):
            if (folder / SAMPLE_RELATIVE).exists():
                return folder / SAMPLE_RELATIVE
    raise FileNotFoundError("Run `python data/generate_sample.py` from the course repo root first.")


@dataclass
class TeamMonth:
    effective: Decimal = Decimal(0)
    billed: Decimal = Decimal(0)
    by_service: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))


@dataclass
class Facts:
    currency: str
    team_month: dict[tuple[str, str], TeamMonth]
    untagged: dict[str, Decimal]
    daily: dict[tuple[str, date], Decimal]  # usage only

    @property
    def teams(self) -> list[str]:
        return sorted({t for t, _ in self.team_month})

    @property
    def months(self) -> list[str]:
        return sorted({m for _, m in self.team_month})


def load_facts(path: Path | None = None) -> Facts:
    path = path or find_sample_csv()
    team_month: dict[tuple[str, str], TeamMonth] = defaultdict(TeamMonth)
    untagged: dict[str, Decimal] = defaultdict(Decimal)
    daily: dict[tuple[str, date], Decimal] = defaultdict(Decimal)
    currency = "USD"
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            month = row["ChargePeriodStart"][:7]
            effective, billed = Decimal(row["EffectiveCost"]), Decimal(row["BilledCost"])
            currency = row["BillingCurrency"]
            team = row["x_TeamId"]
            if not team:
                untagged[month] += effective
                continue
            tm = team_month[(team, month)]
            tm.effective += effective
            tm.billed += billed
            tm.by_service[row["ServiceName"]] += effective
            if row["ChargeCategory"] == "Usage":
                daily[(team, date.fromisoformat(row["ChargePeriodStart"][:10]))] += effective
    return Facts(currency, dict(team_month), dict(untagged), dict(daily))


def build_context(facts: Facts, daily_month: str | None = None) -> dict:
    """The data an LLM sees in Phase 4's context-only evals (Phase 5 agents use tools instead)."""
    daily_month = daily_month or facts.months[-1]
    year, mon = map(int, daily_month.split("-"))
    first = date(year, mon, 1)
    days = [first + timedelta(days=i) for i in range(31) if (first + timedelta(days=i)).month == mon]
    return {
        "currency": facts.currency,
        "team_months": [
            {"team": team, "month": month,
             "effective": str(round(tm.effective, 2)), "billed": str(round(tm.billed, 2)),
             "by_service": {s: str(round(c, 2)) for s, c in sorted(tm.by_service.items(), key=lambda kv: -kv[1])}}
            for (team, month), tm in sorted(facts.team_month.items())
        ],
        "untagged": {m: str(round(c, 2)) for m, c in sorted(facts.untagged.items())},
        f"daily_usage_{daily_month}": {
            team: {d.isoformat(): str(round(facts.daily.get((team, d), Decimal(0)), 2)) for d in days}
            for team in facts.teams
        },
    }
