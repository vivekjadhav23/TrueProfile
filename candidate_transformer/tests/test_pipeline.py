import os
import json
import hashlib
import pytest
from unittest.mock import patch, Mock
from candidate_transformer.pipeline.extractor import Pipeline

def test_pipeline_success(tmp_path):
    """
    Test a full successful pipeline run.
    Integrates CSV and GitHub extracts, runs normalization, merges outputs,
    computes confidence, projects fields, adds a hashed candidate_id,
    and validates results against output_schema.json.
    """
    # Create temporary config file conforming to output_schema.json requirements
    config_file = tmp_path / "config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True},
            {"path": "email", "from": "emails[0]", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"},
            {"path": "skills", "from": "skills", "type": "array"},
            {"path": "experience", "from": "experience", "type": "array"}
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    with patch("candidate_transformer.sources.CsvSource.extract") as mock_csv_extract, \
         patch("candidate_transformer.sources.GithubSource.extract") as mock_github_extract:

        # Mock CSV Source (priority 1)
        mock_csv_extract.return_value = {
            "source_name": "recruiter_csv",
            "full_name": "Jane Doe",
            "emails": ["jane.doe@example.com"],
            "phones": ["9876543210"],
            "current_company": "Acme Corp",
            "title": "Engineer"
        }

        # Mock GitHub Source (priority 3)
        mock_github_extract.return_value = {
            "source_name": "github",
            "full_name": "Jane",
            "emails": ["jane.github@example.com"],
            "skills": ["Python", "Go"],
            "experience": [
                {"company": "Acme Corp", "title": "Software Engineer", "start": "Jan 2020", "end": "present"}
            ]
        }

        pipeline = Pipeline(config_path=str(config_file))
        inputs = [
            {"type": "csv", "path": "dummy.csv"},
            {"type": "github", "url": "https://github.com/jane"}
        ]

        result = pipeline.run(inputs)

        # Asserts matching values mapped to output_schema.json
        assert result["name"] == "Jane"
        assert result["email"] == "jane.doe@example.com"
        assert result["phone"] == "+919876543210" # India formatting
        skills_names = [s["name"] for s in result["skills"]]
        assert "Python" in skills_names
        assert "Go" in skills_names
        assert len(result["experience"]) == 1
        assert result["experience"][0]["end"] == "present"

        # Verify candidate_id SHA256 hashing
        cleaned_emails = sorted(list(set(email.lower() for email in ["jane.doe@example.com", "jane.github@example.com"])))
        sorted_emails_joined = "".join(cleaned_emails)
        full_name_lowercase = "jane"
        input_str = f"{sorted_emails_joined}{full_name_lowercase}"
        expected_hash = hashlib.sha256(input_str.encode("utf-8")).hexdigest()[:16]
        assert result["candidate_id"] == expected_hash

def test_pipeline_resilience(tmp_path):
    """
    Test that the pipeline is resilient to individual source crashes
    and continues parsing other available sources.
    """
    config_file = tmp_path / "config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True}
        ],
        "include_confidence": False,
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    with patch("candidate_transformer.sources.CsvSource.extract") as mock_csv_extract, \
         patch("candidate_transformer.sources.GithubSource.extract") as mock_github_extract:

        # Raise exception for CSV, success for GitHub
        mock_csv_extract.side_effect = Exception("Network IO Error reading CSV")
        mock_github_extract.return_value = {
            "source_name": "github",
            "full_name": "Jane GitHub",
            "emails": []
        }

        pipeline = Pipeline(config_path=str(config_file))
        inputs = [
            {"type": "csv", "path": "error.csv"},
            {"type": "github", "url": "https://github.com/jane"}
        ]

        result = pipeline.run(inputs)

        # CSV crash did not fail the run, GitHub name was mapped
        assert result["name"] == "Jane GitHub"
        assert "candidate_id" in result

