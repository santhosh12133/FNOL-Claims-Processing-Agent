"""Orchestrate extraction, validation, routing, and claim metrics."""
from pathlib import Path

from .extractor import extract_fields, read_text_from_file
from .metrics import build_claim_metrics
from .router import classify_and_route
from .validator import find_inconsistencies, find_missing_fields


def process_text(text: str, source_name: str = "pasted-input.txt") -> dict:
    """Run the full FNOL pipeline on raw text and return a reviewer-friendly result."""
    extracted = extract_fields(text)
    missing_fields = find_missing_fields(extracted)
    inconsistencies = find_inconsistencies(extracted)
    routing = classify_and_route(extracted, missing_fields)

    reasoning = routing["reasoning"]
    if inconsistencies and not missing_fields:
        reasoning += " Additional data-quality notes: " + " ".join(inconsistencies)

    result = {
        "sourceFile": source_name,
        "extractedFields": extracted,
        "missingFields": missing_fields,
        "inconsistencies": inconsistencies,
        "recommendedRoute": routing["recommendedRoute"],
        "reasoning": reasoning,
        "riskSignals": routing.get("riskSignals", []),
    }
    result["processingMetrics"] = build_claim_metrics(
        extracted, missing_fields, inconsistencies, routing
    )
    return result


def process_document(filepath: str) -> dict:
    """Run the full pipeline on a single FNOL document (.txt or .pdf)."""
    text = read_text_from_file(filepath)
    return process_text(text, source_name=Path(filepath).name)
