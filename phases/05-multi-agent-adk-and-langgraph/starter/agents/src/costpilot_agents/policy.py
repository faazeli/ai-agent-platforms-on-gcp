"""Execution boundaries, enforced in code rather than hoped for in prompts.

Prompts *ask* a model to behave. These callbacks *make* the system behave, even
when the model is confused, jailbroken, or reading hostile data:

1. Allow-list: an agent can only run the tools its policy names.
2. Approval: tools that change anything need a human approval recorded in state.
3. Budget: a hard cap on model calls per run (the gateway caps dollars too).

Every decision is reported to an optional ``audit`` callable; Phase 6 plugs in
the immutable audit log there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from google.adk.models.llm_response import LlmResponse
from google.genai import types

AuditFn = Callable[[dict[str, Any]], None]
APPROVALS_KEY = "approved_actions"      # session state: list of approved "<tool>:<key arg>" strings
CALLS_KEY = "temp:model_calls"          # "temp:" state lives for one invocation only; suffixed per agent


@dataclass(frozen=True)
class ToolPolicy:
    agent: str
    allowed: frozenset[str]
    approval_required: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def of(cls, agent: str, allowed: set[str], approval_required: set[str] | None = None) -> "ToolPolicy":
        approval = frozenset(approval_required or set())
        return cls(agent, frozenset(allowed) | approval, approval)


def approval_key(tool_name: str, args: dict[str, Any]) -> str:
    """What a human approves: the tool plus its arguments, so approving one ticket isn't approving all."""
    return f"{tool_name}:" + ",".join(f"{k}={args[k]}" for k in sorted(args))


def make_tool_guard(policy: ToolPolicy, audit: AuditFn | None = None):
    def before_tool(tool, args: dict[str, Any], tool_context) -> dict[str, Any] | None:
        # TODO Lab 5.3 (a): decide "allowed" / "denied" / "needs_approval":
        #   - denied if tool.name is not in policy.allowed
        #   - needs_approval if tool.name is in policy.approval_required and
        #     approval_key(tool.name, args) is not in tool_context.state.get(APPROVALS_KEY, [])
        #   Report every decision to audit(...) if given. Return None to run the tool,
        #   or a dict {"error": {type, status: 403, detail, hint}} to skip it (the model
        #   sees that dict as the tool's result).
        raise NotImplementedError

    return before_tool


def make_model_budget(max_calls: int, agent: str = "", audit: AuditFn | None = None):
    key = f"{CALLS_KEY}:{agent or 'agent'}"  # one counter per agent per run

    def before_model(callback_context, llm_request) -> LlmResponse | None:
        # TODO Lab 5.3 (b): increment callback_context.state[key]; return None while
        #   within max_calls. Past the limit, audit a "budget_stop" event and return an
        #   LlmResponse whose text says the request reached its limit of {max_calls}
        #   model calls (returning a response skips the real model call).
        raise NotImplementedError

    return before_model
