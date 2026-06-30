import re
import logging

logger = logging.getLogger(__name__)

def clean_str(s: str) -> str:
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).strip().lower()

def is_acronym(acronym: str, full_name: str) -> bool:
    acronym = acronym.strip().lower()
    full_name = full_name.strip().lower()
    if not acronym or not full_name:
        return False
    words = [w for w in re.split(r'[^a-zA-Z0-9]', full_name) if w]
    if len(words) < 2:
        return False
    initials = "".join(w[0] for w in words)
    return initials == acronym

def experience_match(exp1: dict, exp2: dict) -> bool:
    c1 = clean_str(exp1.get("company"))
    c2 = clean_str(exp2.get("company"))
    t1 = clean_str(exp1.get("title"))
    t2 = clean_str(exp2.get("title"))
    s1 = exp1.get("start")
    s2 = exp2.get("start")
    e1 = exp1.get("end")
    e2 = exp2.get("end")
    
    # Check if companies match
    companies_overlap = False
    if c1 and c2:
        companies_overlap = (c1 == c2 or c1 in c2 or c2 in c1)
        
    # Check if titles match
    titles_overlap = False
    if t1 and t2:
        titles_overlap = (t1 == t2 or t1 in t2 or t2 in t1)
    elif not t1 or not t2:
        titles_overlap = True
        
    # Check if dates match
    dates_match = False
    if s1 and s2 and e1 and e2:
        dates_match = (str(s1).strip().lower() == str(s2).strip().lower() and str(e1).strip().lower() == str(e2).strip().lower())
        
    # If same time interval and same role, merge them
    if titles_overlap and dates_match:
        return True
        
    return companies_overlap and titles_overlap

def standardize_degree(deg: str) -> str:
    deg = str(deg or "").strip().lower()
    deg = re.sub(r'[^a-z0-9\s]', '', deg)
    deg = re.sub(r'\s+', ' ', deg).strip()
    
    replacements = {
        r'\bbe\b': 'bachelor of engineering',
        r'\bbtech\b': 'bachelor of technology',
        r'\bbs\b': 'bachelor of science',
        r'\bbsc\b': 'bachelor of science',
        r'\bme\b': 'master of engineering',
        r'\bmtech\b': 'master of technology',
        r'\bms\b': 'master of science',
        r'\bmsc\b': 'master of science',
        r'\bmca\b': 'master of computer applications',
        r'\bbca\b': 'bachelor of computer applications',
        r'\bba\b': 'bachelor of arts',
        r'\bma\b': 'master of arts',
        r'\bphd\b': 'doctor of philosophy'
    }
    for pattern, repl in replacements.items():
        deg = re.sub(pattern, repl, deg)
        
    return deg

def education_match(edu1: dict, edu2: dict) -> bool:
    d1 = standardize_degree(edu1.get("degree"))
    d2 = standardize_degree(edu2.get("degree"))
    
    if not d1 or not d2:
        return False
        
    degrees_overlap = (d1 == d2 or d1 in d2 or d2 in d1)
    if not degrees_overlap:
        return False
        
    inst1 = edu1.get("institution") or ""
    inst2 = edu2.get("institution") or ""
    
    if not inst1 or not inst2:
        return True
        
    c_inst1 = clean_str(inst1)
    c_inst2 = clean_str(inst2)
    
    if c_inst1 == c_inst2 or c_inst1 in c_inst2 or c_inst2 in c_inst1:
        return True
        
    if is_acronym(inst1, inst2) or is_acronym(inst2, inst1):
        return True
        
    inst_keywords = ["university", "college", "institute", "school", "sppu", "iit", "nit", "bits"]
    field_keywords = ["engineering", "science", "technology", "arts", "business"]
    
    inst1_is_field = any(k in c_inst1 for k in field_keywords) and not any(k in c_inst1 for k in inst_keywords)
    inst2_is_field = any(k in c_inst2 for k in field_keywords) and not any(k in c_inst2 for k in inst_keywords)
    
    if inst1_is_field or inst2_is_field:
        return True
        
    return False

def merge_experience_items(exp1: dict, exp2: dict) -> dict:
    merged = {}
    for key in ["company", "title", "start", "end", "summary"]:
        v1 = exp1.get(key)
        v2 = exp2.get(key)
        if v1 and v2:
            merged[key] = v1 if len(str(v1)) >= len(str(v2)) else v2
        else:
            merged[key] = v1 or v2
    return merged

