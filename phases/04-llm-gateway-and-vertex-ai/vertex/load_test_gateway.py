"""Lab 4.5 (2) — push the gateway until it throttles, and watch the fallback.

    export OPENAI_API_KEY=$EVAL_RUNNER_VKEY
    python vertex/load_test_gateway.py --model smart --requests 200 --concurrency 40

Prints the status mix and latency percentiles. With a low quota on "smart",
you should see LiteLLM retry and then fall back to "fast" (check the gateway
logs or the x-litellm-model-group response header) instead of failing users.
This spends real money: keep --requests small and the eval-runner budget low.
"""

import argparse
import asyncio
import statistics
import time
from collections import Counter

from openai import APIStatusError, AsyncOpenAI


async def main(args):
    client = AsyncOpenAI(base_url=args.gateway, max_retries=0)
    sem, outcomes, latencies, served_by = asyncio.Semaphore(args.concurrency), Counter(), [], Counter()

    async def one(i):
        async with sem:
            t = time.perf_counter()
            try:
                raw = await client.chat.completions.with_raw_response.create(
                    model=args.model, messages=[{"role": "user", "content": f"Reply with the number {i}."}],
                    max_tokens=5)
                outcomes["ok"] += 1
                served_by[raw.headers.get("x-litellm-model-group", "?")] += 1
            except APIStatusError as e:
                outcomes[e.status_code] += 1
            latencies.append(time.perf_counter() - t)

    await asyncio.gather(*(one(i) for i in range(args.requests)))
    q = statistics.quantiles(latencies, n=20)
    print("outcomes:", dict(outcomes), "served by:", dict(served_by))
    print(f"p50 {q[9]:.2f}s  p95 {q[18]:.2f}s")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--gateway", default="http://localhost:4000")
    p.add_argument("--model", default="smart")
    p.add_argument("--requests", type=int, default=100)
    p.add_argument("--concurrency", type=int, default=20)
    asyncio.run(main(p.parse_args()))
