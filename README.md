# FNOL Claims Processing Agent

A lightweight agent that reads First Notice of Loss (FNOL) documents, extracts
key fields, flags missing or inconsistent data, and routes each claim to the
correct workflow with a plain-English explanation — available as both a CLI
and a browser-based triage desk.

Built for the **"Autonomous Insurance Claims Processing Agent"** assessment brief.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Approach](#approach)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage: Command Line](#usage-command-line)
- [Usage: Web UI](#usage-web-ui)
- [Web API Reference](#web-api-reference)
- [Output Format](#output-format)
- [Routing Rules & Precedence](#routing-rules--precedence)
- [Design Decisions & Assumptions](#design-decisions--assumptions)
- [Sample Documents](#sample-documents)
- [Testing](#testing)
- [Limitations & Future Improvements](#limitations--future-improvements)
- [Deployment](#deployment)
- [Demo Video](#demo-video)

---

## Quick Start

```bash
git clone <your-repo-url> && cd fnol-claims-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -v                                            # 23 tests, all passing
python main.py sample_docs/fnol_01_fast_track.txt    # CLI, single document
python app.py                                        # Web UI → http://localhost:5000
```

---

## Approach

The pipeline has three stages, each in its own module under `agent/`, wired
together by a fourth:

```
document (.txt / .pdf)
        │
        ▼
  extractor.py   →  pulls fields via a label-based regex (FIELD_SCHEMA)
        │
        ▼
  validator.py   →  flags missing mandatory fields + data-quality inconsistencies
        │
        ▼
  router.py      →  applies the 4 routing rules in priority order, explains why
        │
        ▼
  pipeline.py    →  assembles the final JSON result
```

| Module | Responsibility |
|---|---|
| `extractor.py` | Loads raw text (plain read for `.txt`, `pdfplumber` for `.pdf`), then uses one regex built from a label schema to find every `"Label: value"` pair and capture its value up to the next recognized label. Works identically for both formats once PDF text is flattened to a string. |
| `validator.py` | Determines which mandatory fields are missing, and runs a small set of consistency checks (unparseable dates/amounts, loss date outside the policy's effective period, unrecognized claim type). |
| `router.py` | Applies the four routing rules from the brief in a specific priority order (see [below](#routing-rules--precedence)) and returns a human-readable reason for the decision. |
| `pipeline.py` | Ties the above together (`process_document` for files, `process_text` for in-memory text) into the JSON shape the brief requires. |

**Why deterministic rules instead of an LLM call.** For structured/semi-structured
intake documents like FNOL forms, a regex/rule-based extractor is faster, free,
fully offline, and — critically for a *routing* decision — 100% explainable and
testable: every decision traces back to a specific rule, not a model's judgment
call. The brief notes AI tools are encouraged for *building* the solution, which
was used here for scaffolding and review; the *runtime* pipeline was deliberately
kept free of API dependencies so it behaves identically regardless of network
access or API keys. See [Limitations & Future Improvements](#limitations--future-improvements)
for how an LLM-assisted fallback could extend this for unstructured free text.

---

## Project Structure

```
fnol-claims-agent/
├── agent/                      # Core pipeline (no CLI/web concerns live here)
│   ├── extractor.py             # Field extraction (FIELD_SCHEMA, regex)
│   ├── validator.py             # Missing-field + inconsistency checks
│   ├── router.py                 # Routing rules, precedence, reasoning
│   └── pipeline.py               # Orchestrates the above into one result
├── main.py                     # CLI entry point
├── app.py                      # Flask web app (thin wrapper over agent/)
├── templates/index.html          # Web UI page
├── static/style.css              # Web UI styling
├── static/app.js                  # Web UI behavior
├── sample_docs/                # 8 dummy FNOL documents (7 .txt, 1 .pdf)
├── scripts/generate_sample_pdf.py  # Regenerates the PDF sample
├── tests/test_agent.py         # 23 tests: extraction, validation, routing
├── output/                     # JSON results land here with --save
├── requirements.txt
├── DEMO_SCRIPT.md               # Script for the walkthrough video
└── README.md
```

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

`requirements.txt` covers the CLI, the test suite, and the web UI (Flask) —
one install gets you everything.

---

## Usage: Command Line

Process a single document:
```bash
python main.py sample_docs/fnol_01_fast_track.txt
```

Process every sample document and print a summary:
```bash
python main.py --batch sample_docs/
```

Same, but also write each result as JSON into `output/`:
```bash
python main.py --batch sample_docs/ --save
```

---

## Usage: Web UI

```bash
python app.py
```

Open **http://localhost:5000**. From there you can:

- Click a sample button to load and instantly process one of the 8 sample documents
- Paste your own FNOL text into the box and click **Process Claim**
- Upload your own `.txt` / `.pdf` file directly

The recommended route renders as a color-coded stamp — green (Fast-Track),
blue (Standard Review), purple (Specialist Queue), red (Investigation Flag),
amber (Manual Review) — alongside the reasoning, missing fields,
inconsistencies, and the full extracted-field breakdown, grouped the same way
as the brief's own field categories.

This runs on `localhost` only — see [Deployment](#deployment) if you want it
reachable outside your own machine.

---

## Web API Reference

The web UI is a thin client over these JSON endpoints — useful if you want to
script against it directly instead of using the browser:

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the triage desk page |
| `GET` | `/api/samples` | Lists all sample documents with display labels |
| `GET` | `/api/sample-text/<filename>` | Returns the raw text of a `.txt` sample (for the textarea preview) |
| `GET` | `/api/process-sample/<filename>` | Runs the full pipeline on a sample document, returns the result JSON |
| `POST` | `/api/process-text` | Body: `{"text": "..."}` — processes pasted/raw text |
| `POST` | `/api/process-upload` | Multipart form, field `file` — processes an uploaded `.txt`/`.pdf` |

All endpoints return `400` with `{"error": "..."}` for bad input (empty text,
unsupported file type, unknown sample) rather than a raw stack trace.

---

## Output Format

Matches the brief's required shape, plus one addition (`inconsistencies`,
explained in [Design Decisions](#design-decisions--assumptions)):

```json
{
  "sourceFile": "fnol_03_fraud_flag.txt",
  "extractedFields": {
    "policyInformation": { "...": "..." },
    "incidentInformation": { "...": "..." },
    "involvedParties": { "...": "..." },
    "assetDetails": { "...": "..." },
    "otherMandatoryFields": { "...": "..." }
  },
  "missingFields": [],
  "inconsistencies": [],
  "recommendedRoute": "Investigation Flag",
  "reasoning": "Routed to Investigation Flag: ..."
}
```

`extractedFields` is nested by category — matching the brief's own field
grouping — rather than one flat object, since that structure is easier for a
downstream reviewer scanning the JSON to reason about.

---

## Routing Rules & Precedence

The brief gives four rules but doesn't specify what happens when more than one
applies to the same claim (e.g. a cheap claim that also looks fraudulent).
This is resolved by applying them in the following order, highest priority first:

| Order | Rule | Route |
|---|---|---|
| 1 | Any mandatory field missing | **Manual Review** |
| 2 | Description contains a fraud-indicator keyword (`fraud`, `inconsistent`, `staged`) | **Investigation Flag** |
| 3 | Claim type = `Injury` | **Specialist Queue** |
| 4 | Estimated damage < $25,000 | **Fast-Track** |
| 5 | None of the above | **Standard Review** *(fallback, not in the original brief)* |

**Why this order:** incomplete data blocks *any* automated decision, so it's
checked first. Suspected fraud is checked before the dollar-amount rule on
purpose — a small, "fast-track-sized" claim that looks staged should still go
to Investigation, not get rubber-stamped for being cheap. Injury claims are
pulled out next because bodily-injury exposure isn't well-represented by a
repair-cost number. Only after those three checks does the $25,000 threshold
decide between Fast-Track and a default Standard Review queue for larger,
otherwise-clean claims (the brief doesn't say what to do above the threshold,
so this catch-all was added rather than leaving those claims unrouted).

`sample_docs/fnol_06_multiple_flags.txt` is a deliberate stress test: missing
fields **and** a fraud keyword **and** an injury claim type **and** damage
under $25,000 — all four conditions at once — proving Manual Review wins as
intended. See `tests/test_agent.py::test_precedence_missing_field_beats_everything_else`.

---

## Design Decisions & Assumptions

- **What counts as "mandatory."** The brief's last field category is literally
  named "Other Mandatory Fields" (Claim Type, Attachments, Initial Estimate).
  Those three are kept, plus Policy Number, Policyholder Name, Date of Loss,
  Location, and Estimated Damage — because a routing decision can't be made
  without them (no damage figure means the $25k rule can't run; no description
  means the fraud-keyword check can't run). Fields like Time of Loss,
  Effective Dates, Third Parties, Contact Details, and Asset Type/ID are still
  extracted and reported, just not treated as blocking.
- **Placeholder values.** A value that's literally `N/A`, `None`, `Unknown`,
  `-`, etc. is treated the same as if the field were absent — a form that says
  "Third Parties: N/A" hasn't actually told you anything.
- **Inconsistencies don't block routing on their own.** The brief's four
  routing rules don't include an "inconsistent data" rule, so rather than
  inventing new routing behavior, inconsistencies (e.g. a loss date outside
  the policy's effective period) are surfaced in a separate `inconsistencies`
  list and appended to the reasoning for a human to see, without silently
  overriding the specified rules. `fnol_07_inconsistent_dates.txt` demonstrates
  this: the policy had already expired when the loss occurred, which is
  flagged, but the claim still routes to Fast-Track per the stated rules since
  damage is low and nothing else is wrong.
- **Extraction is label-based** — it looks for `"Field Name: value"` patterns,
  matching how FNOL intake forms and structured emails are usually laid out
  (including the ACORD Automobile Loss Notice fields this brief is modeled
  on). It won't work well on a free-text narrative with no labels — see
  [Limitations](#limitations--future-improvements).

---

## Sample Documents

`sample_docs/` has 8 dummy FNOL documents (more than the 3–5 requested, for
full coverage of every rule plus edge cases) — 7 `.txt` and 1 `.pdf`
(generated by `scripts/generate_sample_pdf.py`, using an original layout
rather than reproducing any insurer's copyrighted form):

| File | Demonstrates |
|---|---|
| `fnol_01_fast_track.txt` | Clean claim, low damage → Fast-Track |
| `fnol_02_missing_fields.txt` | Missing mandatory fields → Manual Review |
| `fnol_03_fraud_flag.txt` | Fraud keywords in description → Investigation Flag |
| `fnol_04_injury.txt` | Claim type = Injury → Specialist Queue |
| `fnol_05_standard_review.txt` | Clean claim above $25k → Standard Review |
| `fnol_06_multiple_flags.txt` | All four rules apply at once → precedence test |
| `fnol_07_inconsistent_dates.txt` | Expired-policy inconsistency, non-blocking |
| `fnol_08_pdf_sample.pdf` | Same pipeline, PDF input instead of text |

---

## Testing

```bash
pytest -v
```

23 tests covering:
- Field extraction (including multi-line values and placeholder normalization)
- Missing-field and inconsistency detection
- Each routing rule individually
- The multi-flag precedence edge case
- End-to-end pipeline runs against every file in `sample_docs/`, including the PDF

---

## Limitations & Future Improvements

- **Free-text/unstructured input.** The extractor needs a labeled field to
  find a value. A natural next step is an LLM-assisted fallback (e.g. via the
  Anthropic API) that only activates for fields the regex extractor couldn't
  find, with the deterministic extractor remaining the primary path. This was
  left out of the delivered pipeline so grading doesn't depend on network
  access or an API key.
- **Multiple vehicles/parties.** The schema captures one claimant/third-party
  block per document; a real filing can have several vehicles and injured
  parties, which would need a repeated-section parser.
- **Currency/locale.** Amount parsing assumes USD-style numbers
  (`$1,234.56`); other formats would need locale-aware parsing.
- **Confidence scoring.** A field is currently either found or not; a
  production version might attach a confidence score per field so borderline
  extractions get lighter-touch review instead of being treated like a clean match.

---

## Deployment

This is built and tested to run locally. To push it to your own GitHub repo:

```bash
cd fnol-claims-agent
git init
git add .
git commit -m "FNOL claims processing agent"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

To put the web UI on the public internet rather than `localhost`, deploy
`app.py` like any small Flask app (Render, Railway, Fly.io, and
PythonAnywhere all have free tiers): point the platform at `app.py` and run it
behind a production server (`gunicorn app:app`) instead of the Flask dev
server. There's no database or API key dependency, so it should deploy as-is —
this step is outside the scope of the assessment and isn't wired up here.

---
 <img width="946" height="438" alt="Screenshot 2026-07-08 145924" src="https://github.com/user-attachments/assets/d35d22d3-9d8a-49a9-93e8-98e79025874b" />

 <img width="948" height="445" alt="Screenshot 2026-07-08 145950" src="https://github.com/user-attachments/assets/22fb2b4b-f93a-446e-9a12-642eadce2723" />

 <img width="950" height="443" alt="Screenshot 2026-07-08 150014" src="https://github.com/user-attachments/assets/12021085-0220-4912-9105-ef7009224714" />


 <img width="950" height="443" alt="Screenshot 2026-07-08 150014" src="https://github.com/user-attachments/assets/f6e39c9c-9ee1-434b-b884-a3ddcaf46d02" />


