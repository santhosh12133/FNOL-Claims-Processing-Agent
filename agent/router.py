"""
router.py
---------
Applies the four routing rules from the assessment brief, in a deliberate
priority order, and returns both the recommended route and a plain-English
explanation of why.
"""
import re

from .extractor import flatten_extracted

FRAUD_KEYWORDS = ["fraud", "inconsistent", "staged"]
FAST_TRACK_THRESHOLD = 25000.0

ROUTES = {
    "MANUAL_REVIEW": "Manual Review",
    "INVESTIGATION_FLAG": "Investigation Flag",
    "SPECIALIST_QUEUE": "Specialist Queue",
    "FAST_TRACK": "Fast-Track",
    "STANDARD_REVIEW": "Standard Review",
}


def _parse_money(value):
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _fraud_keyword_hits(description: str) -> list:
    if not description:
        return []
    lowered = description.lower()
    return [kw for kw in FRAUD_KEYWORDS if kw in lowered]


def classify_and_route(extracted: dict, missing_fields: list) -> dict:
    """
    Priority order (highest to lowest):
      1. Missing mandatory field(s)                  -> Manual Review
      2. Fraud-indicator keywords in the description  -> Investigation Flag
      3. Claim type = injury                          -> Specialist Queue
      4. Estimated damage < $25,000                   -> Fast-Track
      5. Otherwise                                     -> Standard Review

    Why this order: a claim can't be safely auto-processed at all if
    required data is missing, so that gate runs first. Suspected fraud is
    checked next because it should override convenience routing — a small,
    cheap claim that looks staged still needs a human, not a fast-track
    rubber stamp. Injury claims are routed to specialists ahead of the
    dollar-amount check because bodily-injury exposure isn't well captured
    by a repair-cost threshold. Only after those three "safety" checks does
    the dollar amount decide between Fast-Track and Standard Review.
    """
    flat = flatten_extracted(extracted)

    if missing_fields:
        return {
            "recommendedRoute": ROUTES["MANUAL_REVIEW"],
            "reasoning": (
                "Routed to Manual Review: the following mandatory field(s) could not "
                f"be found in the document: {', '.join(missing_fields)}. A claim can't "
                "be safely auto-processed with incomplete core data."
            ),
        }

    fraud_hits = _fraud_keyword_hits(flat.get("description"))
    if fraud_hits:
        return {
            "recommendedRoute": ROUTES["INVESTIGATION_FLAG"],
            "reasoning": (
                "Routed to Investigation Flag: the incident description contains "
                f"fraud-indicator keyword(s) [{', '.join(fraud_hits)}]. This overrides "
                "dollar-amount-based routing since suspected fraud needs human review "
                "regardless of claim size."
            ),
        }

    claim_type = (flat.get("claimType") or "").strip().lower()
    if claim_type == "injury":
        return {
            "recommendedRoute": ROUTES["SPECIALIST_QUEUE"],
            "reasoning": (
                "Routed to Specialist Queue: claim type is 'Injury'. Bodily injury "
                "claims carry medical/liability exposure that warrants specialist "
                "handling regardless of the damage estimate."
            ),
        }

    damage = _parse_money(flat.get("estimatedDamage"))
    if damage is not None and damage < FAST_TRACK_THRESHOLD:
        return {
            "recommendedRoute": ROUTES["FAST_TRACK"],
            "reasoning": (
                f"Routed to Fast-Track: estimated damage (${damage:,.2f}) is below the "
                f"${FAST_TRACK_THRESHOLD:,.0f} threshold, with no missing fields, fraud "
                "indicators, or injury claim type detected."
            ),
        }

    return {
        "recommendedRoute": ROUTES["STANDARD_REVIEW"],
        "reasoning": (
            "Routed to Standard Review: the claim didn't meet the criteria for "
            f"Fast-Track (damage at/above ${FAST_TRACK_THRESHOLD:,.0f}), Specialist "
            "Queue, Manual Review, or Investigation Flag, so it goes to a standard "
            "adjuster queue."
        ),
    }
