"""Three interchangeable deciders behind one interface: ``await decider.decide(case) -> Triage``.

- ``MockDecider``: a rules heuristic. Free, instant, offline; the default, and the
  baseline every model must beat (like jev-trader's MODEL=mock).
- ``JevDecider``: TypeSafe AI's Jev. One request asks all three questions and
  returns a probability for every option.
- ``LlmDecider``: a chat model behind the Phase 4 gateway, asked for the same
  answers as JSON (with the Phase 4 repair loop) and a self-reported confidence.

``with_deadline`` wraps any decider: a late or failed decision becomes "unsure",
which the policy sends to a human. It never becomes an action.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .models import CATEGORIES, URGENCY_LEVELS, AnomalyCase, Triage

REAL_QUESTION = ("Is this an unplanned cost problem that the owning team should act on? "
                 "Answer no for planned purchases and for changes listed in the change calendar.")
CATEGORY_QUESTION = "What most likely explains the extra cost?"
URGENCY_QUESTION = "How urgently should the owning team look at this?"


class Decider(Protocol):
    name: str

    async def decide(self, case: AnomalyCase) -> Triage: ...


# ------------------------------------------------------------------- mock


class MockDecider:
    """Hand-written rules. Its probabilities are rough guesses, and that's the point of the
    calibration report: you'll see how far rules-of-thumb confidence is from reality."""

    name = "mock"

    async def decide(self, case: AnomalyCase) -> Triage:
        start = time.perf_counter()
        top = max(case.top_services, key=lambda s: s.effective_cost - s.previous_week_daily_avg)
        if case.change_calendar:
            category, p_real = "expected_event", 0.15
        elif top.charge_category == "Purchase":
            category, p_real = "commitment_purchase", 0.1
        elif not top.tagged:
            category, p_real = "untagged_spend", 0.8
        elif top.charge_category in ("Credit", "Adjustment"):
            category, p_real = "pricing_change", 0.6
        else:
            category, p_real = "usage_spike", 0.75
        level = 0 if p_real < 0.5 else (3 if case.z_score >= 8 else 2 if case.z_score >= 5 else 1)
        others = (1 - 0.6) / (len(CATEGORIES) - 1)
        return Triage(
            p_real=p_real, category=category, category_confidence=0.6,
            category_probabilities={c: 0.6 if c == category else others for c in CATEGORIES},
            urgency=float(level), urgency_probabilities={level: 1.0},
            decider=self.name, latency_ms=(time.perf_counter() - start) * 1000,
        )


# -------------------------------------------------------------------- jev


class JevDecider:
    """TypeSafe AI's System One API through the official SDK (PyPI: ``typesafe-sdk``,
    import ``typesafe_sdk``). Pass a configured ``AsyncTypeSafeClient``; tests pass one
    whose transport is a fake server, so the real SDK serializes and parses every call."""

    name = "jev"

    def __init__(self, client: Any, model: str | None = None) -> None:
        self._client, self._model = client, model

    @staticmethod
    def questions() -> dict[str, Any]:
        # TODO (Lab 5.9, step 2): ask three questions with the SDK's question types
        #   "real":     Noul(instructions=REAL_QUESTION)                  -> a probability of "yes"
        #   "category": Choice(instructions=CATEGORY_QUESTION, criteria=CATEGORIES)
        #   "urgency":  Score(instructions=URGENCY_QUESTION, criteria=URGENCY_LEVELS)
        # from typesafe_sdk import Choice, Noul, Score
        raise NotImplementedError("Lab 5.9: build the three questions")

    async def decide(self, case: AnomalyCase) -> Triage:
        # TODO (Lab 5.9, step 2): one call answers all three questions:
        #   result = await self._client.system_one(state=case.as_state(), questions=self.questions(), model=self._model)
        # then map result.nouls["real"].noul, result.choices["category"] (.choice, .confidence, .probabilities),
        # result.scores["urgency"] (.score, .probabilities) and result.usage into a Triage.
        # Record decider=f"jev:{result.model}" and the latency.
        raise NotImplementedError("Lab 5.9: call Jev and map its answers")


