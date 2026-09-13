"""
app.py
------
Flask front end and versioned JSON API for the FNOL Claims Processing Agent.
The web intake accepts TXT, PDF, Word (.docx), and common claim-image files.
"""
import logging
import tempfile
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from agent.pipeline import process_document, process_text

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "sample_docs"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
API_VERSION = "v1"
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".webp"}

app = Flask(__name__)
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE

logger = logging.getLogger(__name__)

SAMPLE_LABELS = {
    "fnol_08_pdf_sample.pdf": "PDF input",
}


def _request_id():
    return uuid.uuid4().hex[:12]


def _success(data, status=200):
    return jsonify({"success": True, "data": data}), status


def _error(message: str, status: int, code: str, request_id: str | None = None):
    return jsonify({
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id,
        },
    }), status


def _safe_sample_path(filename: str):
    requested = (SAMPLE_DIR / filename).resolve()
    sample_root = SAMPLE_DIR.resolve()
    try:
        requested.relative_to(sample_root)
    except ValueError:
        return None
    return requested


def _process_document_response(path: Path, source_name: str | None = None):
    result = process_document(str(path))
    if source_name:
        result["sourceFile"] = source_name
    return result


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_exc):
    request_id = _request_id()
    return _error(
        "Uploaded file is too large. The maximum supported size is 10 MB.",
        413,
        "FILE_TOO_LARGE",
        request_id,
    )


@app.errorhandler(500)
def handle_internal_error(_exc):
    request_id = _request_id()
    logger.exception("Unhandled FNOL application error request_id=%s", request_id)
    return _error(
        "The FNOL request could not be processed. Please try again.",
        500,
        "INTERNAL_ERROR",
        request_id,
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/v1/health")
def health():
    return _success({"status": "ok", "service": "fnol-claims-agent", "version": API_VERSION})


@app.post("/api/v1/claims/process-upload")
def process_uploaded_file():
    if "file" not in request.files:
        return _error("No file uploaded. Please choose a supported claim file.", 400, "FILE_MISSING")

    upload = request.files["file"]
    original_name = secure_filename(upload.filename or "")
    if not original_name:
        return _error("The uploaded file has no valid filename.", 400, "INVALID_FILENAME")

    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return _error(
            "Unsupported file type. Please upload a supported FNOL file.",
            415,
            "UNSUPPORTED_FILE_TYPE",
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            upload.save(tmp.name)
            tmp_path = Path(tmp.name)

        result = _process_document_response(tmp_path, original_name)
        return _success(result)
    except (OSError, ValueError, TypeError):
        return _error("The uploaded FNOL file could not be processed.", 422, "UPLOAD_PROCESSING_ERROR")
    except Exception:
        request_id = _request_id()
        logger.exception("Unexpected upload processing error request_id=%s", request_id)
        return _error("The uploaded file could not be processed due to an internal error.", 500, "INTERNAL_ERROR", request_id)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Unable to remove temporary upload: %s", tmp_path)


# Sample endpoints are retained for backward compatibility with older clients,
# but the current web UI intentionally does not expose sample selection.
@app.get("/api/v1/samples")
def list_samples():
    if not SAMPLE_DIR.exists():
        return _error("Sample documents are currently unavailable.", 503, "SAMPLES_UNAVAILABLE")

    try:
        samples = []
        for path in sorted(SAMPLE_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() == ".pdf":
                samples.append({
                    "filename": path.name,
                    "label": SAMPLE_LABELS.get(path.name, path.name),
                    "isPdf": True,
                })
        return _success(samples)
    except OSError:
        logger.exception("Unable to list sample documents")
        return _error("Sample documents could not be loaded.", 500, "SAMPLES_READ_ERROR")


@app.get("/api/v1/samples/<filename>")
def sample_detail(filename):
    path = _safe_sample_path(filename)
    if path is None or not path.exists() or not path.is_file() or path.suffix.lower() != ".pdf":
        return _error("Unknown or unsupported sample.", 404, "SAMPLE_NOT_FOUND")
    return _success({
        "filename": path.name,
        "label": SAMPLE_LABELS.get(path.name, path.name),
        "isPdf": True,
    })


@app.post("/api/v1/claims/process-sample/<filename>")
def process_sample(filename):
    path = _safe_sample_path(filename)
    if path is None or not path.exists() or not path.is_file() or path.suffix.lower() != ".pdf":
        return _error("Unknown or unsupported sample.", 404, "SAMPLE_NOT_FOUND")

    try:
        return _success(_process_document_response(path, path.name))
    except (OSError, ValueError, TypeError):
        return _error("The selected sample could not be processed.", 422, "SAMPLE_PROCESSING_ERROR")
    except Exception:
        request_id = _request_id()
        logger.exception("Unexpected sample processing error request_id=%s", request_id)
        return _error("The sample could not be processed due to an internal error.", 500, "INTERNAL_ERROR", request_id)


# Kept for API compatibility with existing integrations.
@app.post("/api/v1/claims/process-text")
def process_pasted_text():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("Request body must be valid JSON.", 400, "INVALID_JSON")

    text = (data.get("text") or "").strip()
    if not text:
        return _error("No text provided.", 400, "EMPTY_TEXT")

    try:
        return _success(process_text(text, source_name="api-input.txt"))
    except (ValueError, TypeError):
        return _error("The supplied FNOL text is invalid or could not be parsed.", 422, "INVALID_INPUT")
    except Exception:
        request_id = _request_id()
        logger.exception("Unexpected text processing error request_id=%s", request_id)
        return _error("The FNOL text could not be processed due to an internal error.", 500, "INTERNAL_ERROR", request_id)


# Backward-compatible aliases.
@app.get("/api/samples")
def legacy_list_samples():
    return list_samples()


@app.post("/api/process-sample/<filename>")
def legacy_process_sample(filename):
    return process_sample(filename)


@app.post("/api/process-text")
def legacy_process_text():
    return process_pasted_text()


@app.post("/api/process-upload")
def legacy_process_upload():
    return process_uploaded_file()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
