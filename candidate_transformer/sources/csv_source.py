import csv
import logging
from .base import BaseSource

logger = logging.getLogger(__name__)

class CSVSource(BaseSource):
    """
    Source reader for CSV format data.
    """

    def extract(self, input_path_or_url: str) -> dict:
        """
        Extract candidate details from a recruiter CSV file.

        Reads a recruiter CSV with columns: name, email, phone, current_company, title.
        Returns a normalized raw dict:
        {
          "source_name": "recruiter_csv",
          "full_name": ...,
          "emails": [email] if email else [],
          "phones": [phone] if phone else [],
          "current_company": ...,
          "title": ...,
        }
        """
        from pathlib import Path
        path = Path(input_path_or_url)
        try:
            with path.open(mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                row = next(reader, None)
                if row is None:
                    logger.warning(f"CSV source {input_path_or_url} has no data rows.")
                    return {
                        "source_name": "recruiter_csv",
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
                
                # Normalize keys by removing spaces, underscores, and lowercasing to handle header variations
                normalized_row = {}
                for k, v in row.items():
                    if k:
                        norm_k = k.strip().lower().replace(" ", "").replace("_", "")
                        normalized_row[norm_k] = v

                import re

                name = normalized_row.get("name") or normalized_row.get("fullname")
                email = normalized_row.get("email")
                phone = normalized_row.get("phone")
                headline = normalized_row.get("headline")
                location = normalized_row.get("location")
                linkedin_url = normalized_row.get("linkedinurl") or normalized_row.get("linkedin")
                github_url = normalized_row.get("githuburl") or normalized_row.get("github")
                years_exp = normalized_row.get("yearsexperience") or normalized_row.get("experienceyears")
                skills = normalized_row.get("skills")
                experience = normalized_row.get("experience")
                education = normalized_row.get("education")

                current_company = normalized_row.get("currentcompany") or normalized_row.get("company")
                title = normalized_row.get("currentrole") or normalized_row.get("title") or normalized_row.get("role")

                full_name = name.strip() if name and isinstance(name, str) and name.strip() else None
                email_val = email.strip() if email and isinstance(email, str) and email.strip() else None
                phone_val = phone.strip() if phone and isinstance(phone, str) and phone.strip() else None
                current_company_val = current_company.strip() if current_company and isinstance(current_company, str) and current_company.strip() else None
                title_val = title.strip() if title and isinstance(title, str) and title.strip() else None
                # ISSUE 3 - headline is null even though CSV has a title column
                headline_val = row.get("title") or row.get("headline") or None
                location_val = location.strip() if location and isinstance(location, str) and location.strip() else None
                linkedin_url_val = linkedin_url.strip() if linkedin_url and isinstance(linkedin_url, str) and linkedin_url.strip() else None
                github_url_val = github_url.strip() if github_url and isinstance(github_url, str) and github_url.strip() else None

                years_experience_val = None
                if years_exp is not None:
                    try:
                        years_experience_val = float(str(years_exp).strip())
                    except ValueError:
                        pass

                skills_val = []
                if skills and isinstance(skills, str):
                    skills_val = [s.strip() for s in re.split(r'[;,]', skills) if s.strip()]

                experience_val = []
                if experience and isinstance(experience, str):
                    exp_match = re.search(r'(.*?)\s+at\s+(.*?)\s*\((.*?)\s*-\s*(.*?)\)', experience)
                    if exp_match:
                        experience_val.append({
                            "title": exp_match.group(1).strip(),
                            "company": exp_match.group(2).strip(),
                            "start": exp_match.group(3).strip(),
                            "end": exp_match.group(4).strip(),
                            "summary": None
                        })
                    else:
                        experience_val.append({
                            "title": None,
                            "company": None,
                            "start": None,
                            "end": None,
                            "summary": experience.strip()
                        })

                education_val = []
                if education and isinstance(education, str):
                    edu_match = re.search(r'(.*?),\s*(.*?)\s*\((\d{4})\s*-\s*(\d{4})\)', education)
                    if edu_match:
                        degree_field = edu_match.group(1).strip()
                        deg_val = degree_field
                        field_val = None
                        
                        prefixes = [r'\bB\.E\b', r'\bB\.E\.\b', r'\bB\.Tech\b', r'\bM\.Tech\b', r'\bB\.Sc\b', r'\bM\.Sc\b', r'\bB\.A\b', r'\bM\.A\b', r'\bB\.S\b', r'\bM\.S\b', r'\bPh\.D\b', r'\bPhD\b']
                        matched_prefix = None
                        for pref in prefixes:
                            m_pref = re.match(pref, deg_val, re.IGNORECASE)
                            if m_pref:
                                matched_prefix = m_pref.group(0)
                                break
                        if matched_prefix:
                            field_part = deg_val[len(matched_prefix):].strip()
                            field_part = re.sub(r'^[\s\.\-\–\—\s]+|[\s\.\-\–\—\s]+$', '', field_part).strip()
                            if field_part:
                                field_val = field_part
                                deg_val = matched_prefix
                                
                        education_val.append({
                            "institution": edu_match.group(2).strip(),
                            "degree": deg_val,
                            "field": field_val,
                            "end_year": edu_match.group(4).strip()
                        })
                    else:
                        education_val.append({
                            "institution": None,
                            "degree": None,
                            "field": None,
                            "end_year": None,
                            "summary": education.strip()
                        })

                result = {
                    "source_name": "recruiter_csv",
                    "full_name": full_name,
                    "emails": [email_val] if email_val else [],
                    "phones": [phone_val] if phone_val else [],
                    "headline": headline_val,
                    "location": location_val,
                    "linkedin_url": linkedin_url_val,
                    "github_url": github_url_val,
                    "years_experience": years_experience_val,
                    "skills": skills_val,
                    "experience": experience_val,
                    "education": education_val
                }

                result["current_company"] = current_company_val
                result["title"] = title_val

                # DEBUG: raw extracted values before normalization
                logger.debug(f"Raw CSV extraction: {result}")

                # WARNING: when a source fails or field is null
                for k, v in result.items():
                    if v is None or v == [] or v == {}:
                        logger.warning(f"CSV source field '{k}' is null or empty.")

                # INFO: which sources were processed
                logger.info(f"Processed CSV source: {input_path_or_url}")

                return result
        except Exception as e:
            logger.warning(f"Failed to extract CSV source from {input_path_or_url}: {e}")
            logger.error(f"Error reading CSV source: {e}", exc_info=True)
            return {
                "source_name": "recruiter_csv",
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

# Alias to support CsvSource naming
CsvSource = CSVSource