# -------------------------------------------------------------------- llm


class LlmTriage(BaseModel):
    real: bool = Field(description=REAL_QUESTION)
    real_confidence: float = Field(ge=0, le=1, description="Your confidence that `real` is correct, 0 to 1")
    category: Literal["usage_spike", "untagged_spend", "commitment_purchase", "pricing_change", "expected_event"]
    category_confidence: float = Field(ge=0, le=1)
    urgency: int = Field(ge=0, le=3)


class LlmDecider:
    """The Phase 4 way: structured output from a chat model through the gateway."""

    name = "llm"

    def __init__(self, client: Any, model: str = "fast") -> None:
        self._client, self._model = client, model

    async def decide(self, case: AnomalyCase) -> Triage:
        from costpilot_llm.structured import ask_structured

        start = time.perf_counter()
        system = ("You triage cloud cost anomalies. Categories:\n"
                  + "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
                  + "\nUrgency levels:\n" + "\n".join(f"{i}: {v}" for i, v in enumerate(URGENCY_LEVELS))
                  + "\nAnswer with JSON only.")
        parsed = await ask_structured(self._client, model=self._model, schema=LlmTriage, messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(case.as_state())},
        ])
        t = parsed.value
        p_real = t.real_confidence if t.real else 1 - t.real_confidence
        others = (1 - t.category_confidence) / (len(CATEGORIES) - 1)
        return Triage(
            p_real=p_real, category=t.category, category_confidence=t.category_confidence,
            category_probabilities={c: t.category_confidence if c == t.category else others for c in CATEGORIES},
            urgency=float(t.urgency), urgency_probabilities={t.urgency: 1.0},
            decider=f"{self.name}:{self._model}", latency_ms=(time.perf_counter() - start) * 1000,
            input_tokens=sum(u.get("prompt_tokens") or 0 for u in parsed.usage) or None,
            output_tokens=sum(u.get("completion_tokens") or 0 for u in parsed.usage) or None,
            notes=[f"attempts={parsed.attempts}", "confidence is self-reported"],
        )


# --------------------------------------------------------------- deadline


UNSURE_CATEGORY = "usage_spike"


def unsure(decider: str, reason: str, latency_ms: float) -> Triage:
    """The fail-safe answer: maximally uncertain, so the policy routes it to a human."""
    return Triage(p_real=0.5, category=UNSURE_CATEGORY, category_confidence=0.0, category_probabilities={},
                  urgency=1.0, urgency_probabilities={}, decider=decider, latency_ms=latency_ms, notes=[reason])


class with_deadline:  # noqa: N801 - used like a function: with_deadline(decider, 5.0)
    def __init__(self, inner: Decider, seconds: float) -> None:
        self.inner, self.seconds, self.name = inner, seconds, inner.name

    async def decide(self, case: AnomalyCase) -> Triage:
        start = time.perf_counter()
        try:
            return await asyncio.wait_for(self.inner.decide(case), self.seconds)
        except asyncio.TimeoutError:
            return unsure(self.name, f"late: no decision within {self.seconds}s", (time.perf_counter() - start) * 1000)
        except Exception as exc:  # an API error must not turn into an action
            return unsure(self.name, f"error: {type(exc).__name__}", (time.perf_counter() - start) * 1000)


def build_decider(kind: str, *, gateway_client: Any = None, timeout_s: float = 10.0) -> Decider:
    """mock (default) | jev (needs TYPESAFE_API_KEY) | llm (needs a gateway client)."""
    if kind == "mock":
        inner: Decider = MockDecider()
    elif kind == "jev":
        from typesafe_sdk import AsyncTypeSafeClient

        inner = JevDecider(AsyncTypeSafeClient())   # reads TYPESAFE_API_KEY / TYPESAFE_DEFAULT_MODEL
    elif kind == "llm":
        if gateway_client is None:
            raise ValueError("the llm decider needs an OpenAI-compatible client for the gateway")
        inner = LlmDecider(gateway_client)
    else:
        raise ValueError(f"unknown decider {kind!r}")
    return with_deadline(inner, timeout_s)
