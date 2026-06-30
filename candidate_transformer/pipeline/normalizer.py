import re
import datetime
import logging
import phonenumbers
from dateutil import parser

logger = logging.getLogger(__name__)

# Hardcoded list of 50 common tech skills for default fallback
DEFAULT_CANONICAL_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Swift", "Kotlin",
    "Ruby", "PHP", "HTML", "CSS", "SQL", "NoSQL", "Docker", "Kubernetes", "AWS", "Azure",
    "GCP", "Git", "React", "Angular", "Vue.js", "Node.js", "Django", "Flask", "Spring Boot", "TensorFlow",
    "PyTorch", "scikit-learn", "Pandas", "NumPy", "Apache Spark", "Hadoop", "Linux", "Bash", "Machine Learning", "Deep Learning",
    "Data Science", "DevOps", "CI/CD", "Terraform", "Ansible", "GraphQL", "REST API", "Microservices", "Agile", "Scrum"
]

# Common country names to ISO-3166-alpha-2 mapping
COMMON_COUNTRIES = {
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "canada": "CA",
    "germany": "DE",
    "deutschland": "DE",
    "france": "FR",
    "india": "IN",
    "australia": "AU",
    "brazil": "BR",
    "brasil": "BR",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "netherlands": "NL",
    "switzerland": "CH",
    "spain": "ES",
    "italy": "IT",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "ireland": "IE",
    "belgium": "BE",
    "austria": "AT",
    "new zealand": "NZ",
    "us": "US",
    "in": "IN",
    "ca": "CA",
    "gb": "GB",
    "de": "DE",
    "fr": "FR",
    "jp": "JP",
    "cn": "CN",
    "sg": "SG",
    "au": "AU",
}

# US states to resolve implicit US country code
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming"
}

# Indian states and union territories for implicit country code resolution
IN_STATES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DN", "DD", "DL", "GA", "GJ", "HR", "HP", "JK", "LA", "JH", "KA", "KL", "LD",
    "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "PY", "PB", "RJ", "SK", "TN", "TS", "TR", "UP", "UK", "WB",
    "andaman and nicobar", "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chandigarh", "chhattisgarh",
    "dadra and nagar haveli", "daman and diu", "delhi", "goa", "gujarat", "haryana", "himachal pradesh", "jammu and kashmir",
    "ladakh", "jharkhand", "karnataka", "kerala", "lakshadweep", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "puducherry", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
    "uttar pradesh", "uttarakhand", "west bengal"
}

