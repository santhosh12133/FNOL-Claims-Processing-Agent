"""
validator.py
------------
Checks the extracted fields for two different kinds of problems:

1. Missing mandatory fields  -> blocks automatic routing (see router.py)
2. Inconsistent data         -> doesn't block routing, but is surfaced to a
   human reviewer as a data-quality note (e.g. dates that don't add up,
   damage amounts that aren't numbers, a claim type that isn't recognized).

Kept intentionally as a small, explainable rule set rather than exhaustive
validation — see README.md for the reasoning.
"""
import re
from datetime import datetime

from .extractor import MANDATORY_FIELDS, flatten_extracted

_DATE_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]
_VALID_CLAIM_TYPES = {
    "collision",
    "injury",
    "theft",
    "property damage",
    "comprehensive",
    "liability",
}


def _parse_date(value):
    if not value:
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


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


def find_missing_fields(extracted: dict) -> list:
    """Return mandatory field keys that were not found (or were empty) in the document."""
    flat = flatten_extracted(extracted)
    return [key for key in MANDATORY_FIELDS if not flat.get(key)]


def find_inconsistencies(extracted: dict) -> list:
    """Return a list of human-readable data-quality issues found in the extracted fields."""
    flat = flatten_extracted(extracted)
    issues = []

    date_raw = flat.get("date")
    loss_date = _parse_date(date_raw)
    if date_raw and loss_date is None:
        issues.append(f"Date of loss '{date_raw}' is not in a recognized date format.")
    elif loss_date and loss_date > datetime.now():
        issues.append(f"Date of loss '{date_raw}' is in the future.")

    damage_raw = flat.get("estimatedDamage")
    damage = _parse_money(damage_raw)
    if damage_raw and damage is None:
        issues.append(f"Estimated damage '{damage_raw}' is not a parsable amount.")
    elif damage is not None and damage <= 0:
        issues.append("Estimated damage is zero or negative, which is not a valid loss amount.")

    estimate_raw = flat.get("initialEstimate")
    if estimate_raw and _parse_money(estimate_raw) is None:
        issues.append(f"Initial estimate '{estimate_raw}' is not a parsable amount.")

    effective_dates = flat.get("effectiveDates")
    if effective_dates and loss_date:
        bound_strings = re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", effective_dates)
        bounds = [d for d in (_parse_date(b) for b in bound_strings) if d]
        if len(bounds) == 2:
            start, end = sorted(bounds)
            if not (start <= loss_date <= end):
                issues.append(
                    f"Date of loss '{date_raw}' falls outside the policy effective "
                    f"period '{effective_dates}'."
                )

    claim_type = (flat.get("claimType") or "").strip().lower()
    if claim_type and claim_type not in _VALID_CLAIM_TYPES:
        issues.append(
            f"Claim type '{flat.get('claimType')}' is not one of the recognized types "
            f"({', '.join(sorted(_VALID_CLAIM_TYPES))})."
        )

    return issues
