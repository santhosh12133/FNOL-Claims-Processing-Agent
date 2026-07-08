"""
pipeline.py
-----------
Ties extraction, validation, and routing together and shapes the final
output to match the JSON format required by the assessment brief
(extractedFields / missingFields / recommendedRoute / reasoning), with one
addition: an "inconsistencies" list surfacing data-quality notes that don't
block routing on their own (see validator.py and README.md).
"""
from pathlib import Path

from .extractor import extract_fields, read_text_from_file
from .router import classify_and_route
from .validator import find_inconsistencies, find_missing_fields


def process_text(text: str, source_name: str = "pasted-input.txt") -> dict:
    """
    Run the full pipeline on raw text you already have in memory (e.g. pasted
    into a web form) rather than a file on disk.
    """
    extracted = extract_fields(text)
    missing_fields = find_missing_fields(extracted)
    inconsistencies = find_inconsistencies(extracted)
    routing = classify_and_route(extracted, missing_fields)

    reasoning = routing["reasoning"]
    if inconsistencies and not missing_fields:
        # If missing fields already decided the route, that reasoning stands on
        # its own. Otherwise, append data-quality notes for the human reviewer.
        reasoning += " Additional data-quality notes: " + " ".join(inconsistencies)

    return {
        "sourceFile": source_name,
        "extractedFields": extracted,
        "missingFields": missing_fields,
        "inconsistencies": inconsistencies,
        "recommendedRoute": routing["recommendedRoute"],
        "reasoning": reasoning,
    }


def process_document(filepath: str) -> dict:
    """Run the full pipeline on a single FNOL document (.txt or .pdf) and return the result dict."""
    text = read_text_from_file(filepath)
    return process_text(text, source_name=Path(filepath).name)
