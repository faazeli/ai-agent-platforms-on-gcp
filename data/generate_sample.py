"""Generate a deterministic, synthetic FOCUS-shaped cost dataset for the course.

The data is fake but realistic enough to teach with:

* 4 teams, ~6 GCP services, 2 resources per team/service, daily rows for Q3 2026.
* Commitment coverage on the payments team's Compute Engine: those usage rows have
  BilledCost = 0 but EffectiveCost > 0, and a monthly Purchase row carries the bill.
  Utilization is ~88%, so the team is billed more than its effective cost: that gap
  is unused commitment, a classic FinOps finding.
  This is the clearest way to learn why EffectiveCost (amortized) differs from
  BilledCost (invoice).
* Some untagged spend (x_TeamId empty) so you can measure tagging hygiene.
* One deliberate anomaly: ml-research Vertex AI spend spikes 6x on day 80 of the
  range (2026-09-18 with the default start date).

Usage:
    python data/generate_sample.py                      # writes data/sample/focus_costs.csv
    python data/generate_sample.py --out /tmp/x.csv --start 2026-01-01 --days 270
    python data/generate_sample.py --out /tmp/recent.csv --recent      # 92 days ending yesterday

Only the standard library is used so it runs anywhere.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

COLUMNS = [
    "BillingAccountId",
    "SubAccountId",
    "ServiceProviderName",
    "ServiceName",
    "ServiceCategory",
    "ChargeCategory",
    "ChargePeriodStart",
    "ChargePeriodEnd",
    "BillingPeriodStart",
    "BilledCost",
    "EffectiveCost",
    "ListCost",
    "BillingCurrency",
    "RegionId",
    "ResourceId",
    "Tags",
    "x_TeamId",
]

BILLING_ACCOUNT = "0A1B2C-3D4E5F-6A7B8C"

# service name -> (FOCUS ServiceCategory, typical daily cost per resource in USD)
SERVICES = {
    "Compute Engine": ("Compute", 42.0),
    "Cloud Run": ("Compute", 9.0),
    "Kubernetes Engine": ("Compute", 55.0),
    "BigQuery": ("Analytics", 31.0),
    "Cloud Storage": ("Storage", 6.5),
    "Vertex AI": ("AI and Machine Learning", 48.0),
}

# team -> (project / SubAccountId, region, services the team uses, size multiplier)
TEAMS = {
    "payments": ("pay-prod-4411", "us-central1",
                 ["Compute Engine", "Cloud Run", "BigQuery", "Cloud Storage"], 1.4),
    "search": ("search-prod-2290", "us-east1",
               ["Kubernetes Engine", "BigQuery", "Cloud Storage", "Vertex AI"], 1.1),
    "data-platform": ("data-prod-7781", "us-central1",
                      ["BigQuery", "Cloud Storage", "Compute Engine", "Cloud Run"], 1.8),
    "ml-research": ("ml-sandbox-1032", "us-central1",
                    ["Vertex AI", "Compute Engine", "Cloud Storage"], 0.9),
}

ANOMALY_TEAM, ANOMALY_SERVICE, ANOMALY_DAY_INDEX, ANOMALY_FACTOR = "ml-research", "Vertex AI", 79, 6.0
COMMITMENT_TEAM, COMMITMENT_SERVICE = "payments", "Compute Engine"
CUD_DISCOUNT = Decimal("0.37")  # covered usage costs 37% less than list
CUD_UTILIZATION = Decimal("0.88")  # 12% of what we committed to goes unused
CENT = Decimal("0.0001")


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def month_start(d: date) -> datetime:
    return datetime(d.year, d.month, 1, tzinfo=timezone.utc)


def generate(start: date, days: int, seed: int = 42) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    covered_effective_by_month: dict[date, Decimal] = {}

    for team, (project, region, services, size) in TEAMS.items():
        for service in services:
            category, base = SERVICES[service]
            for n in (1, 2):
                resource_id = f"projects/{project}/{service.lower().replace(' ', '-')}/res-{n}"
                # each resource has its own level and a gentle upward trend
                level = base * size * rng.uniform(0.6, 1.4)
                trend = rng.uniform(-0.001, 0.004)
                untagged = team == "data-platform" and service == "Cloud Storage" and n == 2
                for i in range(days):
                    day = start + timedelta(days=i)
                    weekday_factor = 0.75 if day.weekday() >= 5 else 1.0
                    daily = level * (1 + trend) ** i * weekday_factor * rng.uniform(0.9, 1.1)
                    if (team, service, i) == (ANOMALY_TEAM, ANOMALY_SERVICE, ANOMALY_DAY_INDEX):
                        daily *= ANOMALY_FACTOR
                    list_cost = money(daily)
                    effective = list_cost
                    billed = list_cost
                    if team == COMMITMENT_TEAM and service == COMMITMENT_SERVICE:
                        effective = money(list_cost * (1 - CUD_DISCOUNT))
                        billed = Decimal("0.0000")  # paid by the monthly commitment purchase
                        key = day.replace(day=1)
                        covered_effective_by_month[key] = covered_effective_by_month.get(key, Decimal(0)) + effective
                    tags = {} if untagged else {"team": team, "env": "prod"}
                    period_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                    rows.append({
                        "BillingAccountId": BILLING_ACCOUNT,
                        "SubAccountId": project,
                        "ServiceProviderName": "Google Cloud",
                        "ServiceName": service,
                        "ServiceCategory": category,
                        "ChargeCategory": "Usage",
                        "ChargePeriodStart": iso(period_start),
                        "ChargePeriodEnd": iso(period_start + timedelta(days=1)),
                        "BillingPeriodStart": iso(month_start(day)),
                        "BilledCost": str(billed),
                        "EffectiveCost": str(effective),
                        "ListCost": str(list_cost),
                        "BillingCurrency": "USD",
                        "RegionId": region,
                        "ResourceId": resource_id,
                        "Tags": json.dumps(tags, separators=(",", ":")),
                        "x_TeamId": "" if untagged else team,
                    })

    # One commitment purchase row per month: billed up front, effective cost 0
    # (its cost already appears, amortized, on the covered usage rows above).
    # We commit to more than we use, so the purchase exceeds the covered usage.
    project, region, _, _ = TEAMS[COMMITMENT_TEAM]
    for month, covered in sorted(covered_effective_by_month.items()):
        period_start = month_start(month)
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        rows.append({
            "BillingAccountId": BILLING_ACCOUNT,
            "SubAccountId": project,
            "ServiceProviderName": "Google Cloud",
            "ServiceName": COMMITMENT_SERVICE,
            "ServiceCategory": "Compute",
            "ChargeCategory": "Purchase",
            "ChargePeriodStart": iso(period_start),
            "ChargePeriodEnd": iso(month_start(next_month)),
            "BillingPeriodStart": iso(period_start),
            "BilledCost": str(money(covered / CUD_UTILIZATION)),
            "EffectiveCost": "0.0000",
            "ListCost": str(money(covered / CUD_UTILIZATION)),
            "BillingCurrency": "USD",
            "RegionId": region,
            "ResourceId": f"projects/{project}/commitments/cud-1",
            "Tags": json.dumps({"team": COMMITMENT_TEAM, "env": "prod"}, separators=(",", ":")),
            "x_TeamId": COMMITMENT_TEAM,
        })

    rows.sort(key=lambda r: (r["ChargePeriodStart"], r["x_TeamId"], r["ServiceName"], r["ResourceId"]))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "sample" / "focus_costs.csv")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 1))
    parser.add_argument("--days", type=int, default=92)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--recent", action="store_true",
                        help="ignore --start and end the range yesterday (for loading to BigQuery)")
    args = parser.parse_args()
    if args.recent:
        args.start = date.today() - timedelta(days=args.days)

    rows = generate(args.start, args.days, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
