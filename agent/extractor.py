"""
extractor.py
------------
Reads raw FNOL documents (.txt or .pdf) and pulls out the fields listed in
the assessment brief using a label-based regex parser. No network/LLM calls
are required — this stays fully deterministic and offline so it runs the
same way in any environment.
"""
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pdfplumber is only required if you're feeding it PDFs
    pdfplumber = None


# Category -> field_key -> label variants that might appear in a document.
# Add more variants here to make the parser recognize differently-worded forms.
FIELD_SCHEMA = {
    "policyInformation": {
        "policyNumber": ["Policy Number", "Policy No", "Policy #"],
        "policyholderName": ["Policyholder Name", "Name of Insured", "Insured Name"],
        "effectiveDates": ["Effective Dates", "Policy Effective Dates", "Policy Period"],
    },
    "incidentInformation": {
        "date": ["Date of Loss", "Incident Date", "Loss Date"],
        "time": ["Time of Loss", "Incident Time", "Loss Time"],
        "location": ["Location of Loss", "Incident Location", "Loss Location"],
        "description": ["Description of Accident", "Accident Description", "Description"],
    },
    "involvedParties": {
        "claimant": ["Claimant", "Insured Driver", "Driver Name"],
        "thirdParties": ["Third Parties", "Third Party"],
        "contactDetails": ["Contact Details", "Contact Phone", "Contact Information"],
    },
    "assetDetails": {
        "assetType": ["Asset Type", "Vehicle Type", "Body Type"],
        "assetId": ["Asset ID", "VIN", "Vehicle ID"],
        "estimatedDamage": ["Estimated Damage", "Damage Estimate"],
    },
    "otherMandatoryFields": {
        "claimType": ["Claim Type"],
        "attachments": ["Attachments"],
        "initialEstimate": ["Initial Estimate"],
    },
}

# Fields treated as "must be present to safely route this claim".
# See README.md ("Design decisions") for why these specific fields were chosen.
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

# Values that count as "not actually provided" even though a label was found.
_EMPTY_VALUES = {"", "n/a", "na", "none", "-", "unknown", "tbd", "none provided", "not provided"}


def _all_label_variants():
    flat = {}
    for category, fields in FIELD_SCHEMA.items():
        for field_key, labels in fields.items():
            flat[field_key] = (category, labels)
    return flat


def _build_pattern(flat_fields):
    """
    Builds a single regex that finds every recognized 'Label:' marker and
    captures the text up to the next recognized label (or end of document).
    Labels are sorted longest-first so e.g. 'Description of Accident' is
    matched whole rather than stopping at the shorter 'Description'.
    """
    all_labels = []
    for field_key, (_category, labels) in flat_fields.items():
        for label in labels:
            all_labels.append((label, field_key))
    all_labels.sort(key=lambda pair: len(pair[0]), reverse=True)

    alternation = "|".join(re.escape(label) for label, _ in all_labels)

    pattern = re.compile(
        rf"(?P<label>{alternation})\s*:?\s*"
        rf"(?P<value>.*?)"
        rf"(?=\n\s*(?:{alternation})\s*:|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    label_to_field = {label.lower(): field_key for label, field_key in all_labels}
    return pattern, label_to_field


_FLAT_FIELDS = _all_label_variants()
_PATTERN, _LABEL_TO_FIELD = _build_pattern(_FLAT_FIELDS)


def read_text_from_file(filepath: str) -> str:
    """Load raw text out of a .txt or .pdf FNOL document."""
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
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)

    raise ValueError(f"Unsupported file type '{suffix}'. Only .txt and .pdf are supported.")


def extract_fields(text: str) -> dict:
    """
    Extract known FNOL fields from raw document text.
    Returns a nested dict mirroring FIELD_SCHEMA's categories; any field not
    found (or found with an empty/placeholder value like 'N/A') is set to None.
    """
    found = {}
    for match in _PATTERN.finditer(text):
        label = match.group("label").strip().lower()
        value = re.sub(r"\s*\n\s*", " ", match.group("value").strip())
        field_key = _LABEL_TO_FIELD.get(label)
        if not field_key:
            continue
        if value.strip().lower() in _EMPTY_VALUES:
            value = None
        # Keep the first non-empty match if a field is accidentally repeated
        if field_key not in found or found[field_key] is None:
            found[field_key] = value or None

    result = {}
    for category, fields in FIELD_SCHEMA.items():
        result[category] = {field_key: found.get(field_key) for field_key in fields}
    return result


def flatten_extracted(extracted: dict) -> dict:
    """Collapse the nested categorized dict into a single flat {field_key: value} dict."""
    flat = {}
    for fields in extracted.values():
        flat.update(fields)
    return flat
