"""
Test suite for the FNOL Claims Processing Agent.

Run with: pytest -v
"""
from pathlib import Path

import pytest

from agent.extractor import extract_fields, flatten_extracted
from agent.pipeline import process_document
from agent.router import classify_and_route
from agent.validator import find_inconsistencies, find_missing_fields

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_docs"

CLEAN_DOC = """
Policy Number: PA-0001-2026
Policyholder Name: Test Person
Effective Dates: 01/01/2026 - 01/01/2027

Date of Loss: 06/01/2026
Time of Loss: 10:00 AM
Location of Loss: 1 Test St, Testville, TS
Description of Accident: A minor fender bender in a parking lot.

Claimant: Test Person
Third Parties: None
Contact Details: test@example.com

Asset Type: Sedan
Asset ID: 1TEST0000000000000
Estimated Damage: $500.00

Claim Type: Collision
Attachments: photo.jpg
Initial Estimate: $500.00
"""


# ---------- extractor ----------

def test_extracts_all_expected_fields():
    extracted = extract_fields(CLEAN_DOC)
    flat = flatten_extracted(extracted)
    assert flat["policyNumber"] == "PA-0001-2026"
    assert flat["policyholderName"] == "Test Person"
    assert flat["estimatedDamage"] == "$500.00"
    assert flat["claimType"] == "Collision"


def test_missing_field_becomes_none():
    text_without_policy_number = CLEAN_DOC.replace("Policy Number: PA-0001-2026\n", "")
    extracted = extract_fields(text_without_policy_number)
    flat = flatten_extracted(extracted)
    assert flat["policyNumber"] is None


def test_placeholder_values_normalize_to_none():
    text = CLEAN_DOC.replace("Third Parties: None", "Third Parties: N/A")
    extracted = extract_fields(text)
    flat = flatten_extracted(extracted)
    assert flat["thirdParties"] is None


def test_multiline_description_is_captured_in_full():
    text = CLEAN_DOC.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: A minor fender bender\nin a parking lot near the entrance.",
    )
    extracted = extract_fields(text)
    flat = flatten_extracted(extracted)
    assert "parking lot near the entrance" in flat["description"]


# ---------- validator ----------

def test_find_missing_fields_flags_absent_mandatory_field():
    extracted = extract_fields(CLEAN_DOC.replace("Policy Number: PA-0001-2026\n", ""))
    missing = find_missing_fields(extracted)
    assert "policyNumber" in missing


def test_find_missing_fields_empty_when_all_present():
    extracted = extract_fields(CLEAN_DOC)
    assert find_missing_fields(extracted) == []


def test_inconsistent_dates_detected():
    text = CLEAN_DOC.replace(
        "Effective Dates: 01/01/2026 - 01/01/2027", "Effective Dates: 01/01/2024 - 01/01/2025"
    )
    extracted = extract_fields(text)
    issues = find_inconsistencies(extracted)
    assert any("effective period" in issue for issue in issues)


def test_non_numeric_damage_flagged():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: totaled")
    extracted = extract_fields(text)
    issues = find_inconsistencies(extracted)
    assert any("not a parsable amount" in issue for issue in issues)


# ---------- router ----------

def test_fast_track_when_clean_and_under_threshold():
    extracted = extract_fields(CLEAN_DOC)
    result = classify_and_route(extracted, missing_fields=[])
    assert result["recommendedRoute"] == "Fast-Track"


def test_manual_review_when_fields_missing_even_if_otherwise_fast_track():
    extracted = extract_fields(CLEAN_DOC)
    result = classify_and_route(extracted, missing_fields=["policyNumber"])
    assert result["recommendedRoute"] == "Manual Review"


def test_investigation_flag_on_fraud_keyword():
    text = CLEAN_DOC.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: Damage appears staged and inconsistent with the report.",
    )
    extracted = extract_fields(text)
    result = classify_and_route(extracted, missing_fields=[])
    assert result["recommendedRoute"] == "Investigation Flag"


def test_specialist_queue_for_injury_claim_type():
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Injury")
    extracted = extract_fields(text)
    result = classify_and_route(extracted, missing_fields=[])
    assert result["recommendedRoute"] == "Specialist Queue"


def test_standard_review_above_threshold():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: $30,000.00")
    extracted = extract_fields(text)
    result = classify_and_route(extracted, missing_fields=[])
    assert result["recommendedRoute"] == "Standard Review"


def test_precedence_missing_field_beats_everything_else():
    """
    A doc with a fraud keyword AND injury claim type AND low damage should
    still route to Manual Review if a mandatory field is missing -- missing
    data is the highest-priority gate.
    """
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Injury")
    text = text.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: Looks staged and inconsistent with the story.",
    )
    text = text.replace("Policy Number: PA-0001-2026\n", "")  # remove a mandatory field
    extracted = extract_fields(text)
    missing = find_missing_fields(extracted)
    result = classify_and_route(extracted, missing)
    assert result["recommendedRoute"] == "Manual Review"


# ---------- end-to-end pipeline, using the real sample_docs/ files ----------

@pytest.mark.parametrize(
    "filename,expected_route",
    [
        ("fnol_01_fast_track.txt", "Fast-Track"),
        ("fnol_02_missing_fields.txt", "Manual Review"),
        ("fnol_03_fraud_flag.txt", "Investigation Flag"),
        ("fnol_04_injury.txt", "Specialist Queue"),
        ("fnol_05_standard_review.txt", "Standard Review"),
        ("fnol_06_multiple_flags.txt", "Manual Review"),
        ("fnol_07_inconsistent_dates.txt", "Fast-Track"),
        ("fnol_08_pdf_sample.pdf", "Fast-Track"),
    ],
)
def test_sample_documents_route_as_expected(filename, expected_route):
    filepath = SAMPLE_DIR / filename
    result = process_document(str(filepath))
    assert result["recommendedRoute"] == expected_route


def test_inconsistent_dates_sample_reports_the_issue_without_blocking_route():
    result = process_document(str(SAMPLE_DIR / "fnol_07_inconsistent_dates.txt"))
    assert result["recommendedRoute"] == "Fast-Track"
    assert any("effective period" in issue for issue in result["inconsistencies"])