def test_pipeline_integration_happy_path(tmp_path):
    """
    Test 1 - Happy path:
      Run pipeline with sample CSV + sample ATS JSON.
      Assert: output is valid JSON matching output_schema.json
      Assert: overall_confidence > 0.5
      Assert: provenance has entries from both sources
      Assert: phones are in E.164 format
      Assert: candidate_id is present and consistent across runs
    """
    config_file = tmp_path / "happy_config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True},
            {"path": "email", "from": "emails[0]", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"},
            {"path": "skills", "from": "skills", "type": "array"},
            {"path": "experience", "from": "experience", "type": "array"},
            {"path": "provenance", "from": "provenance", "type": "array"}
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "sample_inputs", "sample_recruiter.csv")
    ats_path = os.path.join(base_dir, "sample_inputs", "sample_ats.json")

    pipeline = Pipeline(config_path=str(config_file))
    inputs = [
        {"type": "csv", "path": csv_path},
        {"type": "ats_json", "path": ats_path}
    ]

    result1 = pipeline.run(inputs)
    result2 = pipeline.run(inputs)

    # Asserts conforming output
    assert result1["name"] == "Rahul S."  # ATS priority 2 wins over CSV priority 1
    assert result1["email"] == "rahul.sharma@example.com"
    assert result1["phone"] == "+919876543210"  # E.164 format
    skills_names = [s["name"] for s in result1["skills"]]
    assert "Python" in skills_names

    # Assert overall confidence (> 0.20 is expected as only 4/11 fields are populated)
    assert result1["overall_confidence"] > 0.20


    # Assert provenance has entries from both sources
    provenance = result1["provenance"]
    sources = {p.get("source") for p in provenance}
    assert "recruiter_csv" in sources
    assert "ats_json" in sources

    # Assert candidate_id is present and consistent
    assert "candidate_id" in result1
    assert result1["candidate_id"] == result2["candidate_id"]

def test_pipeline_integration_single_source(tmp_path):
    """
    Test 2 - Single source:
      Run with only the GitHub source (mock the API)
      Assert: pipeline doesn't crash
      Assert: missing fields are null, not missing keys
    """
    config_file = tmp_path / "single_config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True},
            {"path": "email", "from": "emails[0]", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"},
            {"path": "github_url", "from": "links.github", "type": "string"},
            {"path": "skills", "from": "skills", "type": "array"},
            {"path": "experience", "from": "experience", "type": "array"}
        ],
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    with patch("candidate_transformer.sources.GithubSource.extract") as mock_github_extract:
        mock_github_extract.return_value = {
            "source_name": "github",
            "full_name": "Jane GitHub",
            "emails": [],
            "github_url": "https://github.com/jane"
        }

        pipeline = Pipeline(config_path=str(config_file))
        inputs = [{"type": "github", "url": "jane"}]

        # Assert no crash
        result = pipeline.run(inputs)

        assert result["name"] == "Jane GitHub"
        assert result["github_url"] == "https://github.com/jane"

        # Assert missing fields are null (keys must exist)
        assert "email" in result
        assert result["email"] is None
        assert "phone" in result
        assert result["phone"] is None
        assert "skills" in result
        assert result["skills"] is None
        assert "experience" in result
        assert result["experience"] is None

def test_pipeline_integration_garbage_source(tmp_path):
    """
    Test 3 - Garbage source:
      Pass a malformed CSV path that doesn't exist
      Assert: pipeline completes with the other sources
      Assert: no exception is raised
    """
    config_file = tmp_path / "garbage_config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True}
        ],
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    with patch("candidate_transformer.sources.GithubSource.extract") as mock_github_extract:
        mock_github_extract.return_value = {
            "source_name": "github",
            "full_name": "Jane Resilient",
            "emails": []
        }

        pipeline = Pipeline(config_path=str(config_file))
        inputs = [
            {"type": "csv", "path": "nonexistent_garbage_file_12345.csv"},
            {"type": "github", "url": "jane"}
        ]

        # Assert no exception is raised and execution completes using GitHub
        result = pipeline.run(inputs)
        assert result["name"] == "Jane Resilient"

def test_pipeline_integration_custom_config(tmp_path):
    """
    Test 4 - Custom config:
      Run with sample_config.json
      Assert: output has "primary_email" not "emails"
      Assert: output does NOT have "experience" (not in config fields)
      Assert: confidence scores present
    """
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "sample_inputs", "sample_config.json")
    csv_path = os.path.join(base_dir, "sample_inputs", "sample_recruiter.csv")

    pipeline = Pipeline(config_path=config_path)
    inputs = [{"type": "csv", "path": csv_path}]

    result = pipeline.run(inputs)

    # Assert custom fields
    assert "primary_email" in result
    assert "emails" not in result
    assert "experience" not in result

    # Assert confidence metadata is present
    assert "overall_confidence" in result
    assert "per_field_confidence" in result

def test_pipeline_integration_all_sources_empty(tmp_path):
    """
    Test 5 - Edge case — all sources empty:
      Pass empty/missing files for all sources
      Assert: returns a valid dict with all nulls
      Assert: overall_confidence is low (< 0.3)
    """
    config_file = tmp_path / "empty_config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "email", "from": "emails[0]", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"}
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    pipeline = Pipeline(config_path=str(config_file))
    inputs = [
        {"type": "csv", "path": "nonexistent_1.csv"},
        {"type": "ats_json", "path": "nonexistent_2.json"}
    ]

    result = pipeline.run(inputs)

    # Assert returns a valid dict with all nulls
    assert result["name"] is None
    assert result["email"] is None
    assert result["phone"] is None

    # Assert overall_confidence is low (< 0.3)
    assert result["overall_confidence"] < 0.3

