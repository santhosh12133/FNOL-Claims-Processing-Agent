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
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from agent.pipeline import process_document, process_text

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "sample_docs"

app = Flask(__name__)
app.json.sort_keys = False

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


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/samples")
def list_samples():
    samples = []
    for path in sorted(SAMPLE_DIR.iterdir()):
        if path.suffix.lower() in (".txt", ".pdf"):
            samples.append(
                {
                    "filename": path.name,
                    "label": SAMPLE_LABELS.get(path.name, path.name),
                    "isPdf": path.suffix.lower() == ".pdf",
                }
            )
    return jsonify(samples)


@app.get("/api/sample-text/<filename>")
def sample_text(filename):
    path = SAMPLE_DIR / filename
    if not path.exists() or path.suffix.lower() != ".txt":
        return jsonify({"error": "Not a readable text sample"}), 404
    return jsonify({"text": path.read_text(encoding="utf-8", errors="replace")})


@app.get("/api/process-sample/<filename>")
def process_sample(filename):
    path = SAMPLE_DIR / filename
    if not path.exists():
        return jsonify({"error": f"Unknown sample: {filename}"}), 404
    try:
        result = process_document(str(path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result)


@app.post("/api/process-text")
def process_pasted_text():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided."}), 400
    try:
        result = process_text(text, source_name="pasted-input.txt")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result)


@app.post("/api/process-upload")
def process_uploaded_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400
    upload = request.files["file"]
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in (".txt", ".pdf"):
        return jsonify({"error": "Only .txt and .pdf files are supported."}), 400

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        upload.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = process_document(tmp_path)
        result["sourceFile"] = upload.filename  # show the real filename, not the temp path
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
