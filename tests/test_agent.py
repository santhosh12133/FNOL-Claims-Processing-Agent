"""
Test suite for the FNOL Claims Processing Agent.

Run with: pytest -v
"""
from pathlib import Path

import pytest

from agent.extractor import extract_fields, flatten_extracted
from agent.pipeline import process_document, process_text
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


def route(text):
    extracted = extract_fields(text)
    return classify_and_route(extracted, find_missing_fields(extracted))


# ---------- extractor ----------

def test_extracts_all_expected_fields():
    extracted = extract_fields(CLEAN_DOC)
    flat = flatten_extracted(extracted)
    assert flat["policyNumber"] == "PA-0001-2026"
    assert flat["policyholderName"] == "Test Person"
    assert flat["estimatedDamage"] == "$500.00"
    assert flat["claimType"] == "Collision"


def test_alternate_labels_are_supported():
    text = CLEAN_DOC.replace("Policy Number:", "Policy ID:")
    text = text.replace("Policyholder Name:", "Policy Holder Name:")
    text = text.replace("Date of Loss:", "Date of Incident:")
    text = text.replace("Estimated Damage:", "Estimated Repair Cost:")
    flat = flatten_extracted(extract_fields(text))
    assert flat["policyNumber"] == "PA-0001-2026"
    assert flat["policyholderName"] == "Test Person"
    assert flat["date"] == "06/01/2026"
    assert flat["estimatedDamage"] == "$500.00"


def test_colonless_and_hyphen_separated_labels_are_supported():
    text = CLEAN_DOC.replace("Policy Number:", "Policy Number ")
    text = text.replace("Claim Type:", "Claim Type -")
    flat = flatten_extracted(extract_fields(text))
    assert flat["policyNumber"] == "PA-0001-2026"
    assert flat["claimType"] == "Collision"


def test_placeholder_variants_normalize_to_none():
    for placeholder in ("N.A.", "Nil", "Not Available", "null", "--"):
        text = CLEAN_DOC.replace("Third Parties: None", f"Third Parties: {placeholder}")
        flat = flatten_extracted(extract_fields(text))
        assert flat["thirdParties"] is None


def test_missing_field_becomes_none():
    text_without_policy_number = CLEAN_DOC.replace("Policy Number: PA-0001-2026\n", "")
    extracted = extract_fields(text_without_policy_number)
    flat = flatten_extracted(extracted)
    assert flat["policyNumber"] is None


def test_empty_duplicate_does_not_hide_later_value():
    text = CLEAN_DOC.replace(
        "Policy Number: PA-0001-2026",
        "Policy Number: N/A\nPolicy Number: PA-0001-2026",
    )
    flat = flatten_extracted(extract_fields(text))
    assert flat["policyNumber"] == "PA-0001-2026"


def test_non_string_extraction_is_rejected():
    with pytest.raises(TypeError):
        extract_fields(None)


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


def test_find_missing_fields_flags_placeholder_as_missing():
    extracted = extract_fields(CLEAN_DOC.replace("Policy Number: PA-0001-2026", "Policy Number: N/A"))
    assert "policyNumber" in find_missing_fields(extracted)


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


def test_written_policy_period_is_validated():
    text = CLEAN_DOC.replace(
        "Effective Dates: 01/01/2026 - 01/01/2027",
        "Effective Dates: January 1, 2026 - January 1, 2027",
    )
    assert not any("effective period" in issue for issue in find_inconsistencies(extract_fields(text)))


def test_unparseable_policy_period_is_reported():
    text = CLEAN_DOC.replace("Effective Dates: 01/01/2026 - 01/01/2027", "Effective Dates: someday - eventually")
    issues = find_inconsistencies(extract_fields(text))
    assert any("could not be parsed" in issue for issue in issues)


def test_non_numeric_damage_flagged():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: totaled")
    extracted = extract_fields(text)
    issues = find_inconsistencies(extracted)
    assert any("not a parsable amount" in issue for issue in issues)


def test_negative_damage_flagged():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: -$500.00")
    issues = find_inconsistencies(extract_fields(text))
    assert any("greater than zero" in issue for issue in issues)


def test_zero_initial_estimate_flagged():
    text = CLEAN_DOC.replace("Initial Estimate: $500.00", "Initial Estimate: $0.00")
    issues = find_inconsistencies(extract_fields(text))
    assert any("Initial estimate" in issue and "greater than zero" in issue for issue in issues)


