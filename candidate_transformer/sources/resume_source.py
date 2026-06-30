import os
import re
import json
import logging
from .base import BaseSource

logger = logging.getLogger(__name__)

class ResumeSource(BaseSource):
    """
    Source reader for PDF, Word (.docx), and plain text resumes.
    Uses Anthropic's Claude API for structured parsing, with a regex-based fallback.
    """

    def extract(self, input_path_or_url: str) -> dict:
        """
        Extract candidate details from a resume file.
        """
        from pathlib import Path
        path = Path(input_path_or_url)
        text = ""
        
        def empty_result(confidence="low"):
            return {
                "source_name": "resume",
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
                "low_confidence": confidence == "low",
                "confidence": confidence
            }

        try:
            ext = path.suffix.lower()
            if ext == ".pdf":
                import pdfplumber
                with pdfplumber.open(str(path)) as pdf:
                    text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            elif ext == ".docx":
                import docx
                doc = docx.Document(str(path))
                text = "\n".join([p.text for p in doc.paragraphs])
            else:
                with path.open(mode='r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
        except Exception as e:
            logger.warning(f"Failed to read resume file {input_path_or_url}: {e}")
            logger.error(f"Error reading resume file: {e}", exc_info=True)
            text = ""

        try:
            if not text.strip():
                raise ValueError("No text content found to parse.")

            from anthropic import Anthropic
            client = Anthropic()

            system_prompt = (
                "You are a resume parser. Extract structured candidate information from the resume text.\n"
                "Return ONLY valid JSON with these fields (use null for missing fields, never invent):\n"
                "{\n"
                "  full_name, emails (array), phones (array), location (raw string),\n"
                "  linkedin_url, github_url, headline, years_experience (number),\n"
                "  skills (array of strings),\n"
                "  experience (array of {company, title, start, end, summary}),\n"
                "  education (array of {institution, degree, field, end_year})\n"
                "}"
            )

            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": text}
                ]
            )

            response_text = message.content[0].text.strip()
            
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            parsed_data = json.loads(response_text)
            
            result = empty_result(confidence="high")
            for k in result:
                if k in parsed_data:
                    result[k] = parsed_data[k]
            
            # DEBUG: raw extracted values before normalization
            logger.debug(f"Raw Resume LLM extraction: {result}")

            # WARNING: when a source fails or field is null
            for k, v in result.items():
                if v is None or v == [] or v == {}:
                    logger.warning(f"Resume LLM source field '{k}' is null or empty.")

            # INFO: which sources were processed
            logger.info(f"Processed resume source: {input_path_or_url}")

            return result

        except Exception as e:
            logger.warning(f"Anthropic LLM extraction failed or returned invalid JSON: {e}. Falling back to advanced regex extraction.")
            
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            result = empty_result(confidence="low")
            
            if not lines:
                return result

            # 1. Name is typically the first line if it's short and clean
            first_line = lines[0]
            if len(first_line) < 50 and not any(c in first_line for c in ["@", ":", "http", "/"]):
                result["full_name"] = first_line

            # 2. Extract email, phone, links using regexes
            email_matches = re.findall(r'[\w.-]+@[\w.-]+\.\w+', text)
            result["emails"] = sorted(list(set(e.strip() for e in email_matches if e.strip())))
            
            phone_matches = re.findall(r'(?:\+?\d{1,3}[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}', text)
            phone_matches_alt = re.findall(r'\+?\d{1,4}[\s\-\.]?\d{10}', text)
            result["phones"] = sorted(list(set(p.strip() for p in (phone_matches + phone_matches_alt) if p.strip())))

            linkedin_match = re.search(r'(linkedin\.com/in/[a-zA-Z0-9\-_/]+)', text, re.IGNORECASE)
            if linkedin_match:
                result["linkedin_url"] = "https://" + linkedin_match.group(1).strip()
                
            github_match = re.search(r'(github\.com/[a-zA-Z0-9\-_/]+)', text, re.IGNORECASE)
            if github_match:
                result["github_url"] = "https://" + github_match.group(1).strip()

            loc_match = re.search(r'Location:\s*(.*)', text, re.IGNORECASE)
            if loc_match:
                result["location"] = loc_match.group(1).strip()
            else:
                loc_pattern = r'\b([A-Z][a-zA-Z]+),\s*(Maharashtra|Gujarat|Karnataka|Delhi|Tamil\s*Nadu|Telangana|Uttar\s*Pradesh|India)\b'
                m = re.search(loc_pattern, text)
                if m:
                    result["location"] = m.group(0).strip()

            # 3. Section-based parsing
            sections = {}
            for i, line in enumerate(lines):
                line_upper = line.upper().strip()
                line_upper = re.sub(r'[*_#\-–—\s]+', ' ', line_upper).strip()
                if len(line_upper) > 25:
                    continue
                if "SKILLS" in line_upper and "SKILLS" not in sections:
                    sections["SKILLS"] = i
                elif "EXPERIENCE" in line_upper and "EXPERIENCE" not in sections:
                    sections["EXPERIENCE"] = i
                elif "EDUCATION" in line_upper and "EDUCATION" not in sections:
                    sections["EDUCATION"] = i
                elif "SUMMARY" in line_upper and "SUMMARY" not in sections:
                    sections["SUMMARY"] = i
                elif "PROJECTS" in line_upper and "PROJECTS" not in sections:
                    sections["PROJECTS"] = i
                elif "ACHIEVEMENTS" in line_upper and "ACHIEVEMENTS" not in sections:
                    sections["ACHIEVEMENTS"] = i

            sorted_sections = sorted(sections.items(), key=lambda x: x[1])

            def get_section_lines(sec_name: str) -> list[str]:
                if sec_name not in sections:
                    return []
                start_idx = sections[sec_name] + 1
                end_idx = len(lines)
                for name, idx in sorted_sections:
                    if idx > start_idx - 1:
                        end_idx = idx
                        break
                sec_lines = lines[start_idx:end_idx]
                
                # Filter out divider lines
                filtered = []
                for line in sec_lines:
                    cleaned = line.strip()
                    if cleaned and not re.match(r'^[-\–\—\=_*~]+$', cleaned):
                        filtered.append(line)
                return filtered

            # Parse SKILLS section
            skill_lines = get_section_lines("SKILLS")
            skills_list = []
            for s_line in skill_lines:
                parts = [p.strip() for p in s_line.split(',') if p.strip()]
                for part in parts:
                    if ":" in part:
                        part = part.split(":", 1)[1].strip()
                    if part:
                        skills_list.append(part)
            result["skills"] = skills_list

            # Parse EDUCATION section
            edu_lines = get_section_lines("EDUCATION")
            education_list = []
            
            curr_edu = {"institution": None, "degree": None, "field": None, "end_year": None}
            inst_keywords = ["university", "college", "institute", "school", "sppu", "iit", "nit", "bits", "academy", "vidyamandir"]
            degree_keywords = ["b.e", "b.tech", "b.s", "b.sc", "bachelor", "master", "diploma", "phd", "m.tech", "secondary", "hsc", "ssc", "class", "grade", "schooling", "intermediate"]
            field_keywords = ["engineering", "science", "commerce", "arts", "humanities", "technology", "biology", "physics", "chemistry", "mathematics"]
            
            def clean_edu_item(item: dict):
                # Clean up field of study mapping from degree field
                deg_val = item["degree"] or ""
                if "in " in deg_val.lower():
                    parts = deg_val.lower().split("in ", 1)
                    item["field"] = parts[1].strip().title()
                    deg_prefix = deg_val[:deg_val.lower().index("in ")].strip()
                    deg_prefix = re.sub(r'^[|,\s\-\–\—\s]+|[|,\s\-\–\—\s]+$', '', deg_prefix).strip()
                    item["degree"] = deg_prefix
                else:
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
                            item["field"] = field_part
                            item["degree"] = matched_prefix

            def is_grade_value(text: str) -> bool:
                text_lower = text.lower()
                if "cgpa" in text_lower or "gpa" in text_lower or "percent" in text_lower or "%" in text_lower or "pointer" in text_lower or "marks" in text_lower or "grade" in text_lower:
                    return True
                if re.search(r'\b\d{1,2}(?:\.\d{1,2})?\s*%', text):
                    return True
                if re.search(r'\b\d{1,2}(?:\.\d{1,2})?\s*/\s*\d{1,2}\b', text):
                    return True
                return False

            edu_date_regex = r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2})\s*\d{4}|\d{4})\b\s*[\-–—]\s*\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2})\s*\d{4}|\d{4}|Present|Current)\b'

            for line in edu_lines:
                line_str = line.strip()
                if not line_str:
                    continue
                    
                # Temporarily replace date-range dashes with a token to avoid splitting on them
                temp_line = line_str
                date_range_match = re.search(edu_date_regex, temp_line, re.IGNORECASE)
                if date_range_match:
                    orig_range = date_range_match.group(0)
                    new_range = re.sub(r'\s*[\-–—]\s*', ' __TO__ ', orig_range)
                    temp_line = temp_line.replace(orig_range, new_range)
                    
                parts = [p.strip() for p in re.split(r'\s*(?:\||\-|\bat\b)\s*', temp_line) if p.strip()]
                parts = [p.replace('__TO__', '-').strip() for p in parts]
                
                for part in parts:
                    year_match = re.findall(r'\b((?:19|20)\d{2})\b', part)
                    if year_match:
                        curr_edu["end_year"] = int(year_match[-1])
                        part_clean = re.sub(r'\b((?:19|20)\d{2})\b', '', part).strip()
                        part_clean = re.sub(r'^[|,\s\-\–\—\(\)\s]+|[|,\s\-\–\—\(\)\s]+$', '', part_clean).strip()
                        if not part_clean:
                            continue
                        part = part_clean
                        
                    # Strip any grade info (CGPA, GPA, percent, etc.) from the part
                    grade_match = re.search(r'\b(?:cgpa|gpa|percent|pointer|marks|grade)\s*:?\s*\d+(?:\.\d+)?(?:\s*/\s*\d+)?\b|\b\d+(?:\.\d+)?\s*%\b', part, re.IGNORECASE)
                    if grade_match:
                        part = part.replace(grade_match.group(0), "").strip()
                        part = re.sub(r'^[|,\s\-\–\—\(\)\s]+|[|,\s\-\–\—\(\)\s]+$', '', part).strip()
                        
                    if not part:
                        continue
                        
                    if any(k in part.lower() for k in inst_keywords):
                        if curr_edu["institution"]:
                            clean_edu_item(curr_edu)
                            education_list.append(curr_edu)
                            curr_edu = {"institution": None, "degree": None, "field": None, "end_year": None}
                        curr_edu["institution"] = part
                        
                    elif any(k in part.lower() for k in degree_keywords) or part.lower().startswith("b.") or part.lower().startswith("m."):
                        curr_edu["degree"] = part
                        
                    elif any(k in part.lower() for k in field_keywords):
                        curr_edu["field"] = part
                        
                    else:
                        if not curr_edu["degree"] and not curr_edu["institution"]:
                            curr_edu["degree"] = part
                        elif curr_edu["degree"] and not curr_edu["field"]:
                            curr_edu["field"] = part
                            
            if curr_edu["institution"] or curr_edu["degree"]:
                clean_edu_item(curr_edu)
                education_list.append(curr_edu)
                
            result["education"] = education_list

            # Parse EXPERIENCE section
            exp_lines = get_section_lines("EXPERIENCE")
            experience_list = []
            curr_job = None
            
            date_range_regex = r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2})\s*\d{4})\b\s*[\-–—]\s*\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2})\s*\d{4}|Present|Current)\b'
            
            i = 0
            while i < len(exp_lines):
                line = exp_lines[i].strip()
                if not line:
                    i += 1
                    continue
                
                is_bullet = False
                if line.startswith("-") or line.startswith("•") or line.startswith("*") or line.startswith("o ") or line.startswith("➢") or line.startswith("(cid:"):
                    is_bullet = True
                elif line and line[0].islower():
                    is_bullet = True
                    
                if is_bullet:
                    desc = line
                    desc = re.sub(r'^(?:\(cid:\d+\)|[\-•*o➢])\s*', '', desc).strip()
                    if curr_job:
                        if curr_job["summary"]:
                            curr_job["summary"] += "\n" + desc
                        else:
                            curr_job["summary"] = desc
                    i += 1
                else:
                    date_match = re.search(date_range_regex, line, re.IGNORECASE)
                    title_keywords = ["developer", "engineer", "intern", "manager", "lead", "architect", "analyst", "specialist", "designer", "consultant", "officer"]
                    has_title_kw = any(re.search(rf'\b{k}\b', line, re.IGNORECASE) for k in title_keywords)
                    
                    is_new_job = False
                    if has_title_kw:
                        is_new_job = True
                    elif " at " in line:
                        is_new_job = True
                    elif (" - " in line or " | " in line) and not date_match:
                        is_new_job = True
                        
                    if is_new_job:
                        if curr_job:
                            experience_list.append(curr_job)
                        curr_job = {"company": None, "title": None, "start": None, "end": None, "summary": ""}
                        
                        if date_match:
                            curr_job["start"] = date_match.group(1).strip()
                            curr_job["end"] = date_match.group(2).strip()
                            cleaned_line = line.replace(date_match.group(0), "").strip()
                            cleaned_line = re.sub(r'^[|,\s\-\–\—\s]+|[|,\s\-\–\—\s]+$', '', cleaned_line).strip()
                        else:
                            cleaned_line = line
                            
                        if " - " in cleaned_line:
                            parts = cleaned_line.split(" - ", 1)
                            curr_job["title"] = parts[0].strip()
                            curr_job["company"] = parts[1].strip()
                        elif " | " in cleaned_line:
                            parts = cleaned_line.split(" | ", 1)
                            curr_job["title"] = parts[0].strip()
                            curr_job["company"] = parts[1].strip()
                        elif " at " in cleaned_line:
                            parts = cleaned_line.split(" at ", 1)
                            curr_job["title"] = parts[0].strip()
                            curr_job["company"] = parts[1].strip()
                        else:
                            curr_job["title"] = cleaned_line
                            
                        if curr_job["company"]:
                            curr_job["company"] = re.sub(r'\s*\(\s*\)\s*$', '', curr_job["company"]).strip()
                            
                        if not curr_job["company"] and i + 1 < len(exp_lines):
                            next_line = exp_lines[i + 1].strip()
                            next_is_bullet = False
                            if next_line.startswith("-") or next_line.startswith("•") or next_line.startswith("*") or next_line.startswith("o ") or next_line.startswith("➢") or next_line.startswith("(cid:"):
                                next_is_bullet = True
                            elif next_line and next_line[0].islower():
                                next_is_bullet = True
                                
                            if next_line and not next_is_bullet and not re.search(date_range_regex, next_line, re.IGNORECASE):
                                company_clean = next_line
                                if " - " in company_clean:
                                    company_clean = company_clean.split(" - ")[0].strip()
                                elif " | " in company_clean:
                                    company_clean = company_clean.split(" | ")[0].strip()
                                company_clean = re.sub(r'\b(remote|onsite|hybrid|india|usa|uk)\b', '', company_clean, flags=re.IGNORECASE).strip()
                                company_clean = re.sub(r'^[,/\s]+|[,/\s]+$', '', company_clean).strip()
                                curr_job["company"] = company_clean
                                i += 1
                    elif date_match and curr_job:
                        curr_job["start"] = date_match.group(1).strip()
                        curr_job["end"] = date_match.group(2).strip()
                        if not curr_job.get("company"):
                            cleaned_line = line.replace(date_match.group(0), "").strip()
                            cleaned_line = re.sub(r'^[|,\s\-\–\—\s]+|[|,\s\-\–\—\s]+$', '', cleaned_line).strip()
                            cleaned_line = re.sub(r'\b(remote|onsite|hybrid)\b', '', cleaned_line, flags=re.IGNORECASE).strip()
                            cleaned_line = re.sub(r'^[|,\s\-\–\—\s]+|[|,\s\-\–\—\s]+$', '', cleaned_line).strip()
                            if cleaned_line:
                                curr_job["company"] = cleaned_line
                    i += 1
            if curr_job:
                experience_list.append(curr_job)
            result["experience"] = experience_list

            # Estimate years_experience
            total_months = 0
            month_map = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
            for exp in experience_list:
                start = exp.get("start")
                end = exp.get("end")
                if start and end:
                    y_start = re.findall(r'\b(\d{4})\b', start)
                    y_end = re.findall(r'\b(\d{4})\b', end)
                    
                    m_start = 1
                    m_end = 12
                    for m_name, m_num in month_map.items():
                        if m_name in start.lower():
                            m_start = m_num
                        if m_name in end.lower():
                            m_end = m_num
                            
                    ys = int(y_start[0]) if y_start else 2026
                    if "present" in end.lower() or "current" in end.lower():
                        ye = 2026
                        m_end = 6
                    else:
                        ye = int(y_end[0]) if y_end else 2026
                        
                    months = (ye - ys) * 12 + (m_end - m_start)
                    total_months += max(1, months)
            if total_months > 0:
                result["years_experience"] = round(total_months / 12, 1)

            # DEBUG: raw extracted values before normalization
            logger.debug(f"Raw Resume advanced regex fallback extraction: {result}")

            # INFO: which sources were processed
            logger.info(f"Processed resume source (advanced regex fallback): {input_path_or_url}")

            return result

# Alias to support ResumeSource naming
ResumeSource = ResumeSource
