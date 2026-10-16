"""Is "85% sure" right 85% of the time? Metrics for probabilistic decisions.

- Brier score: mean squared error of the probability (0 is perfect; always saying 0.5 scores 0.25).
- Expected calibration error (ECE): bucket the predictions by probability and
  compare each bucket's average prediction with how often it was actually true.
- Selective accuracy: accuracy on the cases the policy *acted* on, and the share
  it handed to people. Raising the threshold trades coverage for accuracy.
"""

from __future__ import annotations

from collections.abc import Sequence


def brier(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float:
    return sum((p - float(o)) ** 2 for p, o in zip(probabilities, outcomes, strict=True)) / len(outcomes)


def expected_calibration_error(probabilities: Sequence[float], outcomes: Sequence[bool], bins: int = 5) -> float:
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for p, o in zip(probabilities, outcomes, strict=True):
        buckets[min(int(p * bins), bins - 1)].append((p, o))
    total = len(outcomes)
    return sum(
        len(b) / total * abs(sum(p for p, _ in b) / len(b) - sum(o for _, o in b) / len(b))
        for b in buckets if b
    )


def selective(probabilities: Sequence[float], outcomes: Sequence[bool], low: float, high: float) -> dict[str, float]:
    """Decide automatically outside [low, high], defer inside. Returns coverage and accuracy when deciding."""
    decided = [(p >= high, o) for p, o in zip(probabilities, outcomes, strict=True) if p < low or p >= high]
    coverage = len(decided) / len(outcomes)
    accuracy = sum(pred == o for pred, o in decided) / len(decided) if decided else float("nan")
    return {"coverage": round(coverage, 3), "accuracy": round(accuracy, 3)}
