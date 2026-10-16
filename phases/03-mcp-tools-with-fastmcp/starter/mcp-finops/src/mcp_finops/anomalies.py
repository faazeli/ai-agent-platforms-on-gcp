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
    # TODO Lab 3.4 (a): for each day i >= lookback, compare its cost with the mean and
    #   sample standard deviation of the previous `lookback` days. Skip windows with sd == 0.
    #   Keep days with z = (cost - mean) / sd > threshold, as Anomaly objects
    #   (round z to 2 places), sorted by z_score, largest first.
    raise NotImplementedError
