"""A stand-in ticketing system: the one *write* action in CostPilot.

In a real deployment this would call Jira or ServiceNow. It exists so the
course has a state-changing tool to put behind an approval gate.
"""

from __future__ import annotations

import itertools
from typing import Annotated

from pydantic import Field

CREATED: list[dict] = []
_ids = itertools.count(1001)


def create_savings_ticket(
    team_id: Annotated[str, Field(pattern=r"^[a-z0-9-]{2,40}$")],
    title: Annotated[str, Field(max_length=120)],
    estimated_monthly_savings: float,
) -> dict:
    """Open a ticket asking a team to act on a cost-saving recommendation.
    This CHANGES an external system and requires human approval of the exact arguments."""
    ticket = {"ticket_id": f"FIN-{next(_ids)}", "team_id": team_id, "title": title,
              "estimated_monthly_savings": estimated_monthly_savings}
    CREATED.append(ticket)
    return {"status": "created", **ticket}
