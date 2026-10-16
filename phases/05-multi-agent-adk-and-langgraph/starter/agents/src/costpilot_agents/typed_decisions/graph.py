"""Anomaly triage as a LangGraph flow, with the approval gate from Lab 5.7.

    START → decide → route ─┬─ dismiss ─────────────────────────────► log → END
                            ├─ notify ──────────────────────────────► log → END
                            ├─ review ── interrupt: a person labels it ┐
                            └─ propose ─ interrupt: approve the ticket ┴► (ticket) → log → END

Only a person's resume value creates a ticket, whatever the probabilities say.
Every run ends in the decision log: the probabilities, the route, the policy
version and, for reviewed cases, the person's answer. Those answers are your
labels: re-run ``run_eval`` on them monthly to see whether the decider is still
calibrated on *your* data.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .. import tickets
from .deciders import Decider
from .models import AnomalyCase, Triage
from .policy import TriagePolicy, route


class TriageState(TypedDict, total=False):
    case: dict[str, Any]
    triage: dict[str, Any]
    route: dict[str, Any]
    human: dict[str, Any]
    ticket: dict[str, Any] | None


def draft_ticket(case: AnomalyCase, triage: dict[str, Any]) -> dict[str, Any]:
    excess = float(case.effective_cost - case.trailing_mean)
    return {
        "team_id": case.team_id,
        "title": f"Cost anomaly {case.day}: {triage['category'].replace('_', ' ')} (+${excess:,.0f}/day)"[:120],
        "estimated_monthly_savings": round(excess * 30, 2),
    }


def build_triage_graph(decider: Decider, policy: TriagePolicy, checkpointer: Any,
                       log: Callable[[dict[str, Any]], None], proposals_today: Callable[[], int] = lambda: 0):
    async def decide(state: TriageState) -> TriageState:
        triage = await decider.decide(AnomalyCase.model_validate(state["case"]))
        return {"triage": asdict(triage)}

    def choose(state: TriageState) -> TriageState:
        r = route(Triage(**state["triage"]), policy, proposals_today())
        return {"route": asdict(r)}

    def review(state: TriageState) -> TriageState:
        case = AnomalyCase.model_validate(state["case"])
        answer = interrupt({
            "ask": "The decider is unsure. Is this a real problem, and if so, create this ticket?",
            "reason": state["route"]["reason"],
            "probabilities": {"real": state["triage"]["p_real"], "category": state["triage"]["category_probabilities"]},
            "ticket": draft_ticket(case, state["triage"]),
        })
        # resume with {"real": bool, "category": str | None, "create_ticket": bool}
        return {"human": dict(answer)}

    def propose(state: TriageState) -> TriageState:
        case = AnomalyCase.model_validate(state["case"])
        ticket = draft_ticket(case, state["triage"])
        answer = interrupt({"ask": "Approve this ticket exactly as shown?", "ticket": ticket,
                            "page": state["route"]["page"], "reason": state["route"]["reason"]})
        approved = answer == "approved"
        # An approval confirms the decider was right; a rejection is a label too.
        return {"human": {"real": approved, "category": None, "create_ticket": approved}}

    def act(state: TriageState) -> TriageState:
        human = state.get("human") or {}
        if not human.get("create_ticket"):
            return {"ticket": None}
        case = AnomalyCase.model_validate(state["case"])
        return {"ticket": tickets.create_savings_ticket(**draft_ticket(case, state["triage"]))}

    def write_log(state: TriageState) -> TriageState:
        t, r = state["triage"], state["route"]
        log({
            "ts": time.time(), "case_id": state["case"]["case_id"], "team_id": state["case"]["team_id"],
            "decider": t["decider"], "p_real": t["p_real"], "category": t["category"],
            "category_confidence": t["category_confidence"], "urgency": t["urgency"],
            "latency_ms": round(t["latency_ms"], 1), "route": r["kind"], "page": r["page"],
            "policy_version": r["policy_version"], "human": state.get("human"),
            "ticket_id": (state.get("ticket") or {}).get("ticket_id"),
        })
        return {}

    graph = StateGraph(TriageState)
    for name, fn in [("decide", decide), ("choose", choose), ("review", review), ("propose", propose),
                     ("act", act), ("log", write_log)]:
        graph.add_node(name, fn)
    graph.add_edge(START, "decide")
    graph.add_edge("decide", "choose")
    graph.add_conditional_edges("choose", lambda s: {"dismiss": "log", "notify": "log", "review": "review",
                                                     "propose_ticket": "propose"}[s["route"]["kind"]],
                                ["log", "review", "propose"])
    graph.add_edge("review", "act")
    graph.add_edge("propose", "act")
    graph.add_edge("act", "log")
    graph.add_edge("log", END)
    return graph.compile(checkpointer=checkpointer)
