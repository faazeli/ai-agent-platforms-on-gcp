"""Trailing z-score anomaly detection: the same idea as Phase 2's q06, in Python.

A day is anomalous when its cost is more than ``threshold`` standard deviations
above the mean of the previous ``lookback`` days. Simple, explainable, and good
enough to point a human (or an agent) at the right day.
"""

from __future__ import annotations

from decimal import Decimal
from statistics import mean, stdev

from .models import Anomaly, DailyCost


def find_anomalies(series: list[DailyCost], threshold: float = 3.0, lookback: int = 7) -> list[Anomaly]:
    costs = [float(d.effective_cost) for d in series]
    found: list[Anomaly] = []
    for i in range(lookback, len(series)):
        window = costs[i - lookback: i]
        sd = stdev(window)
        if sd == 0:
            continue
        avg = mean(window)
        z = (costs[i] - avg) / sd
        if z > threshold:
            found.append(Anomaly(
                day=series[i].day,
                effective_cost=series[i].effective_cost,
                trailing_mean=Decimal(str(round(avg, 4))),
                z_score=round(z, 2),
            ))
    return sorted(found, key=lambda a: a.z_score, reverse=True)
