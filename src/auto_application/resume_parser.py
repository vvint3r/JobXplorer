"""
Resume Parser Module

Parses resume PDFs and extracts structured components for form filling.
Outputs a JSON file with sections mapped to typical ATS form fields.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

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
            "accomplishments": self.accomplishments
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, filepath: str) -> None:
        """Save components to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"Resume components saved to {filepath}")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF file."""
    try:
        import pymupdf  # PyMuPDF
        doc = pymupdf.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except ImportError:
        logger.warning("pymupdf not installed. Trying pdfplumber...")
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
            return text
        except ImportError:
            logger.error("No PDF library available. Install pymupdf or pdfplumber.")
            raise ImportError("Please install pymupdf or pdfplumber: pip install pymupdf pdfplumber")


def parse_date(date_str: str) -> Dict[str, str]:
    """
    Parse date string into month and year components.
    Handles formats like: '01/2023', 'January 2023', 'Jan 2023', 'Present'
    """
    date_str = date_str.strip()
    
    if date_str.lower() == 'present':
        now = datetime.now()
        return {"month": str(now.month).zfill(2), "year": str(now.year), "is_current": True}
    
    # Try MM/YYYY format
    match = re.match(r'(\d{1,2})/(\d{4})', date_str)
    if match:
        return {"month": match.group(1).zfill(2), "year": match.group(2), "is_current": False}
    
    # Try Month YYYY format
    month_names = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
        'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    for month_name, month_num in month_names.items():
        pattern = rf'(?i){month_name}\s*(\d{{4}})'
        match = re.search(pattern, date_str)
        if match:
            return {"month": month_num, "year": match.group(1), "is_current": False}
    
    # Try just year
    match = re.match(r'(\d{4})', date_str)
    if match:
        return {"month": "01", "year": match.group(1), "is_current": False}
    
    return {"month": "", "year": "", "is_current": False}


def parse_date_range(date_range: str) -> Dict[str, Dict[str, str]]:
    """Parse a date range like '01/2019 - 01/2023' or '01/2023 - Present'."""
    parts = re.split(r'\s*[-–—]\s*', date_range)
    
    result = {
        "from": {"month": "", "year": "", "is_current": False},
        "to": {"month": "", "year": "", "is_current": False}
    }
    
    if len(parts) >= 1:
        result["from"] = parse_date(parts[0])
    if len(parts) >= 2:
        result["to"] = parse_date(parts[1])
    
    return result


def create_work_experience_entry(
    job_title: str,
    company: str,
    location: str,
    date_from: Dict[str, str],
    date_to: Dict[str, str],
    description: List[str]
) -> Dict[str, Any]:
    """Create a structured work experience entry."""
    return {
        "job_title": job_title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "currently_work_here": date_to.get("is_current", False),
        "from": {
            "month": date_from.get("month", ""),
            "year": date_from.get("year", "")
        },
        "to": {
            "month": date_to.get("month", ""),
            "year": date_to.get("year", "")
        },
        "role_description": "\n".join(description) if description else ""
    }


def create_education_entry(
    school: str,
    degree: str,
    field_of_study: str,
    date_from: Dict[str, str],
    date_to: Dict[str, str],
    gpa: Optional[str] = None
) -> Dict[str, Any]:
    """Create a structured education entry."""
    return {
        "school_or_university": school.strip(),
        "degree": degree.strip(),
        "field_of_study": field_of_study.strip(),
        "from": {
            "month": date_from.get("month", ""),
            "year": date_from.get("year", "")
        },
        "to": {
            "month": date_to.get("month", ""),
            "year": date_to.get("year", "")
        },
        "gpa": gpa
    }


def parse_resume_text(text: str) -> ResumeComponents:
    """
    Parse extracted resume text into structured components.
    This is a general parser - customize for specific resume formats.
    """
    components = ResumeComponents()
    
    # Basic section detection patterns
    sections = {
        'summary': r'(?i)(professional\s*summary|summary|profile|objective)',
        'experience': r'(?i)(professional\s*experience|work\s*experience|experience|employment)',
        'education': r'(?i)(education|academic)',
        'skills': r'(?i)(skills|technical\s*skills|core\s*competencies)',
        'accomplishments': r'(?i)(accomplishments|achievements|key\s*results)'
    }
    
    # This is a simplified parser - in production, you'd use more sophisticated NLP
    logger.info("Parsing resume text into components...")
    
    return components


def load_components_from_json(filepath: str) -> ResumeComponents:
    """Load resume components from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    components = ResumeComponents()
    components.personal_info = data.get("personal_info", {})
    components.professional_summary = data.get("professional_summary", "")
    components.work_experience = data.get("work_experience", [])
    components.education = data.get("education", [])
    components.skills = data.get("skills", [])
    components.accomplishments = data.get("accomplishments", [])
    
    return components


def get_resume_components(resume_path: str) -> ResumeComponents:
    """
    Get structured resume components.
    First checks for existing _components.json file, otherwise parses the PDF.
    """
    resume_path = Path(resume_path)
    components_path = resume_path.with_suffix('.json').parent / f"{resume_path.stem}_components.json"
    
    if components_path.exists():
        logger.info(f"Loading existing components from {components_path}")
        return load_components_from_json(str(components_path))
    
    logger.info(f"Parsing resume from {resume_path}")
    text = extract_text_from_pdf(str(resume_path))
    components = parse_resume_text(text)
    
    # Save for future use
    components.save(str(components_path))
    
    return components


# Form field value getters
def get_work_experience_for_form(components: ResumeComponents, index: int = 0) -> Dict[str, str]:
    """Get work experience entry formatted for form filling."""
    if index >= len(components.work_experience):
        return {}
    
    exp = components.work_experience[index]
    return {
        "job_title": exp.get("job_title", ""),
        "company": exp.get("company", ""),
        "currently_work_here": exp.get("currently_work_here", False),
        "from_month": exp.get("from", {}).get("month", ""),
        "from_year": exp.get("from", {}).get("year", ""),
        "to_month": exp.get("to", {}).get("month", ""),
        "to_year": exp.get("to", {}).get("year", ""),
        "role_description": exp.get("role_description", ""),
        "location": exp.get("location", "")
    }


def get_education_for_form(components: ResumeComponents, index: int = 0) -> Dict[str, str]:
    """Get education entry formatted for form filling."""
    if index >= len(components.education):
        return {}
    
    edu = components.education[index]
    return {
        "school": edu.get("school_or_university", ""),
        "degree": edu.get("degree", ""),
        "field_of_study": edu.get("field_of_study", ""),
        "from_month": edu.get("from", {}).get("month", ""),
        "from_year": edu.get("from", {}).get("year", ""),
        "to_month": edu.get("to", {}).get("month", ""),
        "to_year": edu.get("to", {}).get("year", ""),
        "gpa": edu.get("gpa", "")
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        components = get_resume_components(pdf_path)
        print(components.to_json())
    else:
        print("Usage: python resume_parser.py <path_to_resume.pdf>")

