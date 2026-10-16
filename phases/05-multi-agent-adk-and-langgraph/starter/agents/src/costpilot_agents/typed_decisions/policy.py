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
    # TODO (Lab 5.9, step 3): turn probabilities into one of four routes. In this order:
    #   1. a late or failed decision (triage.notes starts with "late:" or "error:") -> review
    #   2. p_real <  dismiss_below                          -> dismiss
    #   3. p_real <  act_above                              -> review   (unsure: ask a person)
    #   4. category_confidence < min_category_confidence    -> review   (real, cause unclear)
    #   5. proposals_today >= max_proposals_per_day         -> notify, flag "proposal_budget_exhausted"
    #   6. otherwise                                        -> propose_ticket
    # Set page=True when triage.urgency >= page_at_urgency, and always set policy_version.
    raise NotImplementedError("Lab 5.9: write the routing policy")