class Normalizer:
    """
    Normalizes raw extracted fields into standard data types and formats.
    """
    def __init__(self):
        self._model = None

    @property
    def model(self):
        """Lazy loader for SentenceTransformer."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model

    def normalize_phones(self, phones: list[str], region="IN") -> list[str]:
        """
        Parse and format input phone numbers to E.164 (+12345678900).
        Invalid phones are skipped.
        """
        if not phones:
            return []
        valid_phones = []
        for phone in phones:
            try:
                parsed = phonenumbers.parse(phone, region)
                if phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    valid_phones.append(formatted)
            except Exception as e:
                logger.debug(f"Skipping invalid phone {phone}: {e}")
        return valid_phones

    def normalize_dates(self, date_str: str) -> str | None:
        """
        Accept formats: "Jan 2020", "01/2020", "2020-01", "January 2020", "2020".
        Return YYYY-MM format, or YYYY if only year is specified/resolved, or None if unparseable.
        """
        if not date_str or not isinstance(date_str, str):
            return None
        try:
            # We use two defaults with different months to check if date_str specifies a month
            d1 = datetime.datetime(2000, 1, 15)
            d2 = datetime.datetime(2000, 12, 15)
            
            p1 = parser.parse(date_str, default=d1, fuzzy=True)
            p2 = parser.parse(date_str, default=d2, fuzzy=True)
            
            if p1.month == p2.month:
                return f"{p1.year:04d}-{p1.month:02d}"
            else:
                return f"{p1.year:04d}"
        except Exception:
            return None

    def normalize_skills(self, skills: list[str], canonical_list: list[str] = None) -> list[str]:
        """
        Find closest canonical skills using sentence similarity.
        Maps to canonical name if similarity > 0.75; otherwise keeps original name.
        """
        if not skills:
            return []
        
        cleaned_skills = []
        for s in skills:
            skill_name = s or ""
            # ISSUE 1 - Stray bracket in skill name
            skill_name = re.sub(r'[\[\]\(\)]', '', skill_name).strip()
            cleaned_skills.append(skill_name)
        skills = cleaned_skills

        if canonical_list is None:
            canonical_list = DEFAULT_CANONICAL_SKILLS
        if not canonical_list:
            return skills

        try:
            from sentence_transformers import util
            model = self.model
            
            skill_embeddings = model.encode(skills, convert_to_tensor=True)
            canonical_embeddings = model.encode(canonical_list, convert_to_tensor=True)
            
            cosine_scores = util.cos_sim(skill_embeddings, canonical_embeddings)
            
            normalized = []
            for i, skill in enumerate(skills):
                scores = cosine_scores[i]
                max_idx = int(scores.argmax())
                max_score = float(scores[max_idx])
                
                if max_score > 0.75:
                    normalized.append(canonical_list[max_idx])
                else:
                    normalized.append(skill)
            return normalized
        except Exception as e:
            logger.error(f"Error normalizing skills: {e}", exc_info=True)
            return skills

    def normalize_location(self, raw: str) -> dict:
        """
        Parses location string using comma separation heuristics.
        Tries to match country component or resolve state.
        Returns a dictionary with keys: city, region, country.
        """
        res = {"city": None, "region": None, "country": None}
        if not raw or not isinstance(raw, str):
            return res

        raw_clean = raw.strip()
        parts = [p.strip() for p in raw_clean.split(",") if p.strip()]
        if len(parts) == 1 and " " in raw_clean:
            # If no commas but spaces exist, split by space and inspect tokens
            space_parts = [p.strip() for p in raw_clean.split() if p.strip()]
            last_word = space_parts[-1].lower()
            if last_word in [s.lower() for s in IN_STATES] or last_word in COMMON_COUNTRIES:
                parts = space_parts
            elif len(space_parts) >= 2:
                parts = space_parts

        if not parts:
            return res

        last_part = parts[-1]
        last_part_lower = last_part.lower()

        # Direct country lookup
        country_code = COMMON_COUNTRIES.get(last_part_lower)

        if country_code:
            res["country"] = country_code
            if len(parts) == 2:
                res["city"] = parts[0]
            elif len(parts) >= 3:
                res["city"] = parts[0]
                res["region"] = parts[1]
        else:
            # Check Indian State inference
            if last_part_lower in [s.lower() for s in IN_STATES]:
                res["country"] = "IN"
                res["region"] = last_part
                if len(parts) >= 2:
                    res["city"] = parts[-2]
            # Check US State inference
            elif last_part_lower in [s.lower() for s in US_STATES]:
                res["country"] = "US"
                res["region"] = last_part
                if len(parts) >= 2:
                    res["city"] = parts[-2]
            else:
                # Unparseable country/state fallback
                if len(parts) == 1:
                    res["city"] = parts[0]
                elif len(parts) == 2:
                    res["city"] = parts[0]
                    res["region"] = parts[1]
                else:
                    res["city"] = parts[0]
                    res["region"] = parts[1]

        # Clean city and region formatting
        if res["city"] and isinstance(res["city"], str):
            c_str = res["city"].strip()
            if c_str.islower() or c_str.isupper():
                res["city"] = c_str.title()
            else:
                res["city"] = c_str
        if res["region"] and isinstance(res["region"], str):
            r_str = res["region"].strip()
            if len(r_str) == 2:
                res["region"] = r_str.upper()
            elif r_str.islower() or r_str.isupper():
                res["region"] = r_str.title()
            else:
                res["region"] = r_str

        return res

    def run(self, raw_data: dict) -> dict:
        """
        Normalize the incoming raw data in-place or return a normalized copy.
        """
        # Baseline runner
        normalized = raw_data.copy()
        if "phones" in normalized and normalized["phones"]:
            normalized["phones"] = self.normalize_phones(normalized["phones"])
        if "skills" in normalized and normalized["skills"]:
            normalized["skills"] = self.normalize_skills(normalized["skills"])
        if "location" in normalized and normalized["location"]:
            loc_dict = self.normalize_location(normalized["location"])
            normalized["location"] = loc_dict

        # ISSUE 4 - full_name is all caps "VIVEK SHARMA"
        profile = normalized
        if profile.get("full_name"):
            profile["full_name"] = profile["full_name"].title()

        return normalized
