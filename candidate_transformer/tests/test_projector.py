import pytest
from candidate_transformer.pipeline.projector import Projector

def test_projector_field_rename_and_array_indexing():
    """
    Verify path resolution, array index plucks (e.g. emails[0]),
    and array object property mappings (e.g. experience[].company).
    """
    projector = Projector()
    
    canonical = {
        "full_name": "Alice Bob",
        "emails": ["alice@example.com", "bob@example.com"],
        "phones": ["9876543210"],
        "skills": ["Python", "Rust"],
        "experience": [
            {"company": "Google", "title": "SWE"},
            {"company": "Meta", "title": "Manager"}
        ],
        "per_field_confidence": {
            "full_name": 0.9,
            "emails": 0.8,
            "phones": 0.7,
            "skills": 0.6,
            "experience": 0.5
        },
        "overall_confidence": 0.7
    }
    
    config = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "primary_email", "from": "emails[0]", "type": "string"},
            {"path": "companies", "from": "experience[].company", "type": "array"}
        ],
        "include_confidence": False,
        "on_missing": "null"
    }
    
    res = projector.apply(canonical, config)
    
    assert res["name"] == "Alice Bob"
    assert res["primary_email"] == "alice@example.com"
    assert res["companies"] == ["Google", "Meta"]
    # Check that confidence keys are omitted since include_confidence is False
    assert "overall_confidence" not in res
    assert "per_field_confidence" not in res

def test_projector_on_missing_policies():
    """
    Verify 'null', 'omit', and 'error' missing value policies under config rule projection.
    """
    projector = Projector()
    
    canonical = {
        "full_name": "Alice Bob",
        "emails": [],
        "phones": None
    }
    
    # 1. Policy: null
    config_null = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"},
            {"path": "email", "from": "emails[0]", "type": "string", "required": False}
        ],
        "on_missing": "null"
    }
    res_null = projector.apply(canonical, config_null)
    assert res_null["name"] == "Alice Bob"
    assert res_null["phone"] is None
    assert res_null["email"] is None
    
    # 2. Policy: omit
    config_omit = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string"},
            {"path": "email", "from": "emails[0]", "type": "string", "required": False}
        ],
        "on_missing": "omit"
    }
    res_omit = projector.apply(canonical, config_omit)
    assert res_omit == {"name": "Alice Bob"}

    # 3. Policy: error (not required, passes)
    config_error_not_required = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string", "required": False}
        ],
        "on_missing": "error"
    }
    res_err_ok = projector.apply(canonical, config_error_not_required)
    assert res_err_ok["name"] == "Alice Bob"
    assert res_err_ok["phone"] is None

    # 4. Policy: error (required field missing, populates error placeholder string)
    config_error_required = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "phone", "from": "phones[0]", "type": "string", "required": True}
        ],
        "on_missing": "error"
    }
    res_err_required = projector.apply(canonical, config_error_required)
    assert res_err_required["phone"] == "ERROR: phone is required but missing"

def test_projector_confidence_toggle_and_normalize():
    """
    Verify that include_confidence appends confidence metadata to projected fields,
    and verify E164/canonical normalization integration.
    """
    projector = Projector()
    
    canonical = {
        "full_name": "Alice Bob",
        "phones": ["9876543210"],
        "skills": ["python3"],
        "per_field_confidence": {
            "full_name": 1.0,
            "phones": 0.8,
            "skills": 0.7
        },
        "overall_confidence": 0.83
    }
    
    config = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "phone", "from": "phones[0]", "normalize": "E164", "type": "string"},
            {"path": "languages", "from": "skills", "normalize": "canonical", "type": "array"}
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    
    res = projector.apply(canonical, config)
    
    # Assert E164 formatting (defaulting to India number formatting) and skill mapping
    assert res["phone"] == "+919876543210"
    assert res["languages"] == ["Python"]
    
    # Assert mapped confidence metadata
    assert res["overall_confidence"] == 0.83
    assert res["per_field_confidence"] == {
        "name": 1.0,
        "phone": 0.8,
        "languages": 0.7
    }
