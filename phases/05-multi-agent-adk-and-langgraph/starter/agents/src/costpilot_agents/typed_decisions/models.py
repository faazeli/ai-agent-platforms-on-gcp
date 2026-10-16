"""The input (an anomaly with its context) and the output (a triage) of a decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

# The closed sets the deciders choose from. Descriptions matter: they are the
# criteria the classifier scores against, the same way tool descriptions matter in Phase 3.
CATEGORIES: dict[str, str] = {
    "usage_spike": "More of a resource was consumed than usual: traffic growth, a runaway job, a retry loop, a forgotten test cluster.",
    "untagged_spend": "New or growing spend with no owner tag, so nobody is accountable for it.",
    "commitment_purchase": "A planned charge that is not usage: a committed-use discount or reservation purchase, support fee or annual license.",
    "pricing_change": "Similar usage at a different price: a SKU change, an expired discount or credit, a move to a pricier region.",
    "expected_event": "A change announced in advance: a migration, backfill, load test or launch listed in the change calendar.",
}
URGENCY_LEVELS: list[str] = [
    "Can wait for the monthly cost review.",
    "Someone should look this week.",
    "Someone should look today.",
    "Page the owning team now: the cost keeps growing every hour.",
]


class ServiceCost(BaseModel):
    service_name: str
    charge_category: str = Field(description="FOCUS ChargeCategory: Usage, Purchase, Tax, Credit, Adjustment")
    effective_cost: Decimal
    previous_week_daily_avg: Decimal
    tagged: bool = Field(description="True when the cost carries team and service tags")


class AnomalyCase(BaseModel):
    """What Phase 3's detect_anomalies found, plus the context a person would look at."""

    case_id: str
    team_id: str
    day: date
    effective_cost: Decimal
    trailing_mean: Decimal
    z_score: float
    top_services: list[ServiceCost]
    change_calendar: list[str] = Field(default_factory=list, description="Announced changes for this team near this day")

    def as_state(self) -> dict:
        """The JSON a decider sees. No secrets, no personal data: only cost facts (see Phase 6)."""
        return self.model_dump(mode="json", exclude={"case_id"})


@dataclass(frozen=True)
class Triage:
    p_real: float                                  # P(an unplanned problem someone should act on)
    category: str
    category_confidence: float                     # probability of the chosen category
    category_probabilities: dict[str, float]
    urgency: float                                 # expected level, 0..3
    urgency_probabilities: dict[int, float]
    decider: str
    latency_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def urgency_level(self) -> int:
        return max(self.urgency_probabilities, key=self.urgency_probabilities.get) if self.urgency_probabilities \
            else round(self.urgency)
