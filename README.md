# FNOL Claims Processing Agent

> Deterministic insurance-claims triage from First Notice of Loss (FNOL) documents.

A lightweight, explainable pipeline that extracts FNOL fields, validates missing and inconsistent data, detects routing risks, and recommends the appropriate claims workflow.

**Built for the Autonomous Insurance Claims Processing Agent assessment brief.**

## What it does

1. Accepts FNOL text, PDF, Word (`.docx`), or common claim images (`.jpg`, `.jpeg`, `.png`, `.webp`).
2. Extracts structured policy, incident, party, asset, and claim fields.
3. Identifies missing mandatory fields and data-quality inconsistencies.
4. Applies deterministic routing rules with explicit precedence.
5. Returns a short human-readable rationale plus structured JSON output.
6. Exposes the same pipeline through a CLI, Flask UI, and versioned API.

Image uploads use local RapidOCR processing; no external OCR API or model key is required.

## 2-minute demo

### Install

```bash
git clone https://github.com/santhosh12133/FNOL-Claims-Processing-Agent.git
cd FNOL-Claims-Processing-Agent
python -m venv .venv

# Windows
.venv\\Scripts\\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

### Run tests

```bash
pytest -v
```

### Run the CLI

```bash
python main.py sample_docs/fnol_01_fast_track.txt
```

### Run the web UI

```bash
python app.py
```

Open `http://localhost:5000` and upload a supported FNOL file.

## Architecture

```text
FNOL TXT / PDF / DOCX / image
              │
              ▼
        extractor.py
              │
              ▼
        validator.py
              │
              ▼
          router.py
              │
              ▼
          metrics.py
              │
              ▼
         pipeline.py
          │         │
          ▼         ▼
         CLI     Flask API/UI
```

### Core modules

| Module | Responsibility |
|---|---|
| `agent/extractor.py` | Reads TXT/PDF/DOCX/images and extracts labeled FNOL fields. Images are OCR'd with RapidOCR. |
| `agent/validator.py` | Checks mandatory fields, dates, monetary values, policy coverage, claim types, and estimate consistency. |
| `agent/router.py` | Applies safety-first deterministic routing and emits structured risk signals. |
| `agent/metrics.py` | Calculates completeness, issue counts, risk count, and automation eligibility. |
| `agent/pipeline.py` | Orchestrates extraction, validation, routing, metrics, and final output. |
| `app.py` | Flask UI and versioned JSON API with upload/error handling. |
| `main.py` | CLI entry point. |
| `tests/test_agent.py` | Automated tests for extraction, validation, routing, and end-to-end samples. |

## Fields extracted

The schema covers the assessment brief's required fields:

- **Policy:** policy number, policyholder name, effective dates
- **Incident:** date, time, location, description
- **Involved parties:** claimant, third parties, contact details
- **Asset:** asset type, asset ID, estimated damage
- **Other mandatory fields:** claim type, attachments, initial estimate

Common FNOL label variants are supported, including `Policy Number` / `Policy ID`, `Date of Loss` / `Date of Incident`, `Estimated Damage` / `Estimated Loss` / `Estimated Repair Cost`, and `Claim Type` / `Type of Claim`.

Placeholder values such as `N/A`, `Nil`, `None`, `Not Available`, `null`, and `--` are treated as missing.

## Routing rules

The assessment rules are implemented with explicit precedence:

| Priority | Condition | Route |
|---:|---|---|
| 1 | Any mandatory field is missing | **Manual Review** |
| 2 | Description contains fraud-indicator language such as `fraud`, `inconsistent`, or `staged` | **Investigation Flag** |
| 3 | Claim type is injury | **Specialist Queue** |
| 4 | Estimated damage is below `$25,000` | **Fast-Track** |
| 5 | Otherwise | **Standard Review** |

Additional safety checks send invalid or zero-dollar damage values to Manual Review rather than applying the threshold blindly.

The router returns structured signals such as:

```json
{
  "code": "FRAUD_INDICATOR",
  "severity": "critical",
  "details": ["staged", "inconsistent"]
}
```

## Output

The pipeline returns the required assessment fields plus useful quality/risk metadata:

