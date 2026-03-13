from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AlertDecision:
    should_alert: bool
    priority: Optional[str] = None
    reason: Optional[str] = None


HIGH_PRIORITY_LABELS = {
    "request_rescue",
    "medical_emergency",
}

MEDIUM_PRIORITY_LABELS = {
    "missing_person",
    "infrastructure_damage",
    "flooding",
}


def decide_alert(predicted_label: str, predicted_proba: float | None) -> AlertDecision:
    label = (predicted_label or "").strip().lower()
    proba = predicted_proba if predicted_proba is not None else 0.0

    # Only trigger high-priority alerts for high-confidence predictions.
    if label in HIGH_PRIORITY_LABELS and proba >= 0.70:
        return AlertDecision(True, "high", f"label={label}, proba>={0.70}")

    # Only trigger medium-priority alerts for reasonably confident predictions.
    if label in MEDIUM_PRIORITY_LABELS and proba >= 0.65:
        return AlertDecision(True, "medium", f"label={label}, proba>={0.65}")

    return AlertDecision(False)

