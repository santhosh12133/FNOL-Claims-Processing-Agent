"""
extractor.py
------------
Reads FNOL documents (.txt/.pdf) and extracts known fields with a
label-aware, deterministic parser. The extractor is intentionally offline
and explainable so the same input produces the same output everywhere.
"""
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


FIELD_SCHEMA = {
    "policyInformation": {
        "policyNumber": ["Policy Number", "Policy No", "Policy #", "Policy ID"],
        "policyholderName": ["Policyholder Name", "Policy Holder Name", "Name of Insured", "Insured Name"],
        "effectiveDates": ["Effective Dates", "Policy Effective Dates", "Policy Period", "Policy Dates"],
    },
    "incidentInformation": {
        "date": ["Date of Loss", "Incident Date", "Loss Date", "Date of Incident"],
        "time": ["Time of Loss", "Incident Time", "Loss Time", "Time of Incident"],
        "location": ["Location of Loss", "Incident Location", "Loss Location", "Location of Incident"],
        "description": ["Description of Accident", "Accident Description", "Incident Description", "Description"],
    },
    "involvedParties": {
        "claimant": ["Claimant", "Insured Driver", "Driver Name", "Claimant Name"],
        "thirdParties": ["Third Parties", "Third Party", "Other Parties"],
        "contactDetails": ["Contact Details", "Contact Phone", "Contact Information", "Phone Number"],
    },
    "assetDetails": {
        "assetType": ["Asset Type", "Vehicle Type", "Body Type"],
        "assetId": ["Asset ID", "VIN", "Vehicle ID", "Vehicle Identification Number"],
        "estimatedDamage": ["Estimated Damage", "Damage Estimate", "Estimated Loss", "Estimated Repair Cost"],
    },
    "otherMandatoryFields": {
        "claimType": ["Claim Type", "Type of Claim"],
        "attachments": ["Attachments", "Supporting Documents", "Documents Attached"],
        "initialEstimate": ["Initial Estimate", "Initial Damage Estimate", "Initial Loss Estimate"],
    },
}

MANDATORY_FIELDS = [
    "policyNumber",
    "policyholderName",
    "date",
    "location",
    "description",
    "claimType",
    "estimatedDamage",
    "attachments",
    "initialEstimate",
]

_EMPTY_VALUES = {
    "", "n/a", "n.a.", "na", "none", "-", "--", "unknown", "tbd",
    "none provided", "not provided", "not available", "nil", "null",
}


def _all_label_variants():
    flat = {}
    for category, fields in FIELD_SCHEMA.items():
        for field_key, labels in fields.items():
            flat[field_key] = (category, labels)
    return flat


def _build_pattern(flat_fields):
    """Build one regex that captures each recognized label's value."""
    all_labels = []
    for field_key, (_category, labels) in flat_fields.items():
        for label in labels:
            all_labels.append((label, field_key))

    # Longest first prevents "Description" from winning over
    # "Description of Accident".
    all_labels.sort(key=lambda pair: len(pair[0]), reverse=True)
    alternation = "|".join(re.escape(label) for label, _ in all_labels)

    # A label may be followed by ':' or '-' and values may span lines.
    # The next recognized label is the boundary; this also handles documents
    # that omit punctuation after a field label.
    pattern = re.compile(
        rf"(?P<label>{alternation})\s*(?:[:\-]|(?=\S))\s*"
        rf"(?P<value>.*?)"
        rf"(?=\n\s*(?:{alternation})\s*(?:[:\-]|\s)|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    label_to_field = {label.lower(): field_key for label, field_key in all_labels}
    return pattern, label_to_field


_FLAT_FIELDS = _all_label_variants()
_PATTERN, _LABEL_TO_FIELD = _build_pattern(_FLAT_FIELDS)


def _clean_value(value: str):
    """Normalize whitespace and turn known placeholders into None."""
    value = re.sub(r"\s*\n\s*", " ", value).strip()
    value = re.sub(r"[ \t]+", " ", value)
    if value.lower() in _EMPTY_VALUES:
        return None
    return value or None


def read_text_from_file(filepath: str) -> str:
    """Load raw text from a .txt or .pdf FNOL document."""
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        if pdfplumber is None:
            raise RuntimeError(
                "pdfplumber is required to read PDF files. Install with: pip install pdfplumber"
            )
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(f"[Page {page_number}]\n{page_text}")
        return "\n".join(text_parts)

    raise ValueError(f"Unsupported file type '{suffix}'. Only .txt and .pdf are supported.")


def extract_fields(text: str) -> dict:
    """Extract known FNOL fields into the categorized FIELD_SCHEMA shape."""
    if not isinstance(text, str):
        raise TypeError("FNOL document text must be a string.")

    found = {}
    for match in _PATTERN.finditer(text):
        label = match.group("label").strip().lower()
        field_key = _LABEL_TO_FIELD.get(label)
        if not field_key:
            continue

        value = _clean_value(match.group("value"))
        # Prefer the first non-empty value when a document repeats a field.
        if field_key not in found or found[field_key] is None:
            found[field_key] = value

    return {
        category: {field_key: found.get(field_key) for field_key in fields}
        for category, fields in FIELD_SCHEMA.items()
    }


def flatten_extracted(extracted: dict) -> dict:
    """Collapse categorized fields into a single {field_key: value} mapping."""
    flat = {}
    for fields in extracted.values():
        flat.update(fields)
    return flat
