# TrueProfile

Ingest, normalize, deduplicate, and project multi-source candidate profiles with semantic skill mapping and trust-weighted confidence scoring.

![TrueProfile Dashboard](assets/dashboard.png)

## Table of Contents
- [Features](#features)
  - [Multi-Source Ingestion](#multi-source-ingestion)
  - [Normalization Engine](#normalization-engine)
  - [Merge & Deduplication](#merge--deduplication)
  - [Confidence Scoring](#confidence-scoring)
  - [Configurable Output Projection](#configurable-output-projection)
- [System Architecture Overview](#system-architecture-overview)
- [Design Decisions & Reasoning](#design-decisions--reasoning)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Edge Cases Handled](#edge-cases-handled)
- [Assumptions & Descoped](#assumptions--descoped)
- [Sample Produced JSON Output](#sample-produced-json-output)
- [Real Produced Output (Jane Doe)](#real-produced-output-jane-doe)
- [Demo Video](#demo-video)
- [Contact](#contact)

---

## Features

### Multi-Source Ingestion
* **Resilient Document Parsing**: Reads and parses unstructured PDF/TXT resumes using custom section-matching heuristics, filtering out layout/visual dividers, and falling back to Anthropic Claude LLM extraction when credentials are set.
* **CSV Spreadsheets**: Automatically extracts structured rows from recruiter sheets, supporting header variations via key normalization.
* **GitHub Integration**: Connects to the GitHub API dynamically to fetch repositories, coding languages, and user profiles, enriching candidate technical skills.
* **ATS JSON Blobs**: Extracts parsed application tracking system outputs using JSON schemas.

### Normalization Engine
* **Phone Standardizer**: Normalizes international telephone inputs to the E.164 standard using the Google `phonenumbers` port, defaulting to the `"IN"` (India) country code.
* **Date Standardizer**: Resolves complex, unstructured date formats and intervals into standard `YYYY-MM` representation. Treats `"Present"` or `"Current"` as active reference dates.
* **Semantic Skill Canonicalization**: Performs cosine-similarity skills alignment using a sentence-transformer model (`all-MiniLM-L6-v2`), grouping synonymous or misspelled tech keywords into canon lists.

### Merge & Deduplication
* **Fuzzy Deduplication**: Consolidates multiple source records into a single merged profile.
* **Conflict Resolution Policy**: Merges list fields (like education, experience) based on logical matching rules (e.g. merging jobs that share the same title and time range, or mapping degree abbreviations like `B.E.` -> `Bachelor of Engineering`).
* **Acronym Mapping**: Automatically matches abbreviations (like `SPPU` -> `Savitribai Phule Pune University`).

### Confidence Scoring
* **Field-Level Confidence**: Assigns scoring metrics to each field (`0.0` to `1.0`) based on value presence (`+0.5`), agreement between multiple sources (`+0.2`), critical profile fields like email/name (`+0.2`), and high-fidelity source trust (`+0.2`).
* **Overall Confidence**: Calculates a weighted average score across populated candidate details.

### Configurable Output Projection
* **Runtime JSON Configuration**: Maps paths, splits indexes, and supports dot-notation paths (e.g. `links.github`).
* **Field Renaming**: Allows dynamic output renaming at runtime.
* **Missing-Value Policies**: Configurable options for handling missing fields: `null` (inserts default values), `omit` (skips keys), or `error` (raises exceptions).

---

## System Architecture Overview

### High-Level Flow
```
CSV/PDF Input ➔ Extract ➔ Normalize ➔ Merge ➔ Confidence ➔ Project ➔ Validate ➔ Canonical JSON Output
```

### Architecture Diagram

```mermaid
graph TD
    %% Input Sources
    subgraph Input ["Input Sources"]
        PDF[Resume PDF/TXT]
        CSV[Recruiter CSV]
        ATS[ATS JSON]
        GH[GitHub Profile URL]
    end

    %% Pipeline Processing
    subgraph Pipeline ["TrueProfile Core Ingestion Pipeline"]
        DET[1. Detection Engine]
        EXT[2. Extraction Engine]
        NORM[3. Normalization Engine]
        MRG[4. Fuzzy Merger]
        CONF[5. Confidence Scorer]
        PROJ[6. Output Projector]
        VAL[7. Schema Validator]
    end

    %% Process flow
    PDF --> DET
    CSV --> DET
    ATS --> DET
    GH --> DET

    DET --> EXT
    EXT --> NORM
    NORM --> MRG
    MRG --> CONF
    CONF --> PROJ
    PROJ --> VAL

    %% External APIs and Models
    subgraph External ["External Services"]
        LLM[Anthropic Claude API]
        ST[Sentence-Transformers all-MiniLM-L6-v2]
        GH_API[GitHub REST API]
    end

    EXT -.->|Fallback Ingestion| LLM
    NORM -.->|Semantic Skill Alignment| ST
    EXT -.->|Fetch Language Metadata| GH_API

    %% Final Outputs
    subgraph Output ["Target Projection"]
        JSON[Canonical JSON Profile]
    end

    VAL --> JSON
```

### Data Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Recruiter as Recruiter / System API
    participant DET as Detection & Ingestion
    participant EXT as Extraction Engine
    participant NORM as Normalizer
    participant MRG as Merger
    participant CONF as Scorer
    participant PROJ as Projector
    participant VAL as Validator

    Recruiter->>DET: Submit inputs (PDF/CSV/GitHub URL)
    DET->>EXT: Standardized raw file streams
    Note over EXT: Fallback to local regex / LLM API
    EXT->>NORM: Raw Extracted JSON profiles
    Note over NORM: Cosine similarity for skills<br/>E.164 phone formatting
    NORM->>MRG: Cleaned partial profiles
    Note over MRG: Deduplication & date overlap check
    MRG->>CONF: Merged Profile Document
    Note over CONF: Presence & agreement calculation
    CONF->>PROJ: Scored Canonical Profile
    Note over PROJ: Dot-notation schema mapping & omit policy
    PROJ->>VAL: Projected Output JSON
    VAL->>Recruiter: Verified Canonical JSON Output
```

---

## Design Decisions & Reasoning

* **Merge Key Strategy**: Consolidates experience entries by comparing overlapping dates and exact matching titles. If a candidate holds the same role during the exact same time interval, it is mathematically consolidated to prevent duplication.
* **Source Priority Order**: Set to `resume` (5) > `linkedin` (4) > `github` (3) > `ats_json` (2) > `recruiter_csv` (1). This prioritizes high-fidelity, candidate-submitted documents over third-party spreadsheets.
* **Confidence Scoring Rules**: Populated values start at a baseline of `0.5`, with additions for critical fields (name/email) and trusted sources, yielding scores like `0.9` for verified emails instead of lower arbitrary averages.
* **Separated Projection Layer**: Decoupled the canonical merging system from the user-facing output projection. This ensures downstream API consumers can customize naming conventions and missing policies without affecting the core data collection.
* **Trade-offs**: Chose advanced regex rules for fallback text parsers over a full transformer model to ensure zero-cost local execution during Claude API rate-limiting or network issues.

---

## Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.13 / Flask (Web App) / Click (CLI) |
| **Frontend** | HTML5 / CSS3 (Vanilla Dark Mode theme) / JavaScript (ES6+) |
| **AI/LLM** | Anthropic Claude SDK (fallback parser) |
| **Semantic Extraction** | Sentence-Transformers (`all-MiniLM-L6-v2` via PyTorch) |
| **PDF Parsing** | `pdfplumber` |
| **Validation** | `jsonschema` (Draft-07 schema compliance) |

---

## Getting Started

### Clone & Install
```bash
# Clone the repository
git clone https://github.com/vivekjadhav23/TrueProfile.git
cd TrueProfile

# Install dependencies
pip install -r candidate_transformer/requirements.txt
```

### Environment Variables
Optionally configure keys for full API ingestion capabilities:
```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export GITHUB_TOKEN="your-github-token"
```

### Run Dev Server
```bash
# Run Flask web interface
python -m candidate_transformer.ui.app
```

### Open in Browser
Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser to access the TrueProfile interface.

---

## Edge Cases Handled
* **Font CID Bullets**: Strip PDF font artifacts like `(cid:127)` from summaries.
* **Present Date Margins**: Resolves years of experience metrics by matching `"Present"` as June 2026.
* **Layout Divider Cleaning**: Automatically removes line breaks consisting of repeat characters (e.g. `-----`).
* **Degree Splitting**: Safely splits `"B.E. Computer Engineering"` into degree `"B.E."` and field `"Computer Engineering"`.
* **Grade Filtering**: Prevents exam ranks or CGPA lines containing `"College Topper"` from creating false university entries.

---

## Assumptions & Descoped

### Assumptions
* **India-First Ingestion**: The E.164 phone standardizer defaults to the `"IN"` (India) region code.
* **Active Duration Anchors**: Career durations terminating in `"Present"` or `"Current"` assume a reference anchor date of June 2026.
* **Semantic Vector Vocabulary**: Semantic skill classification assumes tech-stack vocabularies matching the local `all-MiniLM-L6-v2` encoder map.

### Descoped
* **Dynamic Output Schemas**: Projection formats support JSON mapping rules but require validation against standard JSON Draft-07 structures. Runtime custom formats outside standard Draft-07 constraints are descoped.
* **Scanned PDF Ingestion**: Document extraction reads standard text layer PDFs. OCR for scanned image-only files is descoped.

---

## Sample Produced JSON Output

Below is a sample projected JSON output produced by the pipeline:
```json
{
  "candidate_id": "b891e32246506c51",
  "full_name": "Vivek Dhananjay Jadhav",
  "primary_email": "vivekdjadhav2004@gmail.com",
  "phone": "+918766069885",
  "location": {
    "city": "Pune",
    "region": "Maharashtra",
    "country": "IN"
  },
  "skills": [
    "C++",
    "DBMS",
    "Express.js",
    "Git",
    "HTML",
    "Java",
    "JavaScript",
    "MongoDB",
    "MySQL",
    "Node.js",
    "Python",
    "React",
    "Redis",
    "SQL"
  ],
  "education": [
    {
      "institution": "Dr. D. Y. Patil Institute of Technology Pune, Maharashtra",
      "degree": "B.E.",
      "field": "Computer Engineering",
      "end_year": 2027
    },
    {
      "institution": "Saraswati Vidyamandir College of Science Shahada, Maharashtra",
      "degree": "Higher Secondary (Class XII)",
      "field": null,
      "end_year": 2023
    }
  ],
  "experience": [
    {
      "company": "CodeAlpha",
      "title": "Full Stack Developer Intern",
      "start": "2026-01",
      "end": "2026-02",
      "summary": "Built 2 production-ready full-stack applications using the MERN stack with secure coding practices, modular architecture, and end-to-end feature ownership from design to deployment."
    }
  ],
  "years_experience": 0.1,
  "overall_confidence": 0.74
}
```

---

## Real Produced Output (Jane Doe)

Below is the real projected and merged JSON output produced by running the pipeline on [test_candidate_recruiter.csv](file:///c:/Users/Vivek/Desktop/Candidate-Transformer/test_candidate_recruiter.csv) and [test_candidate_resume.pdf](file:///c:/Users/Vivek/Desktop/Candidate-Transformer/test_candidate_resume.pdf):

```json
{
  "full_name": "JANE DOE",
  "emails": [
    "jane.doe@example.com"
  ],
  "phones": [
    "+919876543210"
  ],
  "headline": "Software Engineer",
  "location": {
    "city": "Pune",
    "region": "Maharashtra",
    "country": "IN"
  },
  "links": {
    "linkedin": "https://linkedin.com/in/janedoe",
    "github": "https://github.com/janedoe",
    "portfolio": null,
    "other": []
  },
  "years_experience": 2.7,
  "skills": [
    {
      "name": "Docker",
      "confidence": 1.0,
      "sources": [
        "recruiter_csv",
        "resume"
      ]
    },
    {
      "name": "Git",
      "confidence": 0.9,
      "sources": [
        "resume"
      ]
    },
    {
      "name": "Python",
      "confidence": 1.0,
      "sources": [
        "recruiter_csv",
        "resume"
      ]
    },
    {
      "name": "REST API",
      "confidence": 0.9,
      "sources": [
        "resume"
      ]
    },
    {
      "name": "React",
      "confidence": 1.0,
      "sources": [
        "recruiter_csv",
        "resume"
      ]
    },
    {
      "name": "SQL",
      "confidence": 1.0,
      "sources": [
        "recruiter_csv",
        "resume"
      ]
    }
  ],
  "experience": [
    {
      "company": "Google",
      "title": "Software Engineer",
      "start": "2024-01",
      "end": "present",
      "summary": "Developed REST APIs using Python and Flask, improving response latency by 20%.\nContainerized application modules using Docker for local and staging deployments."
    },
    {
      "company": "Microsoft",
      "title": "Software Engineer Intern",
      "start": "2023-05",
      "end": "2023-08",
      "summary": "Developed interface elements using ReactJS, facilitating seamless navigation workflows."
    }
  ],
  "education": [
    {
      "institution": "Savitribai Phule Pune University",
      "degree": "B.E",
      "field": "Computer Engineering",
      "end_year": "2024"
    }
  ],
  "provenance": [
    {
      "field": "full_name",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "emails",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "phones",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "headline",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "location.city",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "location.region",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "location.country",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "links.linkedin",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "links.github",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "years_experience",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "skills",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "skills",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "experience",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "experience",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    },
    {
      "field": "education",
      "source": "resume",
      "method": "regex_fallback"
    },
    {
      "field": "education",
      "source": "recruiter_csv",
      "method": "csv_parsing"
    }
  ],
  "per_field_confidence": {
    "full_name": 0.9,
    "emails": 0.7,
    "phones": 0.5,
    "headline": 0.5,
    "location": 0.9,
    "links": 0.7,
    "years_experience": 0.7,
    "skills": 0.9,
    "experience": 0.9,
    "education": 0.9
  },
  "overall_confidence": 0.76,
  "candidate_id": "9864426aa1f189fa"
}
```

---

## Demo Video
`[INSERT DEMO VIDEO LINK/EMBED HERE]`

---

## Contact
* **Name**: Vivek Jadhav
* **GitHub**: [vivekjadhav23](https://github.com/vivekjadhav23)
* **LinkedIn**: [vivek-jadhav-m23](https://linkedin.com/in/vivek-jadhav-m23)