```json
{
  "sourceFile": "fnol_03_fraud_flag.txt",
  "extractedFields": {},
  "missingFields": [],
  "inconsistencies": [],
  "recommendedRoute": "Investigation Flag",
  "reasoning": "...",
  "riskSignals": [],
  "processingMetrics": {}
}
```

The API wraps successful responses as:

```json
{
  "success": true,
  "data": { }
}
```

Errors use:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "...",
    "requestId": null
  }
}
```

## API

New integrations should use `/api/v1/`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Service health check |
| `GET` | `/api/v1/samples` | List sample documents |
| `GET` | `/api/v1/samples/<filename>` | Get sample metadata |
| `GET` | `/api/v1/samples/<filename>/text` | Read a text sample |
| `POST` | `/api/v1/claims/process-text` | Process FNOL text |
| `POST` | `/api/v1/claims/process-upload` | Process TXT/PDF/DOCX/image upload |
| `POST` | `/api/v1/claims/process-sample/<filename>` | Process a repository sample |

Upload size is limited to 10 MB. Uploaded filenames are sanitized and temporary files are cleaned up after processing. Legacy `/api/...` aliases remain available for compatibility.

## Sample claims

The repository contains eight deliberately different examples:

| Sample | Scenario | Expected route |
|---|---|---|
| `fnol_01_fast_track.txt` | Clean, low-damage claim | Fast-Track |
| `fnol_02_missing_fields.txt` | Missing mandatory information | Manual Review |
| `fnol_03_fraud_flag.txt` | Fraud-indicator keywords | Investigation Flag |
| `fnol_04_injury.txt` | Bodily injury | Specialist Queue |
| `fnol_05_standard_review.txt` | Clean, high-damage claim | Standard Review |
| `fnol_06_multiple_flags.txt` | Multiple rules triggered | Manual Review |
| `fnol_07_inconsistent_dates.txt` | Loss outside policy period | Fast-Track + data-quality warning |
| `fnol_08_pdf_sample.pdf` | PDF input | Fast-Track |

## Testing

Run:

```bash
pytest -v
```

Coverage includes:

- Required and alternative FNOL labels
- Placeholder normalization
- Separator and multiline variations
- Duplicate fields
- Missing mandatory fields
- Date and money validation
- Policy-period checks
- Estimate discrepancies
- Claim-type aliases
- Every routing category
- Routing precedence
- Fraud word-boundary handling
- Structured risk signals
- End-to-end processing of all sample documents, including PDF

## Design decisions

### Deterministic routing

The final routing decision is deliberately rule-based rather than LLM-generated. This makes the result repeatable, explainable, testable, and auditable.

### Local image OCR

Image documents are converted to text with RapidOCR before entering the same extraction/validation/routing pipeline. This keeps image processing consistent with other FNOL inputs without requiring an external OCR service.

### Data-quality warnings do not silently override routing

Validation inconsistencies are surfaced to the reviewer. Routing only changes when an explicit routing rule requires it, preventing an undocumented heuristic from changing the assessment result.

## Project structure

```text
FNOL-Claims-Processing-Agent/
├── agent/
│   ├── extractor.py
│   ├── validator.py
│   ├── router.py
│   ├── metrics.py
│   └── pipeline.py
├── sample_docs/
├── static/
├── templates/
├── tests/
├── app.py
├── main.py
├── requirements.txt
├── DEMO_SCRIPT.md
└── README.md
```

## Deployment

Production WSGI command:

```bash
gunicorn app:app
```

The service has no database or application API-key dependency. Image OCR requires the Python dependencies listed in `requirements.txt`.

## Limitations / next steps

This is a portfolio/assessment implementation rather than a production claims platform. Future improvements could include confidence scores, multiple vehicles/claimants, persistent audit storage, authentication, CI/CD, and LLM-assisted extraction for genuinely unstructured narratives while retaining deterministic routing as the final control.

## Submission checklist

- GitHub repository: complete
- README with approach and run steps: complete
- FNOL extraction: complete
- Missing/inconsistent field detection: complete
- Required routing rules: complete
- JSON output with rationale: complete
- Optional demo video: not required
