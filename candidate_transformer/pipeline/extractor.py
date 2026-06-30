import os
import json
import hashlib
import logging
from typing import Any
from jsonschema import validate

from candidate_transformer.sources import CsvSource, AtsJsonSource, GithubSource, ResumeSource, RecruiterNotesSource
from candidate_transformer.pipeline.normalizer import Normalizer
from candidate_transformer.pipeline.merger import Merger
from candidate_transformer.pipeline.confidence import ConfidenceScorer
from candidate_transformer.pipeline.projector import Projector

logger = logging.getLogger(__name__)

SOURCE_CLASSES = {
    "csv": CsvSource,
    "ats_json": AtsJsonSource,
    "github": GithubSource,
    "resume": ResumeSource,
    "recruiter_notes": RecruiterNotesSource
}

from pathlib import Path

def load_config(config_path: str) -> dict:
    """Helper to load JSON configuration file using pathlib.Path."""
    try:
        path = Path(config_path)
        with path.open(mode='r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {e}")
        return {}

class Pipeline:
    """
    Orchestrates the entire candidate transformer pipeline:
    extracting, normalizing, merging, scoring, projecting, and validating profiles.
    """
    def __init__(self, config_path: str = None):
        self.normalizer = Normalizer()
        self.merger = Merger()
        self.scorer = ConfidenceScorer()
        self.projector = Projector()
        self.config = load_config(config_path) if config_path else None

    def run(self, inputs: list[dict]) -> dict:
        """
        Run the candidate transformer pipeline on a list of inputs.
        """
        # Step 1 - Detect & Extract
        extracted_data = []
        for inp in inputs:
            source_type = inp.get("type")
            input_val = inp.get("path") or inp.get("url")
            
            if not source_type or not input_val:
                logger.warning(f"Invalid input configuration: {inp}")
                continue

            source_class = SOURCE_CLASSES.get(source_type.lower())
            if not source_class:
                logger.warning(f"Unsupported source type: {source_type}")
                continue

            try:
                source_instance = source_class()
                data = source_instance.extract(input_val)
                if data:
                    extracted_data.append(data)
            except Exception as e:
                logger.warning(f"Error extracting from {source_type} ({input_val}): {e}")
                logger.error(f"Error extracting from {source_type} ({input_val}): {e}", exc_info=True)

        # Dynamic Enrichment: check for discovered github_urls to dynamically fetch Github profile
        github_urls_found = set()
        for data in extracted_data:
            url = data.get("github_url")
            if url:
                github_urls_found.add(url)
            links = data.get("links")
            if isinstance(links, dict) and links.get("github"):
                github_urls_found.add(links.get("github"))
                
        already_has_github = any(inp.get("type", "").lower() == "github" for inp in inputs)
        
        if github_urls_found and not already_has_github:
            for github_url in sorted(list(github_urls_found)):
                try:
                    logger.info(f"Dynamically extracting GitHub profile for discovered URL: {github_url}")
                    github_source = GithubSource()
                    git_data = github_source.extract(github_url)
                    if git_data:
                        non_empty_keys = [k for k, v in git_data.items() if k != "source_name" and v is not None and v != "" and v != [] and v != {}]
                        if non_empty_keys:
                            extracted_data.append(git_data)
                except Exception as e:
                    logger.warning(f"Failed to dynamically extract from GitHub URL {github_url}: {e}")

        # Step 2 - Normalize each raw extract
        normalized_data = []
        for data in extracted_data:
            normalized = data.copy()
            if "phones" in normalized and normalized["phones"]:
                normalized["phones"] = self.normalizer.normalize_phones(normalized["phones"])
            if "skills" in normalized and normalized["skills"]:
                normalized["skills"] = self.normalizer.normalize_skills(normalized["skills"])
            if "location" in normalized and normalized["location"]:
                normalized["location"] = self.normalizer.normalize_location(normalized["location"])

            if "experience" in normalized and isinstance(normalized["experience"], list):
                norm_exp = []
                for exp in normalized["experience"]:
                    if isinstance(exp, dict):
                        new_exp = exp.copy()
                        if "start" in new_exp and new_exp["start"]:
                            new_exp["start"] = self.normalizer.normalize_dates(new_exp["start"])
                        if "end" in new_exp and new_exp["end"]:
                            norm_end = self.normalizer.normalize_dates(new_exp["end"])
                            if norm_end:
                                new_exp["end"] = norm_end
                            elif str(new_exp["end"]).lower() in ["present", "current"]:
                                new_exp["end"] = str(new_exp["end"]).lower()
                        norm_exp.append(new_exp)
                normalized["experience"] = norm_exp

            if "education" in normalized and isinstance(normalized["education"], list):
                norm_edu = []
                for edu in normalized["education"]:
                    if isinstance(edu, dict):
                        new_edu = edu.copy()
                        if "end_year" in new_edu and new_edu["end_year"]:
                            if isinstance(new_edu["end_year"], (int, float)):
                                pass
                            else:
                                norm_year = self.normalizer.normalize_dates(str(new_edu["end_year"]))
                                if norm_year:
                                    new_edu["end_year"] = norm_year
                        norm_edu.append(new_edu)
                normalized["education"] = norm_edu

            normalized_data.append(normalized)

        # Step 3 - Merge
        merged = self.merger.merge(normalized_data)
        
        # Track unique contributing sources count before projecting them away
        provenance = merged.get("provenance", [])
        self.unique_sources_count = len({entry.get("source") for entry in provenance if entry.get("source")})

        # Step 4 - Score confidence
        scored = self.scorer.score_record(merged, merged.get("provenance", []))
        self.canonical_record = scored.copy()

        # Validate the canonical Candidate model immediately after merging/normalization, before projection
        from candidate_transformer.pipeline.validator import Validator
        validator_inst = Validator()
        validator_inst.validate(scored)

        # Step 5 - Project (if config provided)
        if self.config:
            projected = self.projector.apply(scored, self.config)
        else:
            projected = scored.copy()

        # Add a candidate_id field: SHA256(sorted_emails_joined + full_name_lowercase) truncated to 16 chars
        full_name = scored.get("full_name") or ""
        emails = scored.get("emails") or []
        
        cleaned_emails = sorted(list(set(email.strip().lower() for email in emails if email)))
        sorted_emails_joined = "".join(cleaned_emails)
        full_name_lowercase = full_name.strip().lower()
        
        input_str = f"{sorted_emails_joined}{full_name_lowercase}"
        candidate_hash = hashlib.sha256(input_str.encode("utf-8")).hexdigest()
        projected["candidate_id"] = candidate_hash[:16]

        return projected
