import json
import pytest
from click.testing import CliRunner
from unittest.mock import patch
from candidate_transformer.cli import main

def test_cli_transform_success(tmp_path):
    """
    Test successful execution of the 'transform' command.
    Checks stdin/stdout response values and the stderr status message format.
    """
    csv_file = tmp_path / "recruiter.csv"
    csv_file.write_text("name,email\nJane,jane@example.com\n", encoding="utf-8")
    
    config_file = tmp_path / "config.json"
    config_data = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True},
            {"path": "email", "from": "emails[0]", "type": "string"}
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    
    with patch("candidate_transformer.pipeline.extractor.Pipeline.run") as mock_pipeline_run:
        mock_pipeline_run.return_value = {
            "name": "Jane",
            "email": "jane@example.com",
            "provenance": [
                {"field": "full_name", "source": "recruiter_csv"},
                {"field": "emails", "source": "recruiter_csv"}
            ],
            "overall_confidence": 0.95
        }
        
        runner = CliRunner()
        result = runner.invoke(main, [
            "transform",
            "--csv", str(csv_file),
            "--config", str(config_file),
            "--pretty"
        ])
        
        assert result.exit_code == 0
        
        # Verify stdout parsed values by isolating the JSON block
        output_str = result.output
        last_brace_idx = output_str.rfind('}')
        assert last_brace_idx != -1
        
        json_str = output_str[:last_brace_idx + 1]
        data = json.loads(json_str)
        assert data["name"] == "Jane"
        assert data["email"] == "jane@example.com"
        
        # Verify summary matches template inside overall output
        assert "✓ Merged 1 sources | confidence: 0.95" in output_str

def test_cli_validate_command(tmp_path):
    """
    Test validation of JSON candidate files using the 'validate' command.
    Checks PASS status for conforming files and FAIL status for non-conforming files.
    """
    # Conforming file (requires full_name)
    valid_file = tmp_path / "result.json"
    valid_file.write_text(json.dumps({
        "full_name": "Jane Doe",
        "emails": ["jane.doe@example.com"],
        "skills": [{"name": "Python", "confidence": 0.9, "sources": ["resume"]}]
    }), encoding="utf-8")
    
    runner = CliRunner()
    result = runner.invoke(main, [
        "validate",
        "--output", str(valid_file)
    ])
    
    assert result.exit_code == 0
    assert "Validation status: PASS" in result.output

    # Non-conforming file (missing full_name)
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps({
        "emails": ["invalid@test.com"]
    }), encoding="utf-8")
    
    result_invalid = runner.invoke(main, [
        "validate",
        "--output", str(invalid_file)
    ])
    
    assert result_invalid.exit_code == 1
    assert "Validation status: FAIL" in result_invalid.stderr
