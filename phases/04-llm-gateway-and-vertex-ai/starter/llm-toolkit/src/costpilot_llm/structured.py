"""Parse, validate, repair, or fail: getting typed objects out of an LLM.

``ask_structured`` asks the model for JSON matching a Pydantic schema, validates
it, and if validation fails, sends the errors back and asks for a corrected
answer, up to ``max_repairs`` times. Then it gives up with a Problem Details
error. It never ``eval``s, never guesses, never returns unvalidated data.

It talks to any OpenAI-compatible client, which is what the LiteLLM gateway
exposes, so the same code works with every model behind the gateway.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


class StructuredOutputError(Exception):
    """The model could not produce valid output. ``problem`` is an RFC 9457 body."""

    def __init__(self, schema_name: str, attempts: int, last_errors: list[dict[str, Any]]) -> None:
        self.problem = {
            "type": "https://example.com/problems/llm-output-invalid",
            "title": "Model output failed validation",
            "status": 502,
            "detail": f"No valid {schema_name} after {attempts} attempt(s).",
            "errors": last_errors[:5],
        }
        super().__init__(self.problem["detail"])


@dataclass
class Parsed(Generic[T]):
    value: T
    attempts: int
    raw: str
    usage: list[dict[str, Any]] = field(default_factory=list)


def strip_fences(text: str) -> str:
    """Cheap local repair: many models wrap JSON in ```json fences."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


def response_format_for(schema: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
    }


def _compact(errors: list[Any]) -> list[dict[str, Any]]:
    return [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in errors]


async def ask_structured(
    client: Any,
    *,
    model: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_repairs: int = 2,
    temperature: float = 0.0,
) -> Parsed[T]:
    # TODO Lab 4.4: implement the parse -> validate -> repair loop.
    #   For attempt in 1..max_repairs+1:
    #     1. call client.chat.completions.create(model=..., messages=history,
    #        response_format=response_format_for(schema), temperature=temperature)
    #     2. raw = response.choices[0].message.content; record response.usage if present
    #     3. try schema.model_validate_json(strip_fences(raw)) -> return Parsed(value, attempt, raw, usage)
    #     4. on ValidationError: append the assistant's raw answer and a user message that
    #        lists _compact(exc.errors()) and asks for corrected JSON only
    #   After the loop: raise StructuredOutputError(schema.__name__, max_repairs + 1, last_errors)
    raise NotImplementedError
