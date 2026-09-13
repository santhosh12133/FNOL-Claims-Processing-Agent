# FNOL Claims Processing Agent

> **Deterministic insurance-claims triage from First Notice of Loss (FNOL) documents.**

A lightweight, explainable claims-processing pipeline that accepts `.txt` and `.pdf` FNOL documents, extracts structured claim data, validates completeness and consistency, detects routing risks, and recommends the appropriate workflow.

**Built for:** the *Autonomous Insurance Claims Processing Agent* assessment brief.

## Why this project is worth reviewing

- **End-to-end:** document intake → extraction → validation → risk signals → routing → JSON/API/UI.
- **Explainable:** every route is produced by explicit, testable business rules rather than an opaque model decision.
- **Offline by design:** no database, paid API, model key, or external service is required to run the core pipeline.
- **Production-minded:** versioned API, consistent error contracts, upload limits, safe filenames, request IDs, and temporary-file cleanup.
- **Recruiter-friendly:** includes sample claims covering normal cases, missing data, fraud indicators, injury, threshold routing, conflicting signals, inconsistent dates, and PDF input.

---

## 2-minute demo

### 1. Install

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

### 2. Run the automated tests

```bash
pytest -v
```

### 3. Run one claim from the CLI

```bash
python main.py sample_docs/fnol_01_fast_track.txt
```

### 4. Try the browser UI

```bash
python app.py
```

Open **http://localhost:5000** and either select a sample, paste FNOL text, or upload a `.txt` / `.pdf` document.

### 5. Try the API

Health check:

```bash
curl http://localhost:5000/api/v1/health
```

Process text:

```bash
curl -X POST http://localhost:5000/api/v1/claims/process-text \\
  -H "Content-Type: application/json" \\
  -d '{"text":"Policy Number: PA-4471-2026\nPolicyholder Name: Maria Gonzalez\nDate of Incident: 06/14/2026\nLocation: Springfield, IL\nIncident Description: Rear-ended at a stop light.\nClaimant Name: Maria Gonzalez\nEstimated Damage: $1,150.00\nType of Claim: Collision\nSupporting Documents: photos.jpg\nInitial Damage Estimate: $1,150.00"}'
```

---

## Architecture

```text
txt / pdf / pasted text
          │
          ▼
   ┌───────────────┐
   │  extractor.py │  label-based field extraction
   └───────┬───────┘
           ▼
   ┌───────────────┐
   │ validator.py  │  mandatory fields + data quality
   └───────┬───────┘
           ▼
   ┌───────────────┐
   │   router.py   │  safety-first routing + risk signals
   └───────┬───────┘
           ▼
   ┌───────────────┐
   │  metrics.py   │  completeness + processing metrics
   └───────┬───────┘
           ▼
   ┌───────────────┐
   │  pipeline.py  │  consistent result object
   └───────┬───────┘
           │
      ┌────┴────┐
      ▼         ▼
    CLI       Flask API/UI
```

### Core modules

| Module | Responsibility |
|---|---|
| `agent/extractor.py` | Reads TXT/PDF content and extracts labeled FNOL fields using a schema-driven regex approach. |
| `agent/validator.py` | Identifies missing mandatory fields and data-quality inconsistencies such as invalid amounts and dates outside the policy period. |
| `agent/router.py` | Applies safety-first routing precedence and returns structured risk signals plus human-readable reasoning. |
| `agent/metrics.py` | Calculates claim completeness, issue counts, risk-signal count, and automation eligibility. |
| `agent/pipeline.py` | Orchestrates extraction, validation, routing, metrics, and final output. |
| `app.py` | Thin Flask layer exposing the browser UI and versioned JSON API. |
| `main.py` | CLI entry point for individual and batch processing. |
| `tests/test_agent.py` | Automated coverage for extraction, validation, routing, and end-to-end sample processing. |

---

## Claim-processing metrics

Every processed claim includes a `processingMetrics` object so downstream systems or a reviewer can quantify intake quality instead of looking only at the final route.