def merge_education_items(edu1: dict, edu2: dict) -> dict:
    merged = {}
    inst1 = edu1.get("institution")
    inst2 = edu2.get("institution")
    inst_keywords = ["university", "college", "institute", "school", "sppu", "iit", "nit", "bits"]
    
    if inst1 and inst2:
        c1 = clean_str(inst1)
        c2 = clean_str(inst2)
        inst1_has_kw = any(k in c1 for k in inst_keywords)
        inst2_has_kw = any(k in c2 for k in inst_keywords)
        if inst1_has_kw and not inst2_has_kw:
            merged["institution"] = inst1
        elif inst2_has_kw and not inst1_has_kw:
            merged["institution"] = inst2
        else:
            merged["institution"] = inst1 if len(str(inst1)) >= len(str(inst2)) else inst2
    else:
        merged["institution"] = inst1 or inst2

    deg1 = edu1.get("degree")
    deg2 = edu2.get("degree")
    if deg1 and deg2:
        merged["degree"] = deg1 if len(str(deg1)) >= len(str(deg2)) else deg2
    else:
        merged["degree"] = deg1 or deg2

    field1 = edu1.get("field")
    field2 = edu2.get("field")
    
    if inst1 and not any(k in clean_str(inst1) for k in inst_keywords) and not field1:
        field1 = inst1
    if inst2 and not any(k in clean_str(inst2) for k in inst_keywords) and not field2:
        field2 = inst2
        
    if field1 and field2:
        merged["field"] = field1 if len(str(field1)) >= len(str(field2)) else field2
    else:
        merged["field"] = field1 or field2

    merged["end_year"] = edu1.get("end_year") or edu2.get("end_year")
    return merged


SOURCE_PRIORITY = {
  "resume": 5,
  "linkedin": 4, 
  "github": 3,
  "ats_json": 2,
  "recruiter_csv": 1,
  "recruiter_notes": 1
}

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

ARRAY_FIELDS = {"emails", "phones"}
OBJECT_FIELDS = {"experience", "education"}

def get_completeness(val) -> int:
    """
    Evaluate the completeness (length) of a value.
    """
    if val is None:
        return 0
    if isinstance(val, (str, list, dict)):
        return len(val)
    if isinstance(val, (int, float)):
        return 1
    return 0

def get_extraction_method(source_dict: dict, field_name: str) -> str:
    """
    Infer the extraction method based on the source metadata.
    """
    source_name = source_dict.get("source_name")
    if source_name == "resume":
        if source_dict.get("low_confidence"):
            return "regex_fallback"
        return "llm_extraction"
    if source_name == "ats_json":
        return "json_mapping"
    if source_name == "recruiter_csv":
        return "csv_parsing"
    if source_name == "recruiter_notes":
        return "regex_extraction"
    if source_name == "github":
        return "github_api"
    return "unknown_method"

