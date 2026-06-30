import pytest
from unittest.mock import patch, Mock
from candidate_transformer.sources import ResumeSource

def test_resume_source_llm_success(tmp_path):
    """
    Test successful resume text parsing via mocked Claude Anthropic API.
    """
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text("Resume of Alice Bob.", encoding="utf-8")

    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [
            Mock(text=(
                '{\n'
                '  "full_name": "Alice Bob",\n'
                '  "emails": ["alice@example.com"],\n'
                '  "phones": ["+1-555-123-4567"],\n'
                '  "location": "San Francisco, CA",\n'
                '  "linkedin_url": "linkedin.com/in/alice",\n'
                '  "github_url": "github.com/alice",\n'
                '  "headline": "Lead Systems Engineer",\n'
                '  "years_experience": 8,\n'
                '  "skills": ["C++", "Python", "Rust"],\n'
                '  "experience": [\n'
                '    {"company": "Big Tech", "title": "Staff Eng", "start": "2020", "end": "present", "summary": "Did stuff"}\n'
                '  ],\n'
                '  "education": [\n'
                '    {"institution": "Stanford", "degree": "BS", "field": "CS", "end_year": 2018}\n'
                '  ]\n'
                '}'
            ))
        ]
        mock_client.messages.create.return_value = mock_message

        source = ResumeSource()
        res = source.extract(str(resume_file))

        assert res["source_name"] == "resume"
        assert res["full_name"] == "Alice Bob"
        assert res["emails"] == ["alice@example.com"]
        assert res["phones"] == ["+1-555-123-4567"]
        assert res["skills"] == ["C++", "Python", "Rust"]
        assert res["low_confidence"] is False

def test_resume_source_fallback_to_regex(tmp_path):
    """
    Test extraction falling back to regular expressions when the Anthropic API fails.
    """
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text(
        "Resume details:\n"
        "Send email to contact@candidate.org or call +12345678901 for more details.\n",
        encoding="utf-8"
    )

    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Key is missing or invalid.")

        source = ResumeSource()
        res = source.extract(str(resume_file))

        assert res["source_name"] == "resume"
        assert res["full_name"] is None
        assert res["emails"] == ["contact@candidate.org"]
        assert res["phones"] == ["+12345678901"]
        assert res["low_confidence"] is True
        assert res["confidence"] == "low"

def test_resume_source_pdf_extraction():
    """
    Test that PDF extraction correctly calls pdfplumber.
    """
    with patch("pdfplumber.open") as mock_pdf_open:
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Extracted text from PDF"
        mock_pdf.pages = [mock_page]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            mock_message = Mock()
            mock_message.content = [Mock(text='{"full_name": "PDF Candidate"}')]
            mock_client.messages.create.return_value = mock_message

            source = ResumeSource()
            res = source.extract("dummy.pdf")

            mock_pdf_open.assert_called_once_with("dummy.pdf")
            assert res["full_name"] == "PDF Candidate"

def test_resume_source_docx_extraction():
    """
    Test that DOCX extraction correctly calls python-docx.
    """
    with patch("docx.Document") as mock_docx_doc:
        mock_doc = Mock()
        mock_para = Mock(text="Extracted text from DOCX paragraph")
        mock_doc.paragraphs = [mock_para]
        mock_docx_doc.return_value = mock_doc

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            mock_message = Mock()
            mock_message.content = [Mock(text='{"full_name": "DOCX Candidate"}')]
            mock_client.messages.create.return_value = mock_message

            source = ResumeSource()
            res = source.extract("dummy.docx")

            mock_docx_doc.assert_called_once_with("dummy.docx")
            assert res["full_name"] == "DOCX Candidate"
