import logging
from typing import Any

logger = logging.getLogger(__name__)

CANONICAL_FIELDS = [
    "full_name",
    "emails",
    "phones",
    "headline",
    "location",
    "links",
    "years_experience",
    "skills",
    "experience",
    "education"
]

class ConfidenceScorer:
    """
    Computes confidence scores for candidate profile fields and overall record.
    """
    def __init__(self):
        pass

    def run(self, candidate_data: dict) -> dict:
        """
        Evaluate candidate data fields and append confidence metadata.
        """
        provenance = candidate_data.get("provenance", [])
        return self.score_record(candidate_data, provenance)

    def score_field(self, field_name: str, value: Any, sources_that_provided_it: list[str]) -> float:
        """
        Compute the confidence score for a single field.
        """
        base = 0.0
        
        # 1. Non-null value check (not None, and not empty collections)
        if value is not None and value != "" and value != [] and value != {"city": None, "region": None, "country": None} and value != {"linkedin": None, "github": None, "portfolio": None, "other": []}:
            base += 0.5
            
        # 2. Agreement bonus (agreement between multiple sources)
        if len(sources_that_provided_it) > 1:
            base += 0.2
            
        # 3. Critical field bonus
        if field_name in ["full_name", "emails"]:
            base += 0.2
            
        # 4. Trusted source bonus (Resume, LinkedIn, GitHub, ATS JSON)
        trusted_sources = {"resume", "linkedin", "github", "ats_json"}
        if any(s in trusted_sources for s in sources_that_provided_it):
            base += 0.2
            
        return round(min(base, 1.0), 2)

    def score_record(self, merged: dict, provenance: list[dict]) -> dict:
        """
        Evaluate and update the record with field-level and overall confidence scores.
        """
        record = merged.copy()
        per_field_confidence = {}
        
        # Ensure provenance is a list
        prov_list = provenance if isinstance(provenance, list) else []

        for field in CANONICAL_FIELDS:
            val = record.get(field)
            
            # Find unique sources that contributed to this field or its subfields in provenance
            sources = list({
                entry.get("source") 
                for entry in prov_list 
                if entry.get("field") and (entry.get("field") == field or entry.get("field").startswith(field + ".")) and entry.get("source")
            })
            
            score = self.score_field(field, val, sources)
            per_field_confidence[field] = score

        record["per_field_confidence"] = per_field_confidence
        
        scores = [v for v in per_field_confidence.values() if v > 0]
        if scores:
            record["overall_confidence"] = sum(scores) / len(scores)
        else:
            record["overall_confidence"] = 0.0

        return record
