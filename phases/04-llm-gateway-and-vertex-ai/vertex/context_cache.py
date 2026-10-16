"""Lab 4.5 (3) — context caching: pay once for a large, repeated prefix.

Caches CostPilot's long system context (FOCUS definitions + examples + data),
then asks several questions against it, and prints token usage so you can
compare cost and latency with and without the cache.

    PROJECT=my-project LOCATION=global MODEL=gemini-3.5-flash python vertex/context_cache.py

Caches have a minimum size and a storage charge per hour of TTL; check the
current limits and prices in the Vertex AI context caching docs before relying
on the numbers below for a decision.
"""

import json
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "solution/llm-toolkit/src"))
from costpilot_llm.evals.data import build_context, load_facts  # noqa: E402
from costpilot_llm.prompts import load_prompt  # noqa: E402

client = genai.Client(vertexai=True, project=os.environ["PROJECT"], location=os.environ.get("LOCATION", "global"))
model = os.environ.get("MODEL", "gemini-3.5-flash")
facts = load_facts()
# Include every month's daily series: caching only pays off (and is only allowed)
# above a minimum prefix size, which a single month's data may not reach.
context = json.dumps({m: build_context(facts, daily_month=m) for m in facts.months})
system = load_prompt("cost_analyst").render(context=context, question="(questions follow)")
questions = ["Which team spent most in September 2026?", "What was untagged spend in September 2026?"]


def ask(question: str, cached_name: str | None = None):
    config = types.GenerateContentConfig(cached_content=cached_name) if cached_name else \
        types.GenerateContentConfig(system_instruction=system)
    r = client.models.generate_content(model=model, contents=question, config=config)
    u = r.usage_metadata
    return r.text.strip()[:80], u.prompt_token_count, getattr(u, "cached_content_token_count", 0)


print("Without cache:")
for q in questions:
    print("  ", ask(q))

cache = client.caches.create(
    model=model,
    config=types.CreateCachedContentConfig(system_instruction=system, ttl="600s", display_name="costpilot-context"),
)
try:
    print("With cache:", cache.name)
    for q in questions:
        print("  ", ask(q, cache.name))
finally:
    client.caches.delete(name=cache.name)  # stop paying for cache storage
