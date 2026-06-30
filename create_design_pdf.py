import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def build_pdf():
    pdf_filename = "Vivek_Sharma_vivek.sharma@gmail.com_Eightfold.pdf"
    
    # Page setup - 0.45 in margins for compact one-page layout
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        rightMargin=32,
        leftMargin=32,
        topMargin=32,
        bottomMargin=32
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2
    )
    
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )
    
    sec_title_style = ParagraphStyle(
        'SecTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=5,
        spaceAfter=3
    )
    
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )

    bold_body_style = ParagraphStyle(
        'BoldBodyText',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    story = []
    
    # Title & Metadata
    story.append(Paragraph("TECHNICAL DESIGN: MULTI-SOURCE CANDIDATE DATA TRANSFORMER", title_style))
    story.append(Paragraph("<b>Author:</b> Vivek Sharma &nbsp;|&nbsp; <b>Email:</b> vivek.sharma@gmail.com &nbsp;|&nbsp; <b>Deliverable:</b> Technical Design One-Pager", subtitle_style))
    
    # Define grid columns for two-column design layout (left: pipeline/schema, right: policies/edge cases)
    left_flow = []
    right_flow = []
    
    # Left Column Content
    left_flow.append(Paragraph("1. ARCHITECTURAL PIPELINE OVERVIEW", sec_title_style))
    left_flow.append(Paragraph(
        "A modular, deterministic pipe-and-filter architecture digests candidate profiles:<br/>"
        "<b>• Detect & Extract:</b> Ingests resumes (PDF/TXT), Recruiter CSVs, and ATS JSONs. If a GitHub profile URL is detected, the pipeline automatically spins up a background thread to call the GitHub API and ingest the candidate's public details.<br/>"
        "<b>• Normalize:</b> Cleans data: validates and formats phone numbers to E.164, parses locations to city/region/country (mapping country to ISO-3166-1 alpha-2), standardizes dates to YYYY-MM, and matches skills against a canonical database using semantic sentence embeddings (all-MiniLM-L6-v2).<br/>"
        "<b>• Merge:</b> Resolves overlapping entities via priority ranking and deduplication heuristics.<br/>"
        "<b>• Scorer:</b> Assigns field and record-level confidence scores.<br/>"
        "<b>• Project & Validate:</b> Dynamically maps fields using JSONPath syntax, and runs a secondary runtime validation on the output.", body_style))
    
    left_flow.append(Spacer(1, 6))
    
    left_flow.append(Paragraph("2. CANONICAL OUTPUT SCHEMA & NORMALIZATIONS", sec_title_style))
    left_flow.append(Paragraph(
        "The system standardizes data into a strict <b>Canonical Candidate Model</b>:<br/>"
        "• <b>candidate_id:</b> Deterministic SHA-256 hash of sorted emails + lowercase name.<br/>"
        "• <b>full_name:</b> Cleaned and converted to title case.<br/>"
        "• <b>emails / phones:</b> Deduped lists; phones are validated and stored in E.164 format.<br/>"
        "• <b>location:</b> Structured object: {city, region, country} (ISO country codes).<br/>"
        "• <b>links:</b> Structured object: {linkedin, github, portfolio, other[]}.<br/>"
        "• <b>skills:</b> Normalized canonical skill names with field confidence & source history.<br/>"
        "• <b>experience / education:</b> Nested arrays containing standard date and degree details.<br/>"
        "• <b>provenance:</b> Field-level audit trail tracking the source and method used for each value.<br/>"
        "• <b>overall_confidence:</b> Score representing merged data reliability.", body_style))
    
    # Right Column Content
    right_flow.append(Paragraph("3. MERGE & CONFLICT-RESOLUTION POLICY", sec_title_style))
    right_flow.append(Paragraph(
        "<b>• Conflict Resolution:</b> Single-value fields are resolved using priority weighting (Resume: 5, LinkedIn: 4, GitHub: 3, ATS: 2, CSV: 1). If there is a tie, the more complete/longer string is chosen.<br/>"
        "<b>• Fuzzy Deduplication:</b> Lists are merged. Education items standardize degree abbreviations (e.g. 'B.E' -> 'Bachelor of Engineering') and perform acronym mapping (e.g. 'SPPU' -> 'Savitribai Phule Pune University').<br/>"
        "<b>• Classification Correction:</b> If a candidate's field-of-study (e.g. 'Computer Engineering') is misclassified as the institution, the merger swaps it into the 'field' key and keeps the real university name.<br/>"
        "<b>• Scorer:</b> Calculates field confidence based on source reputation, value presence, and extraction method (LLM vs regex). Overall confidence averages only active, non-zero scored fields.", body_style))
    
    right_flow.append(Spacer(1, 6))
    
    right_flow.append(Paragraph("4. RUNTIME CUSTOM-OUTPUT PROJECTION", sec_title_style))
    right_flow.append(Paragraph(
        "Users can project the canonical profile to any custom structure using a JSON config:<br/>"
        "• <b>Path Resolution:</b> Supports recursive dot/index queries (e.g. <i>skills[0].name</i> or <i>emails[0]</i>).<br/>"
        "• <b>Type Coercion:</b> If a path resolves to an object (e.g. a skill dictionary) but the target type is 'string', it automatically extracts the primary textual field (e.g., 'name') to avoid mismatches.<br/>"
        "• <b>Dynamic Schema Validation:</b> Reconstructs a JSON Schema at runtime from the projection settings (supporting array, object, and type variants like <i>string[]</i>) to validate the projected output structure.", body_style))
    
    right_flow.append(Spacer(1, 6))
    
    right_flow.append(Paragraph("5. EDGE CASES HANDLED & TIME TRADE-OFFS", sec_title_style))
    right_flow.append(Paragraph(
        "<b>• Acronym / Substring Matches:</b> Handled school and degree name variations to merge education records cleanly.<br/>"
        "<b>• LLM Failure Fallback:</b> Integrated a robust regex fallback parser that extracts all profile sections (name, links, skills, experience, education) from PDF content if API keys are absent.<br/>"
        "<b>• Bracketed Type Notation:</b> Mapped bracketed types (e.g., <i>string[]</i>) to standard JSON Schema arrays.<br/>"
        "<b>• Deliberate Trade-offs (Time Pressure):</b> Excluded support for temporal overlap checking in experience timelines and manual conflict overrides via the UI (defaults to prioritized merging).", body_style))
    
    # Render two columns using a Table
    data = [[left_flow, right_flow]]
    col_width = 3.65 * inch
    t = Table(data, colWidths=[col_width, col_width])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(t)
    
    # Build Document
    doc.build(story)
    print("PDF build successful: " + pdf_filename)

if __name__ == "__main__":
    build_pdf()