class Merger:
    """
    Merges candidate profiles from multiple sources based on priority and completeness.
    """
    def __init__(self):
        pass

    def run(self, primary_data: dict, secondary_data: dict) -> dict:
        """
        Baseline runner to merge two data dictionaries.
        """
        return self.merge([primary_data, secondary_data])

    def merge(self, sources: list[dict]) -> dict:
        """
        Merge normalized profiles from multiple sources into a single canonical dictionary.
        """
        # Handle edge case: empty sources list
        if not sources:
            result = {field: None for field in CANONICAL_FIELDS}
            # Initialize array fields as empty lists for consistency
            result["emails"] = []
            result["phones"] = []
            result["skills"] = []
            result["experience"] = []
            result["education"] = []
            result["location"] = {"city": None, "region": None, "country": None}
            result["links"] = {"linkedin": None, "github": None, "portfolio": None, "other": []}
            result["provenance"] = []
            result["overall_confidence"] = 0.0
            return result

        # Filter out empty dictionaries or ones that only have source_name
        non_empty_sources = []
        for s in sources:
            if not isinstance(s, dict):
                continue
            keys = [k for k, v in s.items() if k != "source_name" and v is not None and v != "" and v != [] and v != {}]
            if keys:
                non_empty_sources.append(s)

        if not non_empty_sources:
            # Fallback if all sources are empty
            result = {field: None for field in CANONICAL_FIELDS}
            result["emails"] = []
            result["phones"] = []
            result["skills"] = []
            result["experience"] = []
            result["education"] = []
            result["location"] = {"city": None, "region": None, "country": None}
            result["links"] = {"linkedin": None, "github": None, "portfolio": None, "other": []}
            result["provenance"] = []
            result["overall_confidence"] = 0.0
            return result

        # Handle edge case: single non-empty source
        if len(non_empty_sources) == 1:
            src = non_empty_sources[0]
            result = {}
            provenance = []
            
            # Map canonical fields
            for field in CANONICAL_FIELDS:
                if field == "location":
                    loc = src.get("location")
                    if isinstance(loc, dict):
                        result["location"] = loc
                    else:
                        result["location"] = {"city": None, "region": None, "country": None}
                    if isinstance(loc, dict) and any(v is not None and v != "" for v in loc.values()):
                        provenance.append({
                            "field": "location",
                            "source": src.get("source_name", "unknown"),
                            "method": get_extraction_method(src, "location")
                        })
                elif field == "links":
                    # Build links object from source
                    links = {"linkedin": src.get("linkedin_url"), "github": src.get("github_url"), "portfolio": None, "other": []}
                    result["links"] = links
                    if links["linkedin"]:
                        provenance.append({"field": "links.linkedin", "source": src.get("source_name", "unknown"), "method": get_extraction_method(src, "linkedin_url")})
                    if links["github"]:
                        provenance.append({"field": "links.github", "source": src.get("source_name", "unknown"), "method": get_extraction_method(src, "github_url")})
                elif field == "skills":
                    skills_objects = []
                    s_list = src.get("skills")
                    if isinstance(s_list, list):
                        for s in s_list:
                            # If it's already a skill dict (mocked in tests), keep it, otherwise build it
                            if isinstance(s, dict):
                                skills_objects.append(s)
                            else:
                                skills_objects.append({
                                    "name": str(s).strip(),
                                    "confidence": 0.8,
                                    "sources": [src.get("source_name", "unknown")]
                                })
                    result["skills"] = skills_objects
                    if skills_objects:
                        provenance.append({
                            "field": "skills",
                            "source": src.get("source_name", "unknown"),
                            "method": get_extraction_method(src, "skills")
                        })
                else:
                    val = src.get(field)
                    if val is None:
                        if field in ARRAY_FIELDS or field in OBJECT_FIELDS:
                            result[field] = []
                        else:
                            result[field] = None
                    else:
                        result[field] = val
                    if val is not None and val != "" and val != []:
                        provenance.append({
                            "field": field,
                            "source": src.get("source_name", "unknown"),
                            "method": get_extraction_method(src, field)
                        })
            result["provenance"] = provenance
            return result

        result = {}
        provenance = []

        # Process each canonical field
        for field in CANONICAL_FIELDS:
            if field == "location":
                merged_loc = {"city": None, "region": None, "country": None}
                for sub in ["city", "region", "country"]:
                    best_val = None
                    best_src = None
                    for src in non_empty_sources:
                        loc = src.get("location")
                        if isinstance(loc, dict) and loc.get(sub):
                            val = loc.get(sub)
                            if best_src is None or SOURCE_PRIORITY.get(src.get("source_name", ""), 1) > SOURCE_PRIORITY.get(best_src.get("source_name", ""), 1):
                                best_val = val
                                best_src = src
                    if best_val:
                        merged_loc[sub] = best_val
                        provenance.append({
                            "field": f"location.{sub}",
                            "source": best_src.get("source_name", "unknown"),
                            "method": get_extraction_method(best_src, "location")
                        })
                result["location"] = merged_loc

            elif field == "links":
                links = {"linkedin": None, "github": None, "portfolio": None, "other": []}
                
                # Fetch linkedin_url
                linkedin_src = None
                for src in non_empty_sources:
                    url = src.get("linkedin_url")
                    if url:
                        if linkedin_src is None or SOURCE_PRIORITY.get(src.get("source_name", ""), 1) > SOURCE_PRIORITY.get(linkedin_src.get("source_name", ""), 1):
                            links["linkedin"] = url
                            linkedin_src = src
                if links["linkedin"]:
                    provenance.append({
                        "field": "links.linkedin",
                        "source": linkedin_src.get("source_name", "unknown"),
                        "method": get_extraction_method(linkedin_src, "linkedin_url")
                    })
                    
                # Fetch github_url
                github_src = None
                for src in non_empty_sources:
                    url = src.get("github_url")
                    if url:
                        if github_src is None or SOURCE_PRIORITY.get(src.get("source_name", ""), 1) > SOURCE_PRIORITY.get(github_src.get("source_name", ""), 1):
                            links["github"] = url
                            github_src = src
                if links["github"]:
                    provenance.append({
                        "field": "links.github",
                        "source": github_src.get("source_name", "unknown"),
                        "method": get_extraction_method(github_src, "github_url")
                    })
                
                result["links"] = links

            elif field == "skills":
                skill_sources = {}
                for src in non_empty_sources:
                    s_list = src.get("skills")
                    if isinstance(s_list, list) and s_list:
                        for s in s_list:
                            if s:
                                if isinstance(s, dict):
                                    s_name = s.get("name")
                                else:
                                    s_name = str(s).strip()
                                
                                if s_name:
                                    s_name_lower = s_name.lower()
                                    found = False
                                    for existing_name in skill_sources:
                                        if existing_name.lower() == s_name_lower:
                                            if src.get("source_name") not in skill_sources[existing_name]:
                                                skill_sources[existing_name].append(src.get("source_name"))
                                            found = True
                                            break
                                    if not found:
                                        skill_sources[s_name] = [src.get("source_name")]
                
                skills_objects = []
                for name, sources_list in skill_sources.items():
                    base_conf = 0.7
                    if "resume" in sources_list or "linkedin" in sources_list:
                        base_conf = 0.9
                    elif "github" in sources_list:
                        base_conf = 0.8
                        
                    bonus = 0.1 * (len(sources_list) - 1)
                    confidence = min(round(base_conf + bonus, 2), 1.0)
                    
                    skills_objects.append({
                        "name": name,
                        "confidence": confidence,
                        "sources": sorted(sources_list)
                    })
                
                result["skills"] = sorted(skills_objects, key=lambda x: x["name"])
                
                for src in non_empty_sources:
                    if src.get("skills"):
                        provenance.append({
                            "field": "skills",
                            "source": src.get("source_name", "unknown"),
                            "method": get_extraction_method(src, "skills")
                        })

            elif field in ARRAY_FIELDS:
                # Union array fields and deduplicate case-insensitively
                seen = set()
                union_val = []
                contributing_sources = []
                for src in non_empty_sources:
                    arr = src.get(field)
                    if isinstance(arr, list) and arr:
                        has_added = False
                        for item in arr:
                            if item is not None and item != "":
                                cleaned_item = str(item).strip()
                                if field == "emails":
                                    cleaned_item = cleaned_item.lower()
                                if cleaned_item.lower() not in seen:
                                    seen.add(cleaned_item.lower())
                                    union_val.append(cleaned_item)
                                    has_added = True
                        if has_added:
                            contributing_sources.append(src)
                
                result[field] = union_val
                
                # Sort contributing sources by priority for provenance logging
                contributing_sources.sort(key=lambda s: SOURCE_PRIORITY.get(s.get("source_name", ""), 1), reverse=True)
                for src in contributing_sources:
                    provenance.append({
                        "field": field,
                        "source": src.get("source_name", "unknown"),
                        "method": get_extraction_method(src, field)
                    })

            elif field in OBJECT_FIELDS:
                # Sort from lowest priority to highest priority
                sorted_sources = sorted(
                    non_empty_sources,
                    key=lambda s: (SOURCE_PRIORITY.get(s.get("source_name", ""), 1), get_completeness(s.get(field))),
                )

                merged_list = []
                contributing_sources = []
                for src in sorted_sources:
                    arr = src.get(field)
                    if isinstance(arr, list) and arr:
                        has_added = False
                        for obj in arr:
                            if not isinstance(obj, dict):
                                continue
                            
                            # Try to match with an existing merged item
                            match_idx = -1
                            for idx, existing in enumerate(merged_list):
                                if field == "experience":
                                    if experience_match(existing, obj):
                                        match_idx = idx
                                        break
                                else:  # education
                                    if education_match(existing, obj):
                                        match_idx = idx
                                        break
                            
                            if match_idx >= 0:
                                # Merge into existing item in-place
                                if field == "experience":
                                    merged_list[match_idx] = merge_experience_items(merged_list[match_idx], obj)
                                else:
                                    merged_list[match_idx] = merge_education_items(merged_list[match_idx], obj)
                                has_added = True
                            else:
                                # Only add if it has at least some meaningful fields
                                has_val = any(obj.get(k) for k in (["company", "title"] if field == "experience" else ["institution", "degree"]))
                                if has_val:
                                    merged_list.append(obj.copy())
                                    has_added = True
                                    
                        if has_added:
                            if src not in contributing_sources:
                                contributing_sources.append(src)

                result[field] = merged_list

                # Sort contributing sources by priority for provenance
                contributing_sources.sort(key=lambda s: SOURCE_PRIORITY.get(s.get("source_name", ""), 1), reverse=True)
                for src in contributing_sources:
                    provenance.append({
                        "field": field,
                        "source": src.get("source_name", "unknown"),
                        "method": get_extraction_method(src, field)
                    })

            else:
                # Single-value fields
                valid_sources = []
                for src in non_empty_sources:
                    val = src.get(field)
                    if val is not None and val != "" and val != []:
                        valid_sources.append(src)

                if not valid_sources:
                    result[field] = None
                    continue

                # Sort by priority first, then by completeness
                valid_sources.sort(
                    key=lambda s: (SOURCE_PRIORITY.get(s.get("source_name", ""), 1), get_completeness(s.get(field))),
                    reverse=True
                )
                winner_src = valid_sources[0]
                result[field] = winner_src.get(field)

                provenance.append({
                    "field": field,
                    "source": winner_src.get("source_name", "unknown"),
                    "method": get_extraction_method(winner_src, field)
                })

        result["provenance"] = provenance
        return result
