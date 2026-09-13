"""
app.py
------
A minimal Flask front end for the FNOL Claims Processing Agent. This does
NOT reimplement any extraction/routing logic -- it's a browser on top of
the exact same agent/ pipeline used by main.py (the CLI).

Run:
    python app.py
Then open http://localhost:5000
"""
import logging
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from agent.pipeline import process_document, process_text

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "sample_docs"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

app = Flask(__name__)
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE

logger = logging.getLogger(__name__)

# Human-friendly labels for the sample picker buttons in the UI
SAMPLE_LABELS = {
    "fnol_01_fast_track.txt": "Clean claim, low damage",
    "fnol_02_missing_fields.txt": "Missing mandatory fields",
    "fnol_03_fraud_flag.txt": "Fraud-indicator keywords",
    "fnol_04_injury.txt": "Injury claim",
    "fnol_05_standard_review.txt": "Clean claim, high damage",
    "fnol_06_multiple_flags.txt": "Multiple rules at once",
    "fnol_07_inconsistent_dates.txt": "Expired-policy inconsistency",
    "fnol_08_pdf_sample.pdf": "PDF input",
}


def _error(message: str, status: int, code: str):
    """Return a consistent, user-safe API error response."""
    return jsonify({"error": message, "code": code}), status


def _safe_sample_path(filename: str):
    """Resolve a sample path while preventing path traversal."""
    requested = (SAMPLE_DIR / filename).resolve()
    sample_root = SAMPLE_DIR.resolve()
    try:
        requested.relative_to(sample_root)
    except ValueError:
        return None
    return requested


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_exc):
    return _error(
        "Uploaded file is too large. The maximum supported size is 10 MB.",
        413,
        "FILE_TOO_LARGE",
    )


@app.errorhandler(500)
def handle_internal_error(_exc):
    # Keep internal exception details out of the API response.
    logger.exception("Unhandled FNOL application error")
    return _error(
        "The FNOL request could not be processed. Please verify the input and try again.",
        500,
        "INTERNAL_ERROR",
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/samples")
def list_samples():
    if not SAMPLE_DIR.exists():
        logger.error("Sample directory is missing: %s", SAMPLE_DIR)
        return _error("Sample documents are currently unavailable.", 503, "SAMPLES_UNAVAILABLE")

    try:
        samples = []
        for path in sorted(SAMPLE_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in (".txt", ".pdf"):
                samples.append(
                    {
                        "filename": path.name,
                        "label": SAMPLE_LABELS.get(path.name, path.name),
                        "isPdf": path.suffix.lower() == ".pdf",
                    }
                )
        return jsonify(samples)
    except OSError:
        logger.exception("Unable to list sample documents")
        return _error("Sample documents could not be loaded.", 500, "SAMPLES_READ_ERROR")


@app.get("/api/sample-text/<filename>")
def sample_text(filename):
    path = _safe_sample_path(filename)
    if path is None or not path.exists() or not path.is_file() or path.suffix.lower() != ".txt":
        return _error("Not a readable text sample.", 404, "SAMPLE_NOT_FOUND")

    try:
        return jsonify({"text": path.read_text(encoding="utf-8", errors="replace")})
    except OSError:
        logger.exception("Unable to read sample text: %s", filename)
        return _error("The selected sample could not be read.", 500, "SAMPLE_READ_ERROR")


@app.get("/api/process-sample/<filename>")
def process_sample(filename):
    path = _safe_sample_path(filename)
    if path is None or not path.exists() or not path.is_file() or path.suffix.lower() not in (".txt", ".pdf"):
        return _error("Unknown or unsupported sample.", 404, "SAMPLE_NOT_FOUND")

    try:
        result = process_document(str(path))
        return jsonify(result)
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Sample processing failed for %s: %s", filename, exc)
        return _error("The selected sample could not be processed.", 422, "SAMPLE_PROCESSING_ERROR")
    except Exception:
        logger.exception("Unexpected sample processing error: %s", filename)
        return _error("The sample could not be processed due to an internal error.", 500, "INTERNAL_ERROR")


@app.post("/api/process-text")
def process_pasted_text():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("Request body must be valid JSON.", 400, "INVALID_JSON")

    text = (data.get("text") or "").strip()
    if not text:
        return _error("No text provided.", 400, "EMPTY_TEXT")

    try:
        result = process_text(text, source_name="pasted-input.txt")
        return jsonify(result)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid pasted FNOL input: %s", exc)
        return _error("The supplied FNOL text is invalid or could not be parsed.", 422, "INVALID_INPUT")
    except Exception:
        logger.exception("Unexpected pasted-text processing error")
        return _error("The FNOL text could not be processed due to an internal error.", 500, "INTERNAL_ERROR")


@app.post("/api/process-upload")
def process_uploaded_file():
    if "file" not in request.files:
        return _error("No file uploaded.", 400, "FILE_MISSING")

    upload = request.files["file"]
    original_name = secure_filename(upload.filename or "")
    if not original_name:
        return _error("The uploaded file has no valid filename.", 400, "INVALID_FILENAME")

    suffix = Path(original_name).suffix.lower()
    if suffix not in (".txt", ".pdf"):
        return _error("Only .txt and .pdf files are supported.", 415, "UNSUPPORTED_FILE_TYPE")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            upload.save(tmp.name)
            tmp_path = Path(tmp.name)

        result = process_document(str(tmp_path))
        result["sourceFile"] = original_name
        return jsonify(result)
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Uploaded FNOL processing failed for %s: %s", original_name, exc)
        return _error("The uploaded FNOL document could not be processed.", 422, "UPLOAD_PROCESSING_ERROR")
    except Exception:
        logger.exception("Unexpected upload processing error for %s", original_name)
        return _error("The uploaded document could not be processed due to an internal error.", 500, "INTERNAL_ERROR")
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Unable to remove temporary upload: %s", tmp_path)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