Example:

```json
"processingMetrics": {
  "mandatoryFieldCompletenessPct": 100.0,
  "fieldsExtracted": 15,
  "fieldsExpected": 15,
  "missingFieldCount": 0,
  "inconsistencyCount": 0,
  "riskSignalCount": 1,
  "automationEligible": true,
  "recommendedRoute": "Fast-Track"
}
```

### What the metrics mean

| Metric | Meaning |
|---|---|
| `mandatoryFieldCompletenessPct` | Percentage of routing-critical fields successfully populated. |
| `fieldsExtracted` / `fieldsExpected` | Overall extraction coverage across the supported FNOL schema. |
| `missingFieldCount` | Number of mandatory fields that prevent a clean automated decision. |
| `inconsistencyCount` | Number of data-quality inconsistencies detected by validation. |
| `riskSignalCount` | Number of structured routing/risk signals produced by the router. |
| `automationEligible` | Whether the recommended route is eligible for straight-through processing under the current rules. |
| `recommendedRoute` | Final workflow recommendation. |

These are **processing-quality and routing metrics**, not operational KPIs such as real insurer cycle time or claim savings; the repository does not have production claims data and does not fabricate those figures.

---

## Routing logic

The router uses an explicit safety-first precedence order:

| Priority | Condition | Route |
|---:|---|---|
| 1 | Mandatory field missing | **Manual Review** |
| 2 | Fraud-indicator language detected | **Investigation Flag** |
| 3 | Injury / bodily-injury claim | **Specialist Queue** |
| 4 | Valid estimated damage below `$25,000` | **Fast-Track** |
| 5 | Otherwise | **Standard Review** |

Additional safety gates send invalid or zero-dollar damage values to Manual Review instead of applying the threshold blindly.

The router also emits structured signals such as:

```json
{
  "code": "FRAUD_INDICATOR",
  "severity": "critical",
  "details": ["staged", "inconsistent"]
}
```

This makes the routing decision both machine-readable and easy for a human reviewer to understand.

---

## Output contract

A successful pipeline result contains:

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

The API wraps this result in a consistent envelope:

```json
{
  "success": true,
  "data": {
    "sourceFile": "fnol_03_fraud_flag.txt",
    "recommendedRoute": "Investigation Flag",
    "processingMetrics": {}
  }
}
```

