import json
import logging
import re
from .base import BaseSource

logger = logging.getLogger(__name__)

class ATSJSONSource(BaseSource):
    """
    Source reader for ATS JSON export files.
    """

    def extract(self, input_path_or_url: str) -> dict:
        """
        Extract candidate details from an ATS JSON file.

        Maps the ATS-specific fields to our canonical raw dict.
        """
        from pathlib import Path
        path = Path(input_path_or_url)
        try:
            with path.open(mode='r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.warning(f"ATS JSON content in {input_path_or_url} is not a valid JSON dict.")
                return {
                    "source_name": "ats_json",
                    "full_name": None,
                    "emails": [],
                    "phones": [],
                    "headline": None,
                    "location": None,
                    "linkedin_url": None,
                    "github_url": None,
                    "years_experience": None,
                    "skills": [],
                    "experience": [],
                    "education": [],
                    "current_company": None,
                    "title": None
                }

            applicant_name = data.get("applicant_name")
            contact_email = data.get("contact_email")
            contact_phone = data.get("contact_phone")
            employer = data.get("employer")
            role = data.get("role")
            bio = data.get("bio")
            tech_stack = data.get("tech_stack")

            headline = None
            if bio and isinstance(bio, str):
                sentences = re.split(r'(?<=[.!?])\s+', bio.strip())
                if sentences:
                    headline = sentences[0]

            skills = []
            if tech_stack is not None:
                skills = tech_stack if isinstance(tech_stack, list) else [tech_stack]

            result = {
                "source_name": "ats_json",
                "full_name": applicant_name,
                "emails": [contact_email] if contact_email else [],
                "phones": [contact_phone] if contact_phone else [],
                "headline": headline,
                "location": None,
                "linkedin_url": None,
                "github_url": None,
                "years_experience": None,
                "skills": skills,
                "experience": [],
                "education": []
            }
            
            result["current_company"] = employer
            result["title"] = role

            # DEBUG: raw extracted values before normalization
            logger.debug(f"Raw ATS JSON extraction: {result}")

            # WARNING: when a source fails or field is null
            for k, v in result.items():
                if v is None or v == [] or v == {}:
                    logger.warning(f"ATS JSON source field '{k}' is null or empty.")

            # INFO: which sources were processed
            logger.info(f"Processed ATS JSON source: {input_path_or_url}")

            return result

        except Exception as e:
            logger.warning(f"Failed to extract ATS JSON source from {input_path_or_url}: {e}")
            logger.error(f"Error reading ATS JSON source: {e}", exc_info=True)
            return {
                "source_name": "ats_json",
                "full_name": None,
                "emails": [],
                "phones": [],
                "headline": None,
                "location": None,
                "linkedin_url": None,
                "github_url": None,
                "years_experience": None,
                "skills": [],
                "experience": [],
                "education": [],
                "current_company": None,
                "title": None
            }

# Alias to support AtsJsonSource naming
AtsJsonSource = ATSJSONSource
