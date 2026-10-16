"""From probabilities to actions: the part YOU own, versioned and reviewed like a prompt.

The decider estimates; the policy decides. Thresholds express how much each
mistake costs: a missed runaway cluster costs money every hour, a false alarm
costs an engineer's attention. When the decider is unsure, the right action is
to ask a person, and that is only possible when "unsure" is a number you trust.

Nothing here creates a ticket. ``propose_ticket`` routes to the human approval
gate (graph.py), exactly like every other write action in CostPilot (Lab 5.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from .models import Triage

RouteKind = Literal["dismiss", "notify", "review", "propose_ticket"]


class TriagePolicy(BaseModel):
    version: str = "2026-10-1"
    dismiss_below: float = Field(0.15, description="P(real) under this: log it, tell nobody")
    act_above: float = Field(0.85, description="P(real) over this: propose a ticket")
    min_category_confidence: float = Field(0.6, description="Below this, a human labels the cause first")
    page_at_urgency: float = Field(2.5, description="Expected urgency at or above this: page the owning team")
    max_proposals_per_day: int = Field(20, description="Like a position cap: a burst of proposals means something upstream broke")


@dataclass
class Route:
    kind: RouteKind
    reason: str
    page: bool = False
    policy_version: str = ""
    flags: list[str] = field(default_factory=list)


def route(triage: Triage, policy: TriagePolicy, proposals_today: int = 0) -> Route:
    v = policy.version
    if triage.notes and any(n.startswith(("late:", "error:")) for n in triage.notes):
        return Route("review", f"no reliable decision ({triage.notes[0]})", policy_version=v)
    if triage.p_real < policy.dismiss_below:
        return Route("dismiss", f"P(real)={triage.p_real:.2f} < {policy.dismiss_below}", policy_version=v)
    if triage.p_real < policy.act_above:
        return Route("review", f"unsure: P(real)={triage.p_real:.2f}", policy_version=v)
    if triage.category_confidence < policy.min_category_confidence:
        return Route("review", f"real, but cause unclear: P({triage.category})={triage.category_confidence:.2f}",
                     policy_version=v)
    page = triage.urgency >= policy.page_at_urgency
    if proposals_today >= policy.max_proposals_per_day:
        return Route("notify", "daily proposal budget used: notify only", page=page, policy_version=v,
                     flags=["proposal_budget_exhausted"])
    return Route("propose_ticket", f"P(real)={triage.p_real:.2f}, {triage.category}", page=page, policy_version=v)
