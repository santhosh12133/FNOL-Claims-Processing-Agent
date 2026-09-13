"""
validator.py
------------
Performs explainable FNOL data-quality checks before routing:
- missing required fields
- malformed dates and amounts
- future loss dates
- policy-period mismatches
- invalid/non-positive financial values
- unsupported claim types
- basic cross-field estimate consistency
"""
import re
from datetime import datetime

from .extractor import MANDATORY_FIELDS, flatten_extracted

_DATE_FORMATS = [
    "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d",
    "%B %d, %Y", "%b %d, %Y",
]
_VALID_CLAIM_TYPES = {
    "collision", "injury", "theft", "property damage", "comprehensive", "liability",
}
_CLAIM_TYPE_ALIASES = {
    "auto collision": "collision",
    "vehicle collision": "collision",
    "car accident": "collision",
    "bodily injury": "injury",
    "property-damage": "property damage",
}
_EMPTY_VALUES = {"", "n/a", "n.a.", "na", "none", "-", "--", "unknown", "tbd", "nil", "null"}


def _parse_date(value):
    if not value:
        return None
    value = value.strip()
    # Ignore common prefixes such as "From" / "To" when this helper is used
    # against an individual date.
    value = re.sub(r"^(from|to)\s+", "", value, flags=re.IGNORECASE)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_money(value):
    """Parse common USD-style amounts without silently accepting malformed data."""
    if value is None:
        return None
    raw = str(value).strip()
    if raw.lower() in _EMPTY_VALUES:
        return None

    # Accept $1,234.56, USD 1234.56, or 1234.56; reject multiple decimals.
    cleaned = re.sub(r"(?i)\busd\b", "", raw)
    cleaned = cleaned.replace(",", "").replace("$", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_claim_type(value):
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return _CLAIM_TYPE_ALIASES.get(normalized, normalized)


def find_missing_fields(extracted: dict) -> list:
    """Return required fields that are absent, blank, or placeholder values."""
    flat = flatten_extracted(extracted)
    missing = []
    for key in MANDATORY_FIELDS:
        value = flat.get(key)
        if value is None or not str(value).strip() or str(value).strip().lower() in _EMPTY_VALUES:
            missing.append(key)
    return missing


def _extract_policy_bounds(value):
    if not value:
        return None
    # Supports numeric and written dates, e.g. 01/01/2026 - 01/01/2027.
    candidates = re.findall(
        r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|[A-Za-z]+\s+\d{1,2},\s+\d{4})",
        value,
    )
    parsed = [_parse_date(item) for item in candidates]
    parsed = [item for item in parsed if item]
    return sorted(parsed[:2]) if len(parsed) >= 2 else None


def find_inconsistencies(extracted: dict) -> list:
    """Return human-readable data-quality issues found in the extracted fields."""
    flat = flatten_extracted(extracted)
    issues = []

    # Date validation.
    date_raw = flat.get("date")
    loss_date = _parse_date(date_raw)
    if date_raw and loss_date is None:
        issues.append(f"Date of loss '{date_raw}' is not in a recognized date format.")
    elif loss_date and loss_date > datetime.now():
        issues.append(f"Date of loss '{date_raw}' is in the future.")

    # Financial validation.
    damage_raw = flat.get("estimatedDamage")
    damage = _parse_money(damage_raw)
    if damage_raw and damage is None:
        issues.append(f"Estimated damage '{damage_raw}' is not a parsable amount.")
    elif damage is not None and damage <= 0:
        issues.append("Estimated damage must be greater than zero.")

    estimate_raw = flat.get("initialEstimate")
    estimate = _parse_money(estimate_raw)
    if estimate_raw and estimate is None:
        issues.append(f"Initial estimate '{estimate_raw}' is not a parsable amount.")
    elif estimate is not None and estimate <= 0:
        issues.append("Initial estimate must be greater than zero.")

    if damage is not None and estimate is not None:
        # A very large discrepancy is useful to surface for human review while
        # avoiding a hard-coded routing decision that was not in the brief.
        larger = max(damage, estimate)
        smaller = min(damage, estimate)
        if smaller > 0 and larger / smaller >= 5:
            issues.append(
                f"Estimated damage (${damage:,.2f}) and initial estimate (${estimate:,.2f}) "
                "differ by a factor of 5 or more."
            )

    # Policy coverage validation.
    effective_dates = flat.get("effectiveDates")
    bounds = _extract_policy_bounds(effective_dates)
    if effective_dates and loss_date and bounds:
        start, end = bounds
        if not (start <= loss_date <= end):
            issues.append(
                f"Date of loss '{date_raw}' falls outside the policy effective period "
                f"'{effective_dates}'."
            )
    elif effective_dates and loss_date and not bounds:
        issues.append(f"Policy effective dates '{effective_dates}' could not be parsed.")

    # Claim type validation with a small set of common aliases.
    claim_type_raw = flat.get("claimType")
    claim_type = _normalize_claim_type(claim_type_raw)
    if claim_type and claim_type not in _VALID_CLAIM_TYPES:
        issues.append(
            f"Claim type '{claim_type_raw}' is not one of the recognized types "
            f"({', '.join(sorted(_VALID_CLAIM_TYPES))})."
        )

    return issues
