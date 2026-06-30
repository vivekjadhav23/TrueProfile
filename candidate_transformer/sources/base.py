from abc import ABC, abstractmethod

class BaseSource(ABC):
    """
    Abstract base class for all data sources in the candidate-transformer pipeline.
    """

    @abstractmethod
    def extract(self, input_path_or_url: str) -> dict:
        """
        Extract data from the specified input path or URL.

        Args:
            input_path_or_url (str): The path or URL to extract data from.

        Returns:
            dict: A dictionary containing the raw extracted fields.
                  MUST include a "source_name" key identifying the source type.
        """
        pass

class RecruiterNotesSource(BaseSource):
    """
    Source reader for recruiter notes (plain text).
    """
    def extract(self, input_path_or_url: str) -> dict:
        """
        Extract email and phone fields from recruiter notes text files.
        """
        import re
        import logging
        from pathlib import Path
        logger = logging.getLogger(__name__)
        path = Path(input_path_or_url)
        
        def empty_result():
            return {
                "source_name": "recruiter_notes",
                "full_name": None,
                "emails": [],
                "phones": [],
                "location": None,
                "linkedin_url": None,
                "github_url": None,
                "headline": None,
                "years_experience": None,
                "skills": [],
                "experience": [],
                "education": []
            }

        try:
            with path.open(mode='r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            emails = re.findall(r'[\w.-]+@[\w.-]+\.\w+', text)
            phones = re.findall(r'[\+]?[\d\s\-\(\)]{10,}', text)
            
            result = empty_result()
            result["emails"] = sorted(list(set(emails)))
            result["phones"] = sorted(list(set(phones)))

            # DEBUG: raw extracted values before normalization
            logger.debug(f"Raw Recruiter Notes extraction: {result}")

            # WARNING: when a source fails or field is null
            for k, v in result.items():
                if v is None or v == [] or v == {}:
                    logger.warning(f"Recruiter Notes source field '{k}' is null or empty.")

            # INFO: which sources were processed
            logger.info(f"Processed recruiter notes source: {input_path_or_url}")

            return result
        except Exception as e:
            logger.warning(f"Failed to extract recruiter notes from {input_path_or_url}: {e}")
            logger.error(f"Error reading recruiter notes: {e}", exc_info=True)
            return empty_result()