Errors use the same predictable structure:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "The supplied FNOL text is invalid or could not be parsed.",
    "requestId": null
  }
}
```

Unexpected server errors receive a request ID so the corresponding application log entry can be traced without exposing internal exception details to the client.

---

## API reference

New integrations should use `/api/v1/`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Service health check. |
| `GET` | `/api/v1/samples` | List available sample documents. |
| `GET` | `/api/v1/samples/<filename>` | Get metadata for one sample. |
| `GET` | `/api/v1/samples/<filename>/text` | Read a text sample for preview. |
| `POST` | `/api/v1/claims/process-text` | Process raw FNOL text from JSON. |
| `POST` | `/api/v1/claims/process-upload` | Process an uploaded `.txt` or `.pdf`. |
| `POST` | `/api/v1/claims/process-sample/<filename>` | Process a repository sample. |

The older `/api/...` paths remain as compatibility aliases for existing clients.

### HTTP behavior

- `200` — successful request
- `400` — malformed request or missing input
- `404` — unknown sample
- `413` — upload exceeds the 10 MB limit
- `415` — unsupported file type
- `422` — supplied document/text cannot be processed
- `500` — unexpected internal server error
- `503` — sample resources unavailable

---

## Sample claims

The repository includes eight deliberately different examples:

| Sample | Scenario | Expected route |
|---|---|---|
| `fnol_01_fast_track.txt` | Clean, low-damage claim | Fast-Track |
| `fnol_02_missing_fields.txt` | Missing mandatory information | Manual Review |
| `fnol_03_fraud_flag.txt` | Fraud-indicator keywords | Investigation Flag |
| `fnol_04_injury.txt` | Bodily injury | Specialist Queue |
| `fnol_05_standard_review.txt` | Clean, high-damage claim | Standard Review |
| `fnol_06_multiple_flags.txt` | Multiple rules triggered simultaneously | Manual Review |
| `fnol_07_inconsistent_dates.txt` | Loss outside policy period | Fast-Track + data-quality warning |
| `fnol_08_pdf_sample.pdf` | PDF input | PDF extraction path |

The multi-flag sample is particularly useful for demonstrating rule precedence: missing mandatory data takes priority over fraud, injury, and damage-based routing.

---

## Extraction and validation details

The extractor supports common FNOL label variants including:

- `Policy Number` / `Policy ID`
- `Policyholder Name` / `Policy Holder Name`
- `Date of Incident`
- `Estimated Damage` / `Estimated Loss` / `Estimated Repair Cost`
- `Type of Claim`
- `Supporting Documents` / `Documents Attached`
- `Initial Damage Estimate` / `Initial Loss Estimate`

Placeholder values such as `N/A`, `Nil`, `None`, `Not Available`, `null`, and `--` are treated as missing.

Validation also checks for malformed or non-positive monetary values, invalid dates, loss dates outside the policy period, unsupported claim types, and large discrepancies between the initial estimate and estimated damage.

---

## Testing

Run:

```bash
pytest -v
```

The test suite covers:

- Standard and alternative field labels
- Placeholder normalization
- Multi-line and separator variations
- Duplicate fields
- Type/error handling
- Date and money validation
- Policy-period checks
- Estimate discrepancies
- Claim-type aliases
- Every routing category
- Routing precedence
- Structured risk signals
- End-to-end processing across the sample documents, including PDF input

The README intentionally does not hard-code a test count so the documentation remains accurate as coverage evolves.

---

## Why deterministic processing?

For this portfolio project, the runtime decision engine intentionally does not call an LLM.

A deterministic pipeline is useful for claims triage because it is:

1. **Explainable** — each decision maps to an explicit rule.
2. **Repeatable** — the same document produces the same decision.
3. **Testable** — edge cases can be represented as automated tests.
4. **Offline** — no API key or network access is needed.
5. **Auditable** — risk signals and reasoning are returned with the result.

An LLM-assisted extraction fallback could be added later for genuinely unstructured narratives, while retaining deterministic rules as the final routing control.

---

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
├── scripts/
├── static/
├── templates/
├── tests/
├── app.py
├── main.py
├── requirements.txt
├── .gitignore
├── DEMO_SCRIPT.md
└── README.md
```

Generated output and local development artifacts are intentionally ignored by Git.

---

## Deployment

For local development:

```bash
python app.py
```

For a production WSGI server:

```bash
gunicorn app:app
```

The application has no database or external API-key dependency, which keeps deployment simple. For a public deployment, add HTTPS and platform-appropriate resource limits and logging.

---

## Limitations and next steps

This is a portfolio/assessment implementation rather than a production claims platform.

Potential next improvements:

- LLM-assisted fallback for unstructured FNOL narratives
- Confidence scores for extracted fields
- Support for multiple vehicles, claimants, and injured parties
- Locale-aware currencies and dates
- Persistent claim/audit storage
- Authentication and role-based access
- CI/CD with automated tests on every pull request
- Operational dashboards for aggregate claim-routing metrics

---

## Recruiter walkthrough

If you only have a few minutes:

1. Read the architecture above.
2. Run `pytest -v`.
3. Run `python app.py` and open the browser UI.
4. Try `fnol_01_fast_track.txt` for a clean automated route.
5. Try `fnol_06_multiple_flags.txt` to see precedence and risk signals.
6. Try `fnol_08_pdf_sample.pdf` to see the PDF path.
7. Call `/api/v1/health` and `/api/v1/claims/process-text` to inspect the API contract.

This demonstrates extraction, validation, business-rule routing, explainability, metrics, API design, error handling, testing, and a usable frontend without requiring any external service.

---

## Demo assets

See [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the walkthrough script.
