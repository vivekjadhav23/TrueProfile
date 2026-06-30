import pytest
from candidate_transformer.sources import AtsJsonSource

def make_expected_ats(full_name=None, emails=None, phones=None, headline=None, skills=None, current_company=None, title=None):
    return {
        "source_name": "ats_json",
        "full_name": full_name,
        "emails": emails if emails else [],
        "phones": phones if phones else [],
        "headline": headline,
        "location": None,
        "linkedin_url": None,
        "github_url": None,
        "years_experience": None,
        "skills": skills if skills is not None else [],
        "experience": [],
        "education": [],
        "current_company": current_company,
        "title": title
    }

def test_ats_json_source_valid(tmp_path):
    """
    Test extraction from a valid ATS JSON with all fields present.
    """
    json_file = tmp_path / "valid.json"
    json_file.write_text(
        '{\n'
        '  "applicant_name": "Jane Doe",\n'
        '  "contact_email": "jane@example.com",\n'
        '  "contact_phone": "+1-555-0100",\n'
        '  "employer": "Acme Corp",\n'
        '  "role": "Engineer",\n'
        '  "bio": "Experienced backend developer. She loves Python.",\n'
        '  "tech_stack": ["Python", "Docker", "AWS"]\n'
        '}',
        encoding="utf-8"
    )
    
    source = AtsJsonSource()
    res = source.extract(str(json_file))
    assert res == make_expected_ats(
        "Jane Doe", ["jane@example.com"], ["+1-555-0100"],
        "Experienced backend developer.", ["Python", "Docker", "AWS"],
        "Acme Corp", "Engineer"
    )

def test_ats_json_source_missing_fields(tmp_path):
    """
    Test extraction from an ATS JSON missing optional fields.
    """
    json_file = tmp_path / "missing.json"
    json_file.write_text(
        '{\n'
        '  "applicant_name": "Jane Doe"\n'
        '}',
        encoding="utf-8"
    )
    
    source = AtsJsonSource()
    res = source.extract(str(json_file))
    assert res == make_expected_ats("Jane Doe")

def test_ats_json_source_invalid_json(tmp_path):
    """
    Test extraction from a malformed/invalid JSON file. Should log error and return empty canonical template.
    """
    json_file = tmp_path / "invalid.json"
    json_file.write_text(
        '{\n'
        '  "applicant_name": "Jane Doe",\n'
        '  "contact_email": \n'
        '}',
        encoding="utf-8"
    )
    
    source = AtsJsonSource()
    res = source.extract(str(json_file))
    assert res == make_expected_ats()
