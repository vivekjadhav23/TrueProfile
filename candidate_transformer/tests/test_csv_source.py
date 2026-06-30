import pytest
from candidate_transformer.sources import CsvSource

def make_expected_csv(full_name=None, emails=None, phones=None, current_company=None, title=None):
    return {
        "source_name": "recruiter_csv",
        "full_name": full_name,
        "emails": emails if emails else [],
        "phones": phones if phones else [],
        "headline": title,
        "location": None,
        "linkedin_url": None,
        "github_url": None,
        "years_experience": None,
        "skills": [],
        "experience": [],
        "education": [],
        "current_company": current_company,
        "title": title
    }

def test_csv_source_valid(tmp_path):
    """
    Test extraction from a valid recruiter CSV with all columns and a single data row.
    """
    csv_file = tmp_path / "valid.csv"
    csv_file.write_text(
        "name,email,phone,current_company,title\n"
        "Alice Smith,alice@example.com,+123456789,Google,Software Engineer\n",
        encoding="utf-8"
    )
    
    source = CsvSource()
    res = source.extract(str(csv_file))
    
    assert res == make_expected_csv("Alice Smith", ["alice@example.com"], ["+123456789"], "Google", "Software Engineer")

def test_csv_source_missing_columns(tmp_path):
    """
    Test extraction from a CSV missing some columns (e.g. name, email).
    Graceful fallback should map missing fields to None or empty lists.
    """
    csv_file = tmp_path / "missing_cols.csv"
    csv_file.write_text(
        "phone,current_company,title\n"
        "+987654321,Meta,Product Manager\n",
        encoding="utf-8"
    )
    
    source = CsvSource()
    res = source.extract(str(csv_file))
    
    assert res == make_expected_csv(None, [], ["+987654321"], "Meta", "Product Manager")

def test_csv_source_empty_file(tmp_path):
    """
    Test extraction from a completely empty file. Should log the issue and return empty canonical template.
    """
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("", encoding="utf-8")
    
    source = CsvSource()
    res = source.extract(str(csv_file))
    
    assert res == make_expected_csv()

def test_csv_source_only_headers(tmp_path):
    """
    Test extraction from a CSV that only contains headers but has no data rows.
    """
    csv_file = tmp_path / "only_headers.csv"
    csv_file.write_text("name,email,phone,current_company,title\n", encoding="utf-8")
    
    source = CsvSource()
    res = source.extract(str(csv_file))
    
    assert res == make_expected_csv()
