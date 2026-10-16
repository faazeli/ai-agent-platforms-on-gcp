"""Run the eval set against a prompt version through the gateway.

    export OPENAI_API_KEY=$EVAL_RUNNER_VKEY          # a LiteLLM virtual key, not a vendor key
    python -m costpilot_llm.evals.run_eval --prompt-version 2 --model fast --runs 1

Writes one JSON line per case to evals/results/ and prints a summary. Compare
prompt versions by accuracy, parse failures and repairs. A prompt change ships
only if it does not lower accuracy (Phase 9 turns this into a CI gate).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..prompts import load_prompt
from ..structured import StructuredOutputError, ask_structured
from .data import build_context, load_facts
from .scorer import Answer, CaseResult, is_correct, summarize

AnswerFn = Callable[[str], Awaitable[tuple[Answer, int]]]


async def run_cases(cases: list[dict[str, Any]], answer: AnswerFn, concurrency: int = 4) -> list[CaseResult]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(case: dict[str, Any]) -> CaseResult:
        async with semaphore:
            try:
                got, attempts = await answer(case["question"])
            except StructuredOutputError as exc:
                return CaseResult(case["id"], case["tag"], False, 3, exc.problem["detail"])
            return CaseResult(case["id"], case["tag"], is_correct(case["expected"], got), attempts)

    return await asyncio.gather(*(one(c) for c in cases))


def gateway_answerer(client: Any, model: str, prompt_version: int | None) -> AnswerFn:
    prompt = load_prompt("cost_analyst", prompt_version)
    context = json.dumps(build_context(load_facts()), indent=1)

    async def answer(question: str) -> tuple[Answer, int]:
        parsed = await ask_structured(
            client, model=model, schema=Answer,
            messages=[{"role": "user", "content": prompt.render(context=context, question=question)}],
        )
        return parsed.value, parsed.attempts

    return answer


async def main_async(args: argparse.Namespace) -> None:
    from openai import AsyncOpenAI  # the gateway speaks the OpenAI protocol

    client = AsyncOpenAI(base_url=args.gateway)  # key from OPENAI_API_KEY
    cases = [json.loads(line) for line in args.evalset.read_text().splitlines() if line.strip()]
    answer = gateway_answerer(client, args.model, args.prompt_version)
    all_results: list[CaseResult] = []
    for _ in range(args.runs):
        all_results += await run_cases(cases, answer)
    summary = summarize(all_results) | {"prompt": f"cost_analyst.v{args.prompt_version or 'latest'}",
                                        "model": args.model, "runs": args.runs}
    out = args.results_dir / f"{int(time.time())}-v{args.prompt_version or 'latest'}-{args.model}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r.__dict__) + "\n" for r in all_results))
    print(json.dumps(summary, indent=2))
    if args.min_accuracy is not None and summary["accuracy"] < args.min_accuracy:
        raise SystemExit(f"FAIL: accuracy {summary['accuracy']} < required {args.min_accuracy}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evalset", type=Path, default=Path("evals/evalset.jsonl"))
    parser.add_argument("--results-dir", type=Path, default=Path("evals/results"))
    parser.add_argument("--gateway", default="http://localhost:4000")
    parser.add_argument("--model", default="fast")
    parser.add_argument("--prompt-version", type=int, default=None)
    parser.add_argument("--runs", type=int, default=1, help="repeat to measure variance")
    parser.add_argument("--min-accuracy", type=float, default=None,
                        help="exit non-zero below this accuracy (the CI gate in Phase 9)")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
