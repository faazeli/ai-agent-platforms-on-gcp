"""Size an agentic platform from a written-down workload model.

    python sizing/workload_model.py sizing/assumptions.example.yaml
    python sizing/workload_model.py my.yaml --scale users=5            # what breaks at 5x users?
    python sizing/workload_model.py my.yaml --markdown > docs/sizing/model.md

Turns assumptions (users, questions, model calls per question, tokens per call,
how peaky traffic is) into the numbers that decide resources: peak requests and
tokens per minute per model, monthly tokens, monthly cost, cost per 1,000
questions, and headroom against your quotas. Every assumption lives in the YAML,
so reviewers can argue with inputs rather than with conclusions.

Prices and quotas in the example file are PLACEHOLDERS. Replace them with values
from the current pricing pages and your own project's quota page (Phase 4 field notes).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

HEADROOM_WARNING = 0.8  # flag when peak uses more than 80% of a quota


@dataclass
class AliasLoad:
    alias: str
    calls_per_day: float
    peak_calls_per_minute: float
    peak_tokens_per_minute: float
    monthly_input_tokens: float
    monthly_output_tokens: float
    monthly_cost: float
    rpm_quota: float | None
    tpm_quota: float | None

    @property
    def rpm_utilization(self) -> float | None:
        return self.peak_calls_per_minute / self.rpm_quota if self.rpm_quota else None

    @property
    def tpm_utilization(self) -> float | None:
        return self.peak_tokens_per_minute / self.tpm_quota if self.tpm_quota else None


def apply_scale(assumptions: dict[str, Any], scales: dict[str, float]) -> dict[str, Any]:
    scaled = json.loads(json.dumps(assumptions))
    for key, factor in scales.items():
        if key not in scaled["traffic"]:
            raise KeyError(f"--scale {key}: not a traffic assumption ({sorted(scaled['traffic'])})")
        scaled["traffic"][key] *= factor
    return scaled


def compute(a: dict[str, Any]) -> dict[str, Any]:
    t = a["traffic"]
    questions_per_day = t["users"] * t["questions_per_user_per_day"]
    working_days = t.get("working_days_per_month", 22)
    peak_share = t["peak_hour_share"]  # fraction of a day's traffic that lands in the busiest hour

    loads: list[AliasLoad] = []
    for alias, m in a["models"].items():
        calls_per_day = questions_per_day * m["calls_per_question"]
        tokens_per_call = m["input_tokens_per_call"] + m["output_tokens_per_call"]
        peak_cpm = calls_per_day * peak_share / 60
        monthly_in = calls_per_day * m["input_tokens_per_call"] * working_days
        monthly_out = calls_per_day * m["output_tokens_per_call"] * working_days
        cost = (monthly_in / 1e6 * m["price_per_million_input"] + monthly_out / 1e6 * m["price_per_million_output"])
        quota = a.get("quotas", {}).get(alias, {})
        loads.append(AliasLoad(alias, calls_per_day, peak_cpm, peak_cpm * tokens_per_call, monthly_in, monthly_out,
                               cost, quota.get("requests_per_minute"), quota.get("tokens_per_minute")))

    fixed = a.get("fixed_monthly_costs", {})
    model_cost = sum(load.monthly_cost for load in loads)
    total = model_cost + sum(fixed.values())
    monthly_questions = questions_per_day * working_days
    warnings = []
    for load in loads:
        for name, util in (("requests/min", load.rpm_utilization), ("tokens/min", load.tpm_utilization)):
            if util is not None and util > HEADROOM_WARNING:
                warnings.append(f"{load.alias}: peak {name} at {util:.0%} of quota")
    return {
        "questions_per_day": questions_per_day,
        "peak_questions_per_minute": questions_per_day * peak_share / 60,
        "loads": loads,
        "model_cost": model_cost,
        "fixed_costs": fixed,
        "total_monthly_cost": total,
        "cost_per_1000_questions": total / monthly_questions * 1000 if monthly_questions else math.nan,
        "warnings": warnings,
    }


def render(result: dict[str, Any], currency: str = "USD", markdown: bool = False) -> str:
    lines = []
    head = "| Alias | Calls/day | Peak calls/min | Peak tokens/min | Quota use (req / tok) | Monthly tokens (in/out) | Monthly cost |"
    if markdown:
        lines += ["# Workload model", "", head, "| --- | --- | --- | --- | --- | --- | --- |"]
    else:
        lines += [head]
    for load in result["loads"]:
        use = " / ".join(f"{u:.0%}" if u is not None else "n/a" for u in (load.rpm_utilization, load.tpm_utilization))
        lines.append(f"| {load.alias} | {load.calls_per_day:,.0f} | {load.peak_calls_per_minute:,.1f} | "
                     f"{load.peak_tokens_per_minute:,.0f} | {use} | "
                     f"{load.monthly_input_tokens / 1e6:,.1f}M / {load.monthly_output_tokens / 1e6:,.1f}M | "
                     f"{load.monthly_cost:,.2f} {currency} |")
    lines += ["", f"Questions/day: {result['questions_per_day']:,.0f}  ·  peak questions/min: "
                  f"{result['peak_questions_per_minute']:,.1f}",
              f"Model cost: {result['model_cost']:,.2f} {currency}/month"]
    for item, cost in result["fixed_costs"].items():
        lines.append(f"  + {item}: {cost:,.2f} {currency}/month")
    lines += [f"Total: {result['total_monthly_cost']:,.2f} {currency}/month  ·  "
              f"{result['cost_per_1000_questions']:,.2f} {currency} per 1,000 questions"]
    if result["warnings"]:
        lines += ["", "WARNINGS:"] + [f"  - {w}" for w in result["warnings"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("assumptions", type=Path)
    parser.add_argument("--scale", action="append", default=[], metavar="KEY=FACTOR",
                        help="multiply a traffic assumption, e.g. users=5")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    assumptions = yaml.safe_load(args.assumptions.read_text())
    scales = {k: float(v) for k, v in (s.split("=", 1) for s in args.scale)}
    result = compute(apply_scale(assumptions, scales))
    print(render(result, assumptions.get("currency", "USD"), args.markdown))
    if result["warnings"]:
        sys.exit(2)  # lets CI or a script notice that a quota would be exceeded


if __name__ == "__main__":
    main()
