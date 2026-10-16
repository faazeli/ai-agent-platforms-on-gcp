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
    specialists = [
        _specialist("cost_analyst", "Answers how much a team spent and what drives it.",
                    models["cost_analyst"], tools_for, max_model_calls, audit, guardrails),
        _specialist("anomaly_detector", "Finds unusual spend spikes and likely causes.",
                    models["anomaly_detector"], tools_for, max_model_calls, audit, guardrails),
        _specialist("recommender", "Proposes savings and, with approval, opens tickets.",
                    models["recommender"], tools_for, max_model_calls, audit, guardrails),
    ]
    return LlmAgent(
        name="coordinator",
        description="Routes cost questions to specialists.",
        model=models["coordinator"],
        instruction=instruction("coordinator"),
        sub_agents=specialists,
        # The coordinator reads the user's message first, so it is screened here too.
        before_model_callback=[make_model_budget(max_model_calls, "coordinator", audit),
                               *([guardrails[0]] if guardrails else [])],
        after_model_callback=[guardrails[1]] if guardrails else None,
    )


def build_monthly_report(models: dict[str, Any], tools_for: ToolsFor, *,
                         audit: AuditFn | None = None) -> Workflow:
    """A fixed workflow for a recurring job: gather costs and anomalies in parallel,
    wait for both, then write.

        START ─┬─► cost_gatherer ───┬─► join ─► report_writer
               └─► anomaly_gatherer ┘

    No LLM decides the order here. When the steps are known in advance, a workflow
    is cheaper, faster and easier to test than letting a model route. ADK 2.x builds
    these with ``Workflow`` edges; the older SequentialAgent/ParallelAgent classes
    still work but are deprecated.

    ``models`` maps cost_gatherer, anomaly_gatherer and report_writer to models.
    Each gatherer saves its reply to session state (``output_key``), and the
    writer's instruction reads them back as {costs} and {anomalies}.
    """
    cost_gatherer = _specialist("cost_gatherer", "Collects cost facts.", models["cost_gatherer"],
                                tools_for, 6, audit, output_key="costs")
    anomaly_gatherer = _specialist("anomaly_gatherer", "Collects anomalies.", models["anomaly_gatherer"],
                                   tools_for, 4, audit, output_key="anomalies")
    writer = LlmAgent(name="report_writer", model=models["report_writer"], instruction=instruction("report_writer"),
                      output_key="report", before_model_callback=make_model_budget(2, "report_writer", audit))
    return Workflow(name="monthly_report",
                    edges=[(START, (cost_gatherer, anomaly_gatherer), JoinNode(name="gathered"), writer)])
