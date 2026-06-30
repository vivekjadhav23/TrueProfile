import pytest
from candidate_transformer.pipeline.confidence import ConfidenceScorer

def test_confidence_scorer_bounds():
    """
    Verify that single-field confidence scores are correctly calculated and bound between 0.0 and 1.0.
    """
    scorer = ConfidenceScorer()
    
    # Minimum boundary: null value, no sources
    min_score = scorer.score_field("headline", None, [])
    assert min_score == 0.0
    assert 0.0 <= min_score <= 1.0
    
    # Maximum boundary: valid value, agreement (>1 source), critical field (full_name), trusted source (resume)
    max_score = scorer.score_field("full_name", "Alice Bob", ["resume", "github"])
    # 0.4 (val) + 0.3 (agreement) + 0.2 (critical) + 0.1 (trusted) = 1.0
    assert max_score == 1.0
    assert 0.0 <= max_score <= 1.0

    # Check capping at 1.0
    cap_score = scorer.score_field("emails", "alice@example.com", ["resume", "linkedin", "github"])
    assert cap_score == 1.0
    assert 0.0 <= cap_score <= 1.0

def test_confidence_scorer_record():
    """
    Verify that record-level confidence scoring calculates accurate field-level values,
    computes the mean score correctly, and remains inside [0.0, 1.0] bounds.
    """
    scorer = ConfidenceScorer()
    
    merged = {
        "full_name": "Alice Bob",
        "emails": ["alice@example.com"],
        "phones": [],
        "headline": "Software Engineer",
        "location": {"city": None, "region": None, "country": None},
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "years_experience": None,
        "skills": [],
        "experience": [],
        "education": []
    }
    
    provenance = [
        {"field": "full_name", "source": "resume"},
        {"field": "full_name", "source": "github"},
        {"field": "emails", "source": "resume"},
        {"field": "headline", "source": "recruiter_csv"}
    ]
    
    res = scorer.score_record(merged, provenance)
    
    per_field = res["per_field_confidence"]
    assert isinstance(per_field, dict)
    assert len(per_field) == 10
    
    # Check that all individual field scores are in bounds
    for field, score in per_field.items():
        assert 0.0 <= score <= 1.0
        
    # Check individual field calculations:
    # full_name: value (0.5) + agreement (0.2) + critical (0.2) + trusted (0.2) = 1.0
    assert per_field["full_name"] == 1.0
    
    # emails: value (0.5) + critical (0.2) + trusted (0.2) = 0.9
    assert per_field["emails"] == 0.9
    
    # headline: value (0.5) = 0.5
    assert per_field["headline"] == 0.5
    
    # location: None/empty = 0.0
    assert per_field["location"] == 0.0
    
    # Check overall confidence score matches the mean of the fields with confidence > 0
    expected_sum = 1.0 + 0.9 + 0.5  # 2.4
    expected_mean = expected_sum / 3
    assert pytest.approx(res["overall_confidence"]) == expected_mean
    assert 0.0 <= res["overall_confidence"] <= 1.0
