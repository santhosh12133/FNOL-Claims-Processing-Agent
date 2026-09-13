"""Explainable, deterministic FNOL routing with safety-first gates."""
import re
from typing import Any

from .extractor import flatten_extracted

FRAUD_KEYWORDS = ("fraud", "fraudulent", "staged", "inconsistent", "fabricated", "fake")
INJURY_TYPES = {"injury", "bodily injury", "personal injury"}
FAST_TRACK_THRESHOLD = 25_000.0
ROUTES = {
    "MANUAL_REVIEW": "Manual Review",
    "INVESTIGATION_FLAG": "Investigation Flag",
    "SPECIALIST_QUEUE": "Specialist Queue",
    "FAST_TRACK": "Fast-Track",
    "STANDARD_REVIEW": "Standard Review",
}


def _parse_money(value: Any):
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _fraud_keyword_hits(description: Any) -> list[str]:
    if not description:
        return []
    lowered = str(description).lower()
    return [kw for kw in FRAUD_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", lowered)]


def _normalise_claim_type(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def classify_and_route(extracted: dict, missing_fields: list) -> dict:
    """Classify a claim using deterministic safety-first routing rules.

    Returns the route, human-readable reasoning, and structured risk signals.
    """
    flat = flatten_extracted(extracted)
    signals = []

    # Incomplete core data must never be auto-routed.
    if missing_fields:
        signals.append({"code": "MISSING_DATA", "severity": "high", "details": list(missing_fields)})
        return {"recommendedRoute": ROUTES["MANUAL_REVIEW"], "reasoning": f"Manual Review is required because mandatory field(s) are missing: {', '.join(missing_fields)}.", "riskSignals": signals}

    # Explicit fraud language overrides convenience routing.
    fraud_hits = _fraud_keyword_hits(flat.get("description"))
    if fraud_hits:
        signals.append({"code": "FRAUD_INDICATOR", "severity": "critical", "details": fraud_hits})
        return {"recommendedRoute": ROUTES["INVESTIGATION_FLAG"], "reasoning": f"Investigation Flag is recommended because the incident description contains fraud-indicator term(s): {', '.join(fraud_hits)}.", "riskSignals": signals}

    # Injury exposure requires specialist handling regardless of repair cost.
    claim_type = _normalise_claim_type(flat.get("claimType"))
    if claim_type in INJURY_TYPES:
        signals.append({"code": "INJURY_EXPOSURE", "severity": "high", "details": [claim_type]})
        return {"recommendedRoute": ROUTES["SPECIALIST_QUEUE"], "reasoning": "Specialist Queue is recommended because the claim involves bodily injury, which may require medical and liability review.", "riskSignals": signals}

    # Never apply the amount threshold to an invalid amount.
    damage = _parse_money(flat.get("estimatedDamage"))
    if damage is None or damage < 0:
        signals.append({"code": "INVALID_DAMAGE", "severity": "high", "details": [flat.get("estimatedDamage")]})
        return {"recommendedRoute": ROUTES["MANUAL_REVIEW"], "reasoning": "Manual Review is required because the estimated damage cannot be reliably evaluated.", "riskSignals": signals}

    if damage == 0:
        signals.append({"code": "ZERO_DAMAGE", "severity": "medium", "details": [damage]})
        return {"recommendedRoute": ROUTES["MANUAL_REVIEW"], "reasoning": "Manual Review is recommended because the estimated damage is $0.00 and needs confirmation.", "riskSignals": signals}

    if damage < FAST_TRACK_THRESHOLD:
        signals.append({"code": "LOW_DAMAGE", "severity": "low", "details": [damage]})
        return {"recommendedRoute": ROUTES["FAST_TRACK"], "reasoning": f"Fast-Track is recommended because estimated damage (${damage:,.2f}) is below the ${FAST_TRACK_THRESHOLD:,.0f} threshold and no higher-priority risk signal was found.", "riskSignals": signals}

    signals.append({"code": "ABOVE_FAST_TRACK_THRESHOLD", "severity": "medium", "details": [damage]})
    return {"recommendedRoute": ROUTES["STANDARD_REVIEW"], "reasoning": f"Standard Review is recommended because estimated damage (${damage:,.2f}) is at or above the ${FAST_TRACK_THRESHOLD:,.0f} Fast-Track threshold and no higher-priority risk was found.", "riskSignals": signals}
