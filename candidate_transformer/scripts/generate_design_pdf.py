import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf(name="Vivek", email="vivek@example.com"):
    # Name of the output PDF as required by guidelines: <FullName>_<Email>_Eightfold.pdf
    pdf_filename = f"{name.replace(' ', '')}_{email.strip()}_Eightfold.pdf"
    
    # Resolve root folder to save PDF
    root_dir = Path(__file__).resolve().parent.parent.parent
    pdf_path = root_dir / pdf_filename

    # Document setup - 0.4 inch margins to fit exactly on a single page
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#1e3a8a") # Deep Blue
    c_secondary = colors.HexColor("#0f766e") # Teal Accent
    c_text = colors.HexColor("#1f2937") # Charcoal
    c_muted = colors.HexColor("#4b5563") # Muted Gray

    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=c_primary,
        alignment=1, # Center
        spaceAfter=3
    )
    
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=c_secondary,
        alignment=1,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=c_primary,
        spaceBefore=5,
        spaceAfter=3,
        borderPadding=2
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=c_text,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=body_style,
        leftIndent=10,
        firstLineIndent=-6,
        spaceAfter=2
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("Eightfold Assignment: Multi-Source Candidate Data Transformer", title_style))
    story.append(Paragraph(f"<b>Design & Technical One-Pager</b> | Candidate: {name} ({email})", subtitle_style))

    # Section 1: Pipeline Architecture
    story.append(Paragraph("1. Pipeline Architecture & Execution Flow", h1_style))
    story.append(Paragraph(
        "The engine operates on a decoupled seven-stage pipeline designed for modularity, resilience, and determinism:",
        body_style
    ))
    story.append(Paragraph("• <b>Detect</b>: Identifies source types from input paths (CSV, ATS JSON, GitHub URL, Resume, notes).", bullet_style))
    story.append(Paragraph("• <b>Extract</b>: Instantiates respective readers (e.g. LLM-based Resume, Git API) wrapped in try/excepts to prevent failures.", bullet_style))
    story.append(Paragraph("• <b>Normalize</b>: Formats phone numbers to E.164, parses location strings to sub-objects, and resolves tech skills.", bullet_style))
    story.append(Paragraph("• <b>Merge</b>: Consolidates profiles using source priorities and completes arrays/sub-objects using union rules.", bullet_style))
    story.append(Paragraph("• <b>Confidence</b>: Calculates reliability per field based on completeness, agreements, and trusted source bonuses.", bullet_style))
    story.append(Paragraph("• <b>Project</b>: Transforms the unified canonical record into custom formats based on dynamic config paths.", bullet_style))
    story.append(Paragraph("• <b>Validate</b>: Enforces JSON schema constraints at both the canonical level (pre-projection) and configuration level.", bullet_style))

    story.append(Spacer(1, 4))

    # Section 2: Canonical Output Schema
    story.append(Paragraph("2. Canonical Schema Definition", h1_style))
    schema_intro = (
        "We enforce a strict Candidate Model structure to unify conflicting source types: "
        "<b>candidate_id</b> (SHA256 string), <b>full_name</b> (string), <b>emails</b> (list), <b>phones</b> (list, E.164 format), "
        "<b>location</b> (dict: city, region, country code), <b>links</b> (dict: linkedin, github, portfolio, other[]), "
        "<b>headline</b> (string), <b>years_experience</b> (number), <b>skills</b> (list of {name, confidence, sources}), "
        "<b>experience</b> (list of {company, title, start, end, summary}), <b>education</b> (list of {institution, degree, field, end_year}), "
        "and <b>provenance</b> / <b>overall_confidence</b> metadata."
    )
    story.append(Paragraph(schema_intro, body_style))

    story.append(Spacer(1, 4))

    # Section 3: Merge, Conflict Resolution & Confidence Scoring
    story.append(Paragraph("3. Merge, Conflict Resolution & Confidence Model", h1_style))
    story.append(Paragraph(
        "<b>Conflict Resolution</b>: Single-value fields are resolved by sorting inputs by source priority first: "
        "<i>Resume (5) &gt; LinkedIn (4) &gt; GitHub (3) &gt; ATS JSON (2) &gt; Recruiter CSV/Notes (1)</i>, falling back to field completeness. "
        "List fields (emails, phones) are case-normalized and unioned. Complex objects (experience, education) are deduplicated by "
        "composite keys (company+title, institution+degree).",
        body_style
    ))
    story.append(Paragraph(
        "<b>Confidence Scorer</b>: Scores fields from 0.0 to 1.0 based on presence (+0.4), multi-source agreement (+0.3), "
        "critical fields full_name/emails (+0.2), and trusted sources resume/linkedin (+0.1). Overall confidence is the mean of field scores. "
        "Individual skills compute their own confidence: base rating (0.7-0.9 based on source trust) + 0.1 bonus per additional source.",
        body_style
    ))

    story.append(Spacer(1, 4))

    # Section 4: Configurable Output & Separation of Concerns
    story.append(Paragraph("4. Runtime Configuration Projection & Validation", h1_style))
    story.append(Paragraph(
        "A strict boundary separates the <i>canonical engine</i> from the <i>projection layer</i>. The canonical profile is validated against the default "
        "Candidate schema immediately after merge, before projection. `Projector.py` then traverses JSONPaths, renaming columns, applying "
        "E.164/canonical filters, and generating a dynamic JSON schema on the fly based on requested types, ensuring output validation is "
        "completely configurable without polluting the pipeline core.",
        body_style
    ))

    story.append(Spacer(1, 4))

    # Section 5: Edge Cases, Trade-offs & Descoped Scope
    story.append(Paragraph("5. Edge Cases & Descoped trade-offs", h1_style))
    story.append(Paragraph("• <b>Unreliable LLM Parsing</b>: PDF/Word resume parsing uses Claude, falling back to custom regex parsers if API limits are hit.", bullet_style))
    story.append(Paragraph("• <b>India-centric Localizations</b>: Location parser splits and resolves Indian states, converting implicit regions to ISO country code 'IN'.", bullet_style))
    story.append(Paragraph("• <b>Descoped out-of-time</b>: Excluded complex graph-based skill taxonomy mapping, relying instead on cosine similarity matching against a hardcoded tech skill list.", bullet_style))

    # Build the document
    doc.build(story)
    print(f"Generated 1-page design document PDF: {pdf_filename}")
    return pdf_path

if __name__ == "__main__":
    name = "Vivek"
    email = "vivek@example.com"
    
    # Parse CLI arguments if present
    if len(sys.argv) > 2:
        name = sys.argv[1]
        email = sys.argv[2]
        
    generate_pdf(name, email)
