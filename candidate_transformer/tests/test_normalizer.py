import pytest
from candidate_transformer.pipeline.normalizer import Normalizer

def test_normalize_phones():
    normalizer = Normalizer()
    
    # Valid Indian mobile number (E.164 formatting)
    assert normalizer.normalize_phones(["+91 98765 43210"]) == ["+919876543210"]
    # Valid Indian number parsed with default region="IN"
    assert normalizer.normalize_phones(["9876543210"]) == ["+919876543210"]
    # Invalid numbers (should be skipped)
    assert normalizer.normalize_phones(["12345", "not-a-number"]) == []
    # Mix of valid/invalid
    assert normalizer.normalize_phones(["9876543210", "invalid"]) == ["+919876543210"]

def test_normalize_dates():
    normalizer = Normalizer()
    
    # Months and Years
    assert normalizer.normalize_dates("Jan 2020") == "2020-01"
    assert normalizer.normalize_dates("01/2020") == "2020-01"
    assert normalizer.normalize_dates("2020-01") == "2020-01"
    assert normalizer.normalize_dates("January 2020") == "2020-01"
    
    # Year Only
    assert normalizer.normalize_dates("2020") == "2020"
    
    # Unparseable
    assert normalizer.normalize_dates("unknown date") is None
    assert normalizer.normalize_dates("") is None

def test_normalize_location():
    normalizer = Normalizer()
    
    # 3 parts, country match (India)
    loc1 = normalizer.normalize_location("Mumbai, Maharashtra, India")
    assert loc1 == {"city": "Mumbai", "region": "Maharashtra", "country": "IN"}
    
    # 2 parts, country match (Germany)
    loc2 = normalizer.normalize_location("Berlin, Germany")
    assert loc2 == {"city": "Berlin", "region": None, "country": "DE"}
    
    # Indian State full-name inference (Karnataka -> IN)
    loc3 = normalizer.normalize_location("Bangalore, Karnataka")
    assert loc3 == {"city": "Bangalore", "region": "Karnataka", "country": "IN"}
    
    # Indian State abbreviation inference (TN -> IN)
    loc4 = normalizer.normalize_location("Chennai, TN")
    assert loc4 == {"city": "Chennai", "region": "TN", "country": "IN"}

    # US State abbreviation inference still works
    loc5 = normalizer.normalize_location("Boston, MA")
    assert loc5 == {"city": "Boston", "region": "MA", "country": "US"}
    
    # Unparseable fallback - 1 part
    loc6 = normalizer.normalize_location("SomePlace")
    assert loc6 == {"city": "SomePlace", "region": None, "country": None}
    
    # Unparseable fallback - 2 parts
    loc7 = normalizer.normalize_location("SomeCity, SomeRegion")
    assert loc7 == {"city": "SomeCity", "region": "SomeRegion", "country": None}

def test_normalize_skills():
    normalizer = Normalizer()
    
    # Test semantic matching
    skills = ["python3", "docker container", "extremely_niche_rust_framework"]
    normalized = normalizer.normalize_skills(skills)
    
    assert "Python" in normalized
    assert "Docker" in normalized
    assert "extremely_niche_rust_framework" in normalized
