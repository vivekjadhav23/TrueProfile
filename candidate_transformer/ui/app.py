import os
import json
import logging
from pathlib import Path
from flask import Flask, request, jsonify

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Base directory for resolving file paths
BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_INPUTS_DIR = BASE_DIR / "sample_inputs"

# Ensure templates folder exists (we'll read it directly from file)
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

@app.route("/")
def index():
    html_path = TEMPLATES_DIR / "index.html"
    try:
        return html_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error loading index.html: {e}", 500

@app.route("/api/inputs", methods=["GET"])
def get_inputs():
    """List all available files in sample_inputs."""
    try:
        files = []
        if SAMPLE_INPUTS_DIR.exists():
            for f in SAMPLE_INPUTS_DIR.iterdir():
                if f.is_file() and f.suffix.lower() != ".json" and "temp" not in f.name:
                    files.append(f.name)
        return jsonify({"files": sorted(files)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/transform", methods=["POST"])
def transform():
    """Run the pipeline on selected inputs and optional custom config."""
    try:
        req_data = request.json or {}
        selected_files = req_data.get("files", [])
        custom_config = req_data.get("config")
        github_url = req_data.get("github_url")
        
        # Build inputs list for the Pipeline
        inputs = []
        for filename in selected_files:
            file_path = SAMPLE_INPUTS_DIR / filename
            ext = file_path.suffix.lower()
            if ext == ".csv":
                inputs.append({"type": "csv", "path": str(file_path)})
            elif ext in [".json", ".ats"]:
                inputs.append({"type": "ats_json", "path": str(file_path)})
            elif ext in [".pdf", ".docx"]:
                inputs.append({"type": "resume", "path": str(file_path)})
            elif ext == ".txt":
                if "notes" in filename.lower():
                    inputs.append({"type": "recruiter_notes", "path": str(file_path)})
                else:
                    inputs.append({"type": "resume", "path": str(file_path)})
            elif "github" in filename.lower() or "github" in str(file_path):
                inputs.append({"type": "github", "url": filename})

        # Append external GitHub source if provided
        if github_url and isinstance(github_url, str) and github_url.strip():
            inputs.append({"type": "github", "path": github_url.strip()})

        if not inputs:
            return jsonify({"error": "No valid inputs selected."}), 400

        # Save config if custom config was passed
        config_path = None
        if custom_config:
            temp_config_path = BASE_DIR / "sample_inputs" / "temp_web_config.json"
            temp_config_path.write_text(json.dumps(custom_config), encoding="utf-8")
            config_path = str(temp_config_path)

        # Import and run Pipeline
        from candidate_transformer.pipeline.extractor import Pipeline
        pipeline = Pipeline(config_path=config_path)
        
        # Run pipeline
        result = pipeline.run(inputs)

        # Retrieve intermediate merged/scored canonical candidate data for comparison in UI
        canonical_model = getattr(pipeline, "canonical_record", result)

        return jsonify({
            "success": True,
            "canonical": canonical_model,
            "projected": result
        })
    except Exception as e:
        logger.error(f"Error in transformation API: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload a file to the sample_inputs folder."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part in request."}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file."}), 400
            
        target_path = SAMPLE_INPUTS_DIR / file.filename
        file.save(str(target_path))
        return jsonify({"success": True, "filename": file.filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
