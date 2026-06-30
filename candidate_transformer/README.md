# Candidate Transformer

## 1. Problem
Recruiters and hiring platforms process candidate profiles scattered across fragmented, unstructured, and conflicting formats (e.g., resume PDFs, recruiter spreadsheets, ATS JSON blobs, and developer GitHub profiles). This project provides a robust, localized pipeline that automatically extracts, cleans, merges, scores, projects, and validates these multi-source candidate inputs into a single canonical candidate profile.

## 2. Pipeline Overview
The processing engine orchestrates the pipeline through seven distinct stages:
```
[Inputs] ➔ detect ➔ extract ➔ normalize ➔ merge ➔ confidence ➔ project ➔ validate ➔ [JSON Output]
```
- **detect**: Identifies the source type from options: `csv`, `ats_json`, `github`, `resume`, `recruiter_notes`.
- **extract**: Instantiates appropriate `BaseSource` reader, calling `.extract()` resiliently.
- **normalize**: Formats phone numbers to E.164 (India default), resolves dates, and normalizes skills via cosine similarity.
- **merge**: Consolidates fields using source priorities, unioning array properties and resolving objects.
- **confidence**: Scores field reliability based on presence, agreement bonuses, critical fields, and trusted sources.
- **project**: Custom-renames paths, enforces missing policies (`null`/`omit`/`error`), and generates schema.
- **validate**: Matches output format against a strict Draft-07 JSON schema.

## 3. Quickstart
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment keys
export ANTHROPIC_API_KEY=your_key
export GITHUB_TOKEN=your_token  # Optional, prevents API rate-limiting

# Run candidate transformation pipeline
python cli.py transform \
  --csv sample_inputs/sample_recruiter.csv \
  --github johndoe \
  --resume sample_inputs/sample_resume.txt \
  --pretty
```

## 4. Custom Config
Using `--config`, users define projection rules. Below is the configuration in `sample_inputs/sample_config.json`:
```json
{
  "fields": [
    {"path": "full_name", "type": "string", "required": true},
    {"path": "primary_email", "from": "emails[0]", "type": "string"},
    {"path": "phone", "from": "phones[0]", "type": "string"},
    {"path": "skills", "from": "skills", "type": "array"},
    {"path": "years_experience", "from": "years_experience", "type": "number"}
  ],
  "include_confidence": true,
  "on_missing": "null"
}
```
- **fields**: Specifies mapped fields. `from` defines source paths (supporting indexing like `[0]` and dot notation like `links.github`).
- **include_confidence**: Toggle (`true`/`false`) adding `overall_confidence` and `per_field_confidence` mappings.
- **on_missing**: Action taken for missing values (`null` inserts `None`, `omit` skips keys, `error` raises ValueError).

## 5. Running Tests
Run all 41 test cases (unit, mock API, and integration) using `pytest`:
```bash
pytest candidate_transformer/tests/ -v
```

## 6. Sample Output
Running with `sample_config.json` yields:
```json
{
  "full_name": "Rahul Sharma",
  "primary_email": "rahul.dev@example.com",
  "phone": "+919876543210",
  "skills": ["AWS", "Docker", "Go", "Kubernetes", "Python", "SQL"],
  "years_experience": null,
  "overall_confidence": 0.58,
  "per_field_confidence": {
    "full_name": 1.0,
    "primary_email": 0.7,
    "phone": 0.8,
    "skills": 0.4,
    "years_experience": 0.0
  },
  "candidate_id": "19ec9913678ef6c9"
}
```

## 7. Assumptions & Descoped
- **India Focus**: Default phone parsing region set to `"IN"` and location heuristics default to Indian states/union territories mapping to country code `"IN"`.
- **LLM Token Caching**: Model calls rely on `"claude-sonnet-4-6"` with local fallbacks if API limits are reached.
- **Dot-Notation Projector**: JSONPath resolution allows nested fields (like `links.github`), which is mapped canonical-first inside pipeline stages.

## 8. Design Doc
Refer to `design_doc.pdf` (or `DESIGN.md` where applicable) for architectural diagrams, schema mappings, and pipeline design criteria.
