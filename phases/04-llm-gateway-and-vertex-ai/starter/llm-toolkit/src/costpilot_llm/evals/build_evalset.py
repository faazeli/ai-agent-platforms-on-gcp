"""Build the CostPilot eval set from the sample data.

    python -m costpilot_llm.evals.build_evalset --out evals/evalset.jsonl

Each line is one case: a question, the expected answer, and a tag saying which
capability it exercises. Expected answers come from data.py, never from a model.
Phase 5 reuses the same file to evaluate agents that use tools.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from .data import Facts, load_facts

MONTH_NAMES = {"07": "July", "08": "August", "09": "September"}


def _pos(team: str) -> str:
    return f"{team}'" if team.endswith("s") else f"{team}'s"


def _human(month: str) -> str:
    return f"{MONTH_NAMES.get(month[5:], month[5:])} {month[:4]}"


def build_cases(facts: Facts) -> list[dict]:
    cases: list[dict] = []

    def add(tag: str, question: str, answer_type: str, value: str, unit: str | None = None) -> None:
        cases.append({"id": f"q{len(cases) + 1:02d}", "tag": tag, "question": question,
                      "expected": {"answer_type": answer_type, "value": value, "unit": unit}})

    months = facts.months
    last = months[-1]

    for month in months:  # 12 cases: totals
        for team in facts.teams:
            tm = facts.team_month[(team, month)]
            add("total", f"What was {_pos(team)} total effective cost in {_human(month)}?",
                "number", str(round(tm.effective, 2)), facts.currency)

    for team in facts.teams:  # 4 cases: top service
        by_service = facts.team_month[(team, last)].by_service
        add("top_service", f"Which service cost {team} the most in {_human(last)}?",
            "text", max(by_service, key=by_service.get))

    for month in months:  # 3 cases: billed vs effective (unused commitment)
        tm = facts.team_month[("payments", month)]
        add("commitment", f"How much more did payments get billed than its effective cost in {_human(month)}?",
            "number", str(round(tm.billed - tm.effective, 2)), facts.currency)

    ml_days = {d: c for (t, d), c in facts.daily.items() if t == "ml-research" and d.strftime("%Y-%m") == last}
    add("anomaly", f"On which day in {_human(last)} did {_pos('ml-research')} daily cost spike?",
        "date", max(ml_days, key=ml_days.get).isoformat())

    add("untagged", f"How much spend had no owning team in {_human(last)}?",
        "number", str(round(facts.untagged.get(last, Decimal(0)), 2)), facts.currency)

    totals = {t: facts.team_month[(t, last)].effective for t in facts.teams}
    add("ranking", f"Which team had the highest effective cost in {_human(last)}?", "text", max(totals, key=totals.get))

    dp = {m: facts.team_month[("data-platform", m)].effective for m in months}
    best = max(dp, key=dp.get)
    add("ranking", "In which month was data-platform's effective cost highest? Answer as YYYY-MM.", "text", best)

    first = months[0]
    add("billed", f"What was {_pos('search')} total billed cost in {_human(first)}?",
        "number", str(round(facts.team_month[("search", first)].billed, 2)), facts.currency)

    add("count", f"How many different services did payments use in {_human(last)}?",
        "number", str(len(facts.team_month[("payments", last)].by_service)), None)

    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("evals/evalset.jsonl"))
    args = parser.parse_args()
    cases = build_cases(load_facts())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(c) + "\n" for c in cases))
    print(f"wrote {len(cases)} cases to {args.out}  (built {date.today().isoformat()})")


if __name__ == "__main__":
    main()
