"""CostPilot's agent team, built with Google ADK.

    coordinator ──► cost_analyst      (get_team_cost, top_resources, list_teams)
                ├─► anomaly_detector  (detect_anomalies, top_resources, list_teams)
                └─► recommender       (get_team_cost, top_resources, create_savings_ticket*)
                                                          * approval-gated write

    monthly_report:  START ─┬─► cost_gatherer ───┬─► join ─► report_writer   (a Workflow)
                            └─► anomaly_gatherer ┘

Everything an agent depends on is injected: the model for each agent (so each
can use its own gateway key and budget) and a ``tools_for`` factory that returns
the tools for a list of names (MCP in production, plain functions in tests).
That makes the team testable offline and deployable unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from google.adk.agents import LlmAgent
from google.adk.workflow import START, JoinNode, Workflow

from ..policy import AuditFn, ToolPolicy, make_model_budget, make_tool_guard
from ..tickets import create_savings_ticket

INSTRUCTIONS = Path(__file__).resolve().parents[1] / "instructions"
ToolsFor = Callable[[list[str]], list[Any]]
# (before_model_callback, after_model_callback), e.g. Phase 6's Model Armor adk_callbacks(...)
Guardrails = tuple[Callable[..., Any], Callable[..., Any]] | None

POLICIES = {
    "cost_analyst": ToolPolicy.of("cost_analyst", {"get_team_cost", "top_resources", "list_teams"}),
    "anomaly_detector": ToolPolicy.of("anomaly_detector", {"detect_anomalies", "top_resources", "list_teams"}),
    "recommender": ToolPolicy.of("recommender", {"get_team_cost", "top_resources"},
                                 approval_required={"create_savings_ticket"}),
    "cost_gatherer": ToolPolicy.of("cost_gatherer", {"get_team_cost", "top_resources"}),
    "anomaly_gatherer": ToolPolicy.of("anomaly_gatherer", {"detect_anomalies"}),
}
LOCAL_TOOLS = {"create_savings_ticket": create_savings_ticket}  # not MCP: our own write action


def instruction(name: str) -> str:
    return (INSTRUCTIONS / f"{name}.md").read_text()


def _specialist(name: str, description: str, model: Any, tools_for: ToolsFor,
                max_model_calls: int, audit: AuditFn | None, guardrails: Guardrails = None,
                **extra: Any) -> LlmAgent:
    policy = POLICIES[name]
    mcp_names = sorted(policy.allowed - LOCAL_TOOLS.keys())
    local = [LOCAL_TOOLS[t] for t in sorted(policy.allowed & LOCAL_TOOLS.keys())]
    return LlmAgent(
        name=name,
        description=description,
        model=model,
        instruction=instruction(name),
        tools=[*tools_for(mcp_names), *local],
        before_tool_callback=make_tool_guard(policy, audit),
        # Callbacks run in order; the first to return a response short-circuits the model call.
        before_model_callback=[make_model_budget(max_model_calls, name, audit),
                               *([guardrails[0]] if guardrails else [])],
        after_model_callback=[guardrails[1]] if guardrails else None,
        **extra,
    )


def build_team(models: dict[str, Any], tools_for: ToolsFor, *, max_model_calls: int = 12,
               audit: AuditFn | None = None, guardrails: Guardrails = None) -> LlmAgent:
    """``models`` maps agent name -> ADK model (a LiteLlm, a model string, or a test double)."""
    # TODO Lab 5.2 (a): build the three specialists with _specialist(...), passing guardrails through:
    #   cost_analyst, anomaly_detector, recommender (each with a one-line description,
    #   which is what the coordinator reads when deciding where to route).
    # Then return the coordinator: an LlmAgent named "coordinator" with
    #   instruction("coordinator"), sub_agents=[...], NO tools, a model budget, and the
    #   guardrails too (it reads the user's message first).
    raise NotImplementedError


def build_monthly_report(models: dict[str, Any], tools_for: ToolsFor, *,
                         audit: AuditFn | None = None) -> Workflow:
    """START ─┬─► cost_gatherer ───┬─► join ─► report_writer"""
    # TODO Lab 5.2 (b): build cost_gatherer (output_key="costs") and anomaly_gatherer
    #   (output_key="anomalies") with _specialist, a report_writer LlmAgent
    #   (instruction("report_writer"), output_key="report"), and return
    #   Workflow(name="monthly_report", edges=[(START, (gatherer_a, gatherer_b), JoinNode(name="gathered"), writer)])
    raise NotImplementedError
