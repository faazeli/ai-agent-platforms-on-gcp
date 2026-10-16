"""Compare deciders on the labeled triage set: accuracy, calibration, coverage, latency, tokens.

    python -m costpilot_agents.typed_decisions.run_eval --decider mock
    TYPESAFE_API_KEY=... python -m costpilot_agents.typed_decisions.run_eval --decider jev
    python -m costpilot_agents.typed_decisions.run_eval --decider llm --gateway http://localhost:4000

Run all three, put the tables side by side, and record the result in your ADR.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
from pathlib import Path
from typing import Any

from .calibration import brier, expected_calibration_error, selective
from .deciders import Decider, build_decider
from .models import AnomalyCase
from .policy import TriagePolicy, route

DEFAULT_EVALSET = Path(__file__).resolve().parents[3] / "evals" / "triage_evalset.jsonl"


def load_cases(path: Path = DEFAULT_EVALSET) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


async def evaluate(decider: Decider, cases: list[dict[str, Any]], policy: TriagePolicy | None = None,
                   concurrency: int = 4) -> dict[str, Any]:
    policy = policy or TriagePolicy()
    gate = asyncio.Semaphore(concurrency)

    async def one(item: dict[str, Any]):
        async with gate:
            return await decider.decide(AnomalyCase.model_validate(item["case"]))

    triages = await asyncio.gather(*(one(c) for c in cases))
    expected = [c["expected"] for c in cases]
    p = [t.p_real for t in triages]
    real = [e["real"] for e in expected]
    routes = [route(t, policy).kind for t in triages]
    # The costly mistake: a real problem the policy dismissed without asking anyone.
    missed = [c["case"]["case_id"] for c, r, e in zip(cases, routes, expected, strict=True) if r == "dismiss" and e["real"]]
    # The noisy mistake: a ticket proposed for something that was not a problem.
    false_alarms = [c["case"]["case_id"] for c, r, e in zip(cases, routes, expected, strict=True)
                    if r == "propose_ticket" and not e["real"]]
    tokens = [t.input_tokens or 0 for t in triages]
    return {
        "decider": triages[0].decider if triages else decider.name,
        "cases": len(cases),
        "real_accuracy": round(sum((pi >= 0.5) == r for pi, r in zip(p, real, strict=True)) / len(cases), 3),
        "brier": round(brier(p, real), 3),
        "ece": round(expected_calibration_error(p, real), 3),
        "auto_decided": selective(p, real, policy.dismiss_below, policy.act_above),
        "category_accuracy": round(sum(t.category == e["category"] for t, e in zip(triages, expected, strict=True)) / len(cases), 3),
        "urgency_mae": round(statistics.mean(abs(t.urgency - e["urgency"]) for t, e in zip(triages, expected, strict=True)), 2),
        "routes": {k: routes.count(k) for k in ("dismiss", "notify", "review", "propose_ticket")},
        "missed_real_problems": missed,
        "false_alarm_proposals": false_alarms,
        "latency_ms_p50": round(statistics.median(t.latency_ms for t in triages), 1),
        "input_tokens_total": sum(tokens) or None,
        "policy_version": policy.version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--decider", choices=["mock", "jev", "llm"], default=os.environ.get("COSTPILOT_DECIDER", "mock"))
    parser.add_argument("--evalset", type=Path, default=DEFAULT_EVALSET)
    parser.add_argument("--gateway", default=os.environ.get("COSTPILOT_GATEWAY_URL", "http://localhost:4000"))
    parser.add_argument("--max-brier", type=float, help="exit 1 if the Brier score is worse (a CI gate)")
    args = parser.parse_args()

    client = None
    if args.decider == "llm":
        from openai import AsyncOpenAI

        client = AsyncOpenAI(base_url=args.gateway, api_key=os.environ.get("COORDINATOR_VKEY", "sk-dev"))
    report = asyncio.run(evaluate(build_decider(args.decider, gateway_client=client), load_cases(args.evalset)))
    print(json.dumps(report, indent=2))
    if args.max_brier is not None and report["brier"] > args.max_brier:
        raise SystemExit(f"Brier {report['brier']} > {args.max_brier}")


if __name__ == "__main__":
    main()
