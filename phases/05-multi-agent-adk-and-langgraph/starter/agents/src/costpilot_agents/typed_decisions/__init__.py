"""Typed decisions (Lab 5.9): anomaly triage with calibrated probabilities.

An agent writes; a *decision* picks from a closed set. When CostPilot finds a
cost anomaly, three decisions follow: is it a real problem, what kind, how
urgent. Asking a chat LLM for those returns text that we parse, plus a
"confidence" the model makes up. A classifier such as TypeSafe AI's Jev returns
a probability for every option, so the code can act when it is sure, ask a
human when it is not, and measure whether "90% sure" really means 90%.

    case ──► decider (mock | jev | llm) ──► Triage ──► policy ──► dismiss | notify | review | propose_ticket
                                                                                         │
                                                                     human approval ◄────┘ (graph.py)
"""

from .models import AnomalyCase, Triage
from .policy import Route, TriagePolicy, route

__all__ = ["AnomalyCase", "Route", "Triage", "TriagePolicy", "route"]
