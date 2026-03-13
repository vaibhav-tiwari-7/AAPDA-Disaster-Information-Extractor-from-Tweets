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
}


def decide_alert(predicted_label: str, predicted_proba: float | None) -> AlertDecision:
    label = (predicted_label or "").strip().lower()
    proba = predicted_proba if predicted_proba is not None else 0.0

    if label in HIGH_PRIORITY_LABELS and proba >= 0.40:
        return AlertDecision(True, "high", f"label={label}, proba>={0.40}")
    if label in HIGH_PRIORITY_LABELS:
        return AlertDecision(True, "high", f"label={label} (low confidence)")

    if label in MEDIUM_PRIORITY_LABELS and proba >= 0.45:
        return AlertDecision(True, "medium", f"label={label}, proba>={0.45}")

    return AlertDecision(False)

