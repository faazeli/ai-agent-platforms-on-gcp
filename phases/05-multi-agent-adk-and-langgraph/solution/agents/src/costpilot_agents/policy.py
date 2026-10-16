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
        decision, reason = "allowed", ""
        if tool.name not in policy.allowed:
            decision, reason = "denied", f"{policy.agent} may not call {tool.name}"
        elif tool.name in policy.approval_required:
            if approval_key(tool.name, args) not in tool_context.state.get(APPROVALS_KEY, []):
                decision, reason = "needs_approval", "a human must approve this exact action first"
        if audit:
            audit({"event": "tool_call", "agent": policy.agent, "tool": tool.name, "args": args,
                   "decision": decision, "reason": reason})
        if decision == "allowed":
            return None  # run the tool
        # Returning a dict skips the tool; the model sees this as the tool's result.
        return {"error": {"type": "https://example.com/problems/" +
                          ("tool-not-allowed" if decision == "denied" else "approval-required"),
                          "status": 403, "detail": reason,
                          "hint": "Tell the user what you would do and ask them to approve it."
                          if decision == "needs_approval" else "Use only your own tools."}}

    return before_tool


def make_model_budget(max_calls: int, agent: str = "", audit: AuditFn | None = None):
    key = f"{CALLS_KEY}:{agent or 'agent'}"  # one counter per agent per run

    def before_model(callback_context, llm_request) -> LlmResponse | None:
        calls = callback_context.state.get(key, 0) + 1
        callback_context.state[key] = calls
        if calls <= max_calls:
            return None
        if audit:
            audit({"event": "budget_stop", "agent": agent, "model_calls": calls, "limit": max_calls})
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text=f"I stopped because this request reached its limit of {max_calls} model calls. "
                 "Please narrow the question.")]))

    return before_model
