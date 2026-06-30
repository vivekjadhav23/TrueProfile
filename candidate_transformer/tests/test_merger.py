import pytest
from candidate_transformer.pipeline.merger import Merger

def test_merger_empty_sources():
    """
    Test that merging an empty list of sources, or a list of empty sources,
    returns all canonical fields mapped to None (or empty collections) with an empty provenance.
    """
    merger = Merger()
    expected_empty = {
        "full_name": None,
        "emails": [],
        "phones": [],
        "headline": None,
        "location": {"city": None, "region": None, "country": None},
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "years_experience": None,
        "skills": [],
        "experience": [],
        "education": [],
        "provenance": [],
        "overall_confidence": 0.0
    }
    assert merger.merge([]) == expected_empty
    assert merger.merge([{}, {}]) == expected_empty

def test_merger_single_source():
    """
    Test that merging a single source returns its canonical values directly
    along with a populated provenance list.
    """
    merger = Merger()
    source = {
        "source_name": "resume",
        "full_name": "Alice Bob",
        "emails": ["alice@bob.com"],
        "low_confidence": False
    }
    
    res = merger.merge([source])
    assert res["full_name"] == "Alice Bob"
    assert res["emails"] == ["alice@bob.com"]
    assert res["location"] == {"city": None, "region": None, "country": None}
    assert len(res["provenance"]) == 2
    assert {"field": "full_name", "source": "resume", "method": "llm_extraction"} in res["provenance"]

def test_merger_two_conflicting_sources():
    """
    Test merging two conflicting sources.
    Asserts that higher priority source wins even if lower priority has a longer (more complete) string.
    Asserts that same-priority fields resolve by completeness (longer string).
    """
    merger = Merger()
    
    # Source 1: recruiter_csv (priority 1) - has longer name
    src1 = {
        "source_name": "recruiter_csv",
        "full_name": "Alice Charlotte Bob",
        "headline": "Lead Architect",
        "years_experience": 10
    }
    
    # Source 2: resume (priority 5) - has higher priority but shorter name
    src2 = {
        "source_name": "resume",
        "full_name": "Alice Bob",
        "years_experience": None
    }
    
    res = merger.merge([src1, src2])
    
    # Priority wins: resume (Alice Bob) wins over recruiter_csv (Alice Charlotte Bob)
    assert res["full_name"] == "Alice Bob"
    # recruiter_csv wins for headline since resume has none
    assert res["headline"] == "Lead Architect"
    # recruiter_csv wins for years_experience since resume has none/null
    assert res["years_experience"] == 10
    
    # Check provenance
    assert {"field": "full_name", "source": "resume", "method": "llm_extraction"} in res["provenance"]
    assert {"field": "headline", "source": "recruiter_csv", "method": "csv_parsing"} in res["provenance"]

def test_merger_three_sources_complex():
    """
    Test merging three sources.
    Asserts array unions and de-duplications.
    Asserts object array unions by unique key (higher priority wins during collisions).
    """
    merger = Merger()
    
    src_resume = {
        "source_name": "resume",
        "full_name": "Alice Bob",
        "emails": ["alice@resume.com"],
        "skills": ["Python", "Rust"],
        "experience": [
            {"company": "Google", "title": "Software Engineer", "summary": "Did resume things"}
        ],
        "low_confidence": False
    }
    
    src_github = {
        "source_name": "github",
        "full_name": "Alice",
        "github_url": "github.com/alice",
        "skills": ["Go", "Python"],
        "experience": [
            {"company": "Google", "title": "Software Engineer", "summary": "Did git things"} # Colliding key
        ]
    }
    
    src_csv = {
        "source_name": "recruiter_csv",
        "emails": ["alice.bob@csv.com"],
        "phones": ["9876543210"],
        "experience": [
            {"company": "Meta", "title": "Manager", "summary": "Managed stuff"} # Unique key
        ]
    }
    
    res = merger.merge([src_resume, src_github, src_csv])
    
    # Single field: priority (resume > github)
    assert res["full_name"] == "Alice Bob"
    
    # Array fields: Union and deduplicate
    assert sorted(res["emails"]) == sorted(["alice@resume.com", "alice.bob@csv.com"])
    skills_names = [s["name"] for s in res["skills"]]
    assert sorted(skills_names) == sorted(["Python", "Rust", "Go"])
    assert res["phones"] == ["9876543210"]
    assert res["links"]["github"] == "github.com/alice"
    
    # Object field union:
    # 1. Google/Software Engineer: collision between resume and github.
    #    Resume has priority 5, github has priority 3. So resume wins and we get "Did resume things".
    # 2. Meta/Manager: unique key from recruiter_csv.
    assert len(res["experience"]) == 2
    google_exp = [e for e in res["experience"] if e["company"] == "Google"][0]
    meta_exp = [e for e in res["experience"] if e["company"] == "Meta"][0]
    
    assert google_exp["summary"] == "Did resume things"
    assert meta_exp["summary"] == "Managed stuff"
