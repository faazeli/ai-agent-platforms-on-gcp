"""Lab 9.7 — the four DORA metrics from a deployments log.

    python dora/dora_metrics.py deployments.csv --days 28

deployments.csv columns (one row per production deployment):
    deployed_at, first_commit_at, service, change_failed, restored_at
    2026-10-01T14:03:00Z, 2026-09-30T09:12:00Z, agents, false,
    2026-10-02T10:00:00Z, 2026-10-01T16:40:00Z, cost-api, true, 2026-10-02T11:25:00Z

Export it from your deploy history, e.g. GitHub deployments:
    gh api repos/OWNER/REPO/deployments --paginate -q '.[] | [.created_at, .sha, .environment] | @csv'
(then join commit times with `git log` and mark failures from your incident tracker).
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def compute(rows: list[dict[str, str]], days: int) -> dict[str, float | None]:
    if not rows:
        return {"deploys_per_week": 0.0, "lead_time_hours_median": None,
                "change_failure_rate": None, "time_to_restore_hours_median": None}
    end = max(_ts(r["deployed_at"]) for r in rows)
    window = [r for r in rows if _ts(r["deployed_at"]) > end - timedelta(days=days)]
    lead = [(_ts(r["deployed_at"]) - _ts(r["first_commit_at"])).total_seconds() / 3600 for r in window]
    failed = [r for r in window if r["change_failed"].strip().lower() == "true"]
    restore = [(_ts(r["restored_at"]) - _ts(r["deployed_at"])).total_seconds() / 3600
               for r in failed if r.get("restored_at", "").strip()]
    return {
        "deploys_per_week": round(len(window) / (days / 7), 2),
        "lead_time_hours_median": round(median(lead), 1) if lead else None,
        "change_failure_rate": round(len(failed) / len(window), 3) if window else None,
        "time_to_restore_hours_median": round(median(restore), 1) if restore else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--days", type=int, default=28)
    args = parser.parse_args()
    with args.csv.open(newline="") as f:
        rows = [{k.strip(): v for k, v in row.items()} for row in csv.DictReader(f, skipinitialspace=True)]
    for name, value in compute(rows, args.days).items():
        print(f"{name:32} {value}")


if __name__ == "__main__":
    main()