def test_large_estimate_discrepancy_is_reported():
    text = CLEAN_DOC.replace("Initial Estimate: $500.00", "Initial Estimate: $3,000.00")
    issues = find_inconsistencies(extract_fields(text))
    assert any("differ by a factor" in issue for issue in issues)


def test_claim_type_alias_is_accepted():
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Bodily Injury")
    issues = find_inconsistencies(extract_fields(text))
    assert not any("unrecognized" in issue for issue in issues)


# ---------- router ----------

def test_fast_track_when_clean_and_under_threshold():
    result = route(CLEAN_DOC)
    assert result["recommendedRoute"] == "Fast-Track"
    assert result["riskSignals"][0]["code"] == "LOW_DAMAGE"


def test_manual_review_when_fields_missing_even_if_otherwise_fast_track():
    extracted = extract_fields(CLEAN_DOC)
    result = classify_and_route(extracted, missing_fields=["policyNumber"])
    assert result["recommendedRoute"] == "Manual Review"
    assert result["riskSignals"][0]["code"] == "MISSING_DATA"


def test_investigation_flag_on_fraud_keyword():
    text = CLEAN_DOC.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: Damage appears staged and inconsistent with the report.",
    )
    result = route(text)
    assert result["recommendedRoute"] == "Investigation Flag"
    assert result["riskSignals"][0]["severity"] == "critical"


def test_fraud_detection_uses_word_boundaries():
    text = CLEAN_DOC.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: The driver used a fraudulent-sounding policy explanation.",
    )
    result = route(text)
    assert result["recommendedRoute"] == "Investigation Flag"


def test_specialist_queue_for_injury_claim_type():
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Injury")
    result = route(text)
    assert result["recommendedRoute"] == "Specialist Queue"
    assert result["riskSignals"][0]["code"] == "INJURY_EXPOSURE"


def test_specialist_queue_for_bodily_injury_alias():
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Bodily Injury")
    assert route(text)["recommendedRoute"] == "Specialist Queue"


def test_manual_review_for_invalid_damage():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: unknown")
    result = route(text)
    assert result["recommendedRoute"] == "Manual Review"
    assert result["riskSignals"][0]["code"] == "INVALID_DAMAGE"


def test_manual_review_for_zero_damage():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: $0.00")
    result = route(text)
    assert result["recommendedRoute"] == "Manual Review"
    assert result["riskSignals"][0]["code"] == "ZERO_DAMAGE"


def test_standard_review_above_threshold():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: $30,000.00")
    result = route(text)
    assert result["recommendedRoute"] == "Standard Review"
    assert result["riskSignals"][0]["code"] == "ABOVE_FAST_TRACK_THRESHOLD"


def test_threshold_boundary_is_standard_review():
    text = CLEAN_DOC.replace("Estimated Damage: $500.00", "Estimated Damage: $25,000.00")
    assert route(text)["recommendedRoute"] == "Standard Review"


def test_precedence_missing_field_beats_everything_else():
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Injury")
    text = text.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: Looks staged and inconsistent with the story.",
    )
    text = text.replace("Policy Number: PA-0001-2026\n", "")
    result = route(text)
    assert result["recommendedRoute"] == "Manual Review"


def test_precedence_fraud_beats_injury_and_fast_track():
    text = CLEAN_DOC.replace("Claim Type: Collision", "Claim Type: Injury")
    text = text.replace(
        "Description of Accident: A minor fender bender in a parking lot.",
        "Description of Accident: The incident appears staged.",
    )
    assert route(text)["recommendedRoute"] == "Investigation Flag"


# ---------- end-to-end pipeline ----------
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
    assert result["sourceFile"] == filename
    assert "extractedFields" in result
    assert "missingFields" in result
    assert "inconsistencies" in result
    assert "reasoning" in result


def test_inconsistent_dates_sample_reports_the_issue_without_blocking_route():
    result = process_document(str(SAMPLE_DIR / "fnol_07_inconsistent_dates.txt"))
    assert result["recommendedRoute"] == "Fast-Track"
    assert any("effective period" in issue for issue in result["inconsistencies"])


def test_pipeline_preserves_pasted_text_source_name():
    result = process_text(CLEAN_DOC, source_name="manual-entry.txt")
    assert result["sourceFile"] == "manual-entry.txt"
    assert result["recommendedRoute"] == "Fast-Track"
