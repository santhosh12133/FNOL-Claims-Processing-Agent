"""Derived claim-processing metrics for reviewer dashboards and API consumers."""
from typing import Any

from .extractor import flatten_extracted

# These are the fields that must be present before an automated routing decision
# can be trusted. Keep this aligned with validator.py's mandatory-field policy.
MANDATORY_FIELDS = {
    "policyNumber",
    "policyholderName",
    "date",
    "location",
    "description",
    "estimatedDamage",
    "claimType",
    "attachments",
    "initialEstimate",
}

ALL_FIELDS = {
    "policyNumber",
    "policyholderName",
    "effectiveDates",
    "date",
    "time",
    "location",
    "description",
    "claimant",
    "thirdParties",
    "contactDetails",
    "assetType",
    "assetId",
    "estimatedDamage",
    "claimType",
    "attachments",
    "initialEstimate",
}

MANUAL_ROUTES = {"Manual Review", "Investigation Flag", "Specialist Queue"}


def _present(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def build_claim_metrics(extracted: dict, missing_fields: list, inconsistencies: list, routing: dict) -> dict:
    """Build compact, explainable metrics from an already-processed claim."""
    flat = flatten_extracted(extracted)
    extracted_count = sum(1 for field in ALL_FIELDS if _present(flat.get(field)))
    mandatory_present = sum(1 for field in MANDATORY_FIELDS if _present(flat.get(field)))
    mandatory_total = len(MANDATORY_FIELDS)
    completeness = round((mandatory_present / mandatory_total) * 100, 1) if mandatory_total else 100.0

    route = routing.get("recommendedRoute", "")
    signals = routing.get("riskSignals") or []

    return {
        "mandatoryFieldCompletenessPct": completeness,
        "fieldsExtracted": extracted_count,
        "fieldsExpected": len(ALL_FIELDS),
        "missingFieldCount": len(missing_fields),
        "inconsistencyCount": len(inconsistencies),
        "riskSignalCount": len(signals),
        "automationEligible": route not in MANUAL_ROUTES,
        "recommendedRoute": route,
    }
