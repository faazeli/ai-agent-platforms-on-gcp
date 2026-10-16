"""Score answers against expected values.

Numbers pass within 0.5% relative (or 0.01 absolute) tolerance, because a model
summing 90 rows by hand may be off by a cent, and that isn't the failure we care
about. Text passes on a case-insensitive exact match. Dates must match exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field


class Answer(BaseModel):
    """What the model must return. Also the output schema sent to the gateway."""

    answer_type: Literal["number", "text", "date"]
    value: str = Field(description="The answer itself: a plain number, a name, or YYYY-MM-DD")
    unit: str | None = Field(default=None, description="Currency code for money, otherwise null")
    explanation: str = Field(max_length=400, description="One or two sentences")


def _number(text: str) -> Decimal | None:
    cleaned = re.sub(r"[^\d.\-]", "", text)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def is_correct(expected: dict[str, Any], answer: Answer) -> bool:
    # TODO Lab 4.3: numbers pass within max(0.01, 0.5% of the target) (use _number to
    #   tolerate "1,003.00"), dates must match exactly, text matches case-insensitively
    #   after stripping whitespace.
    raise NotImplementedError


@dataclass
class CaseResult:
    id: str
    tag: str
    correct: bool
    attempts: int
    error: str | None = None


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    by_tag: dict[str, list[CaseResult]] = {}
    for r in results:
        by_tag.setdefault(r.tag, []).append(r)
    return {
        "cases": total,
        "accuracy": round(sum(r.correct for r in results) / total, 3) if total else 0.0,
        "parse_failures": sum(r.error is not None for r in results),
        "repairs": sum(max(r.attempts - 1, 0) for r in results),
        "by_tag": {t: round(sum(r.correct for r in rs) / len(rs), 3) for t, rs in sorted(by_tag.items())},
    }
