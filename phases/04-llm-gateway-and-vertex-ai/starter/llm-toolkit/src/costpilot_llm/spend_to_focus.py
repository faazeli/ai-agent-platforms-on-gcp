"""FinOps for your own AI spend: turn LiteLLM spend logs into FOCUS rows.

The gateway records the cost of every call per virtual key. Aggregating those
logs per day, key and model, and writing them in the same FOCUS shape as the
cloud bill, lets CostPilot answer "what do our agents cost?" with the same
tools it uses for everything else.

    curl -s "localhost:4000/spend/logs?start_date=2026-10-01&end_date=2026-10-15" \
      -H "Authorization: Bearer $LITELLM_MASTER_KEY" > spend.json
    python -m costpilot_llm.spend_to_focus spend.json --out ai_spend_focus.csv

Field names in spend logs vary a little between LiteLLM versions; the accessors
below accept the common spellings. Check one row of your own export first.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

FOCUS_COLUMNS = [
    "BillingAccountId", "SubAccountId", "ServiceProviderName", "ServiceName", "ServiceCategory",
    "ChargeCategory", "ChargePeriodStart", "ChargePeriodEnd", "BillingPeriodStart", "BilledCost",
    "EffectiveCost", "ListCost", "BillingCurrency", "RegionId", "ResourceId", "Tags", "x_TeamId",
]


def _first(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return default


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def to_focus_rows(logs: list[dict[str, Any]], billing_account: str = "litellm-gateway",
                  currency: str = "USD") -> list[dict[str, str]]:
    """Aggregate spend per (day, agent key, model) into one FOCUS Usage row each."""
    totals: dict[tuple[str, str, str, str], Decimal] = defaultdict(Decimal)
    for log in logs:
        metadata = _first(log, "metadata", default={}) or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        key_meta = metadata.get("user_api_key_metadata") or metadata
        day = _timestamp(_first(log, "startTime", "start_time")).strftime("%Y-%m-%d")
        agent = _first(key_meta, "agent", default=None) or _first(metadata, "user_api_key_alias",
                                                                  default="unknown-agent")
        team = _first(key_meta, "team", default="") or ""
        model = _first(log, "model_group", "model", default="unknown-model")
        totals[(day, agent, team, model)] += Decimal(str(_first(log, "spend", default=0)))

    rows = []
    for (day, agent, team, model), spend in sorted(totals.items()):
        start = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        cost = str(spend.quantize(Decimal("0.000001")))
        rows.append({
            "BillingAccountId": billing_account,
            "SubAccountId": "costpilot",
            "ServiceProviderName": "Google Cloud",
            "ServiceName": "Vertex AI",
            "ServiceCategory": "AI and Machine Learning",
            "ChargeCategory": "Usage",
            "ChargePeriodStart": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ChargePeriodEnd": (start + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "BillingPeriodStart": start.replace(day=1).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "BilledCost": cost,
            "EffectiveCost": cost,
            "ListCost": cost,
            "BillingCurrency": currency,
            "RegionId": "",
            "ResourceId": f"litellm/{agent}/{model}",
            "Tags": json.dumps({"agent": agent, "model_alias": model, "team": team}, separators=(",", ":")),
            "x_TeamId": team,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spend_logs", type=Path, help="JSON array from GET /spend/logs")
    parser.add_argument("--out", type=Path, default=Path("ai_spend_focus.csv"))
    args = parser.parse_args()
    rows = to_focus_rows(json.loads(args.spend_logs.read_text()))
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FOCUS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} FOCUS rows to {args.out}; load them with Phase 2's staging + MERGE")


if __name__ == "__main__":
    main()
