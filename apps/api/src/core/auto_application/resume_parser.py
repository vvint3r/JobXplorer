"""Resume parser — extracted from src/auto_application/resume_parser.py.

Parses resume PDFs into structured components JSON.
Operates on bytes (not file paths) for SaaS compatibility.
"""

import json
import logging
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResumeComponents:
    """Structured resume data for form filling."""

    def __init__(self):
        self.personal_info: Dict[str, str] = {}
        self.professional_summary: str = ""
        self.work_experience: List[Dict[str, Any]] = []
        self.education: List[Dict[str, Any]] = []
        self.skills: List[str] = []
        self.accomplishments: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "personal_info": self.personal_info,
            "professional_summary": self.professional_summary,
            "work_experience": self.work_experience,
            "education": self.education,
            "skills": self.skills,
            "accomplishments": self.accomplishments,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes (no file path needed)."""
    try:
        import pymupdf

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            doc = pymupdf.open(tmp.name)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
    except ImportError:
        pass

    try:
        import pdfplumber
        import io

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except ImportError:
        pass

    raise ImportError("No PDF library available. Install pymupdf or pdfplumber.")


def parse_date(date_str: str) -> Dict[str, str]:
    """Parse date string into month and year components."""
    date_str = date_str.strip()

    if date_str.lower() == "present":
        now = datetime.now()
        return {"month": str(now.month).zfill(2), "year": str(now.year), "is_current": True}

    match = re.match(r"(\d{1,2})/(\d{4})", date_str)
    if match:
        return {"month": match.group(1).zfill(2), "year": match.group(2), "is_current": False}

    month_names = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09",
        "oct": "10", "nov": "11", "dec": "12",
    }

    for month_name, month_num in month_names.items():
        pattern = rf"(?i){month_name}\s*(\d{{4}})"
        match = re.search(pattern, date_str)
        if match:
            return {"month": month_num, "year": match.group(1), "is_current": False}

    match = re.match(r"(\d{4})", date_str)
    if match:
        return {"month": "01", "year": match.group(1), "is_current": False}

    return {"month": "", "year": "", "is_current": False}


def parse_resume_text(text: str) -> ResumeComponents:
    """Parse extracted resume text into structured components.

    Uses section header detection and heuristic extraction.
    """
    components = ResumeComponents()

    if not text or len(text.strip()) < 50:
        return components

    lines = text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # Section header patterns
    section_patterns = {
        "summary": re.compile(r"(?i)^(professional\s*summary|summary|profile|objective)\s*:?\s*$"),
        "experience": re.compile(r"(?i)^(professional\s*experience|work\s*experience|experience|employment\s*history)\s*:?\s*$"),
        "education": re.compile(r"(?i)^(education|academic\s*background)\s*:?\s*$"),
        "skills": re.compile(r"(?i)^(skills|technical\s*skills|core\s*competencies|areas\s*of\s*expertise)\s*:?\s*$"),
        "accomplishments": re.compile(r"(?i)^(accomplishments|achievements|key\s*results|awards)\s*:?\s*$"),
    }

    # Split into sections
    sections: Dict[str, List[str]] = {}
    current_section = "header"
    sections[current_section] = []

    for line in lines:
        matched = False
        for sec_name, pattern in section_patterns.items():
            if pattern.match(line):
                current_section = sec_name
                sections[current_section] = []
                matched = True
                break
        if not matched:
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append(line)

    # Extract personal info from header
    if "header" in sections:
        header = sections["header"]
        if header:
            components.personal_info["name"] = header[0] if header else ""
            for line in header:
                email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", line)
                if email_match:
                    components.personal_info["email"] = email_match.group()
                phone_match = re.search(r"[\+]?[\d\s\(\)\-\.]{10,}", line)
                if phone_match:
                    components.personal_info["phone"] = phone_match.group().strip()
                linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", line, re.I)
                if linkedin_match:
                    components.personal_info["linkedin"] = linkedin_match.group()

    # Extract summary
    if "summary" in sections:
        components.professional_summary = " ".join(sections["summary"])

    # Extract skills
    if "skills" in sections:
        for line in sections["skills"]:
            # Handle comma/pipe/bullet-separated skills
            skills = re.split(r"[,|•·]", line)
            for skill in skills:
                skill = skill.strip().strip("-").strip("•").strip()
                if skill and len(skill) > 1:
                    components.skills.append(skill)

    # Extract accomplishments
    if "accomplishments" in sections:
        for line in sections["accomplishments"]:
            cleaned = line.strip().lstrip("-•·").strip()
            if cleaned:
                components.accomplishments.append(cleaned)

    return components


def parse_resume_from_bytes(pdf_bytes: bytes) -> tuple[ResumeComponents, str]:
    """Parse a resume PDF from bytes. Returns (components, raw_text)."""
    text = extract_text_from_pdf_bytes(pdf_bytes)
    components = parse_resume_text(text)
    return components, text
