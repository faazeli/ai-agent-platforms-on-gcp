"""The monthly report as an explicit LangGraph state machine.

    START → gather → write → review ─(passed, or 2 revisions used)→ approve → END
                       ▲        │
                       └─ fail ─┘

Compared with the ADK SequentialAgent version, everything here is explicit:
typed state, a bounded revision loop, a checkpoint after every step (so a
crashed run resumes where it stopped), and a human approval pause via
``interrupt``. The nodes' work is injected (``ReportDeps``) so the graph is
tested offline and wired to the gateway and MCP tools in ``live.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

MAX_REVISIONS = 2


class ReportState(TypedDict, total=False):
    team_id: str
    month: str
    facts: dict[str, Any]
    draft: str
    feedback: str
    review_passed: bool
    revisions: int
    decision: Literal["approved", "rejected"]


@dataclass
class Review:
    passed: bool
    feedback: str = ""


@dataclass
class ReportDeps:
    gather: Callable[[str, str], Awaitable[dict[str, Any]]]
    write: Callable[[ReportState], Awaitable[str]]
    review: Callable[[ReportState], Awaitable[Review]]


def build_report_graph(deps: ReportDeps, checkpointer: Any):
    async def gather(state: ReportState) -> ReportState:
        return {"facts": await deps.gather(state["team_id"], state["month"]), "revisions": 0}

    async def write(state: ReportState) -> ReportState:
        return {"draft": await deps.write(state), "revisions": state.get("revisions", 0) + 1}

    async def review(state: ReportState) -> ReportState:
        result = await deps.review(state)
        return {"review_passed": result.passed, "feedback": result.feedback}

    def approve(state: ReportState) -> ReportState:
        # Pauses the run and surfaces the draft. The caller resumes the same thread
        # with Command(resume="approved" | "rejected"), possibly hours later.
        decision = interrupt({"draft": state["draft"], "revisions": state["revisions"]})
        return {"decision": "approved" if decision == "approved" else "rejected"}

    def after_review(state: ReportState) -> str:
        if state["review_passed"] or state["revisions"] >= MAX_REVISIONS:
            return "approve"
        return "write"

    # TODO Lab 5.7: assemble the graph:
    #   StateGraph(ReportState); add the four nodes; edges START→gather→write→review;
    #   add_conditional_edges("review", after_review, ["write", "approve"]); approve→END;
    #   return graph.compile(checkpointer=checkpointer)
    raise NotImplementedError
