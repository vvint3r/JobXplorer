"""
Resume Components Loader

Loads structured resume components for form filling.
Provides convenient accessors for work experience, education, and other sections.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ResumeComponentsLoader:
    """Loads and provides access to structured resume components for form filling."""
    
    def __init__(self, components_path: str = None, config: Dict = None):
        """
        Initialize the loader.
        
        Args:
            components_path: Path to the resume components JSON file
            config: Optional user config dict (will look for resume_components_path)
        """
        self.components: Dict[str, Any] = {}
        
        if components_path:
            self.load(components_path)
        elif config and config.get("application_info", {}).get("resume_components_path"):
            self.load(config["application_info"]["resume_components_path"])
    
    def load(self, filepath: str) -> bool:
        """Load resume components from a JSON file."""
        if not os.path.exists(filepath):
            logger.error(f"Resume components file not found: {filepath}")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.components = json.load(f)
            logger.info(f"Loaded resume components from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error loading resume components: {e}")
            return False
    
    # ==================== PERSONAL INFO ====================
    
    @property
    def personal_info(self) -> Dict[str, str]:
        """Get personal info section."""
        return self.components.get("personal_info", {})
    
    @property
    def full_name(self) -> str:
        return self.personal_info.get("full_name", "")
    
    @property
    def first_name(self) -> str:
        return self.personal_info.get("first_name", "")
    
    @property
    def last_name(self) -> str:
        return self.personal_info.get("last_name", "")
    
    @property
    def email(self) -> str:
        return self.personal_info.get("email", "")
    
    @property
    def phone(self) -> str:
        return self.personal_info.get("phone", "")
    
    @property
    def phone_formatted(self) -> str:
        """Phone number with only digits (for form fields)."""
        return self.personal_info.get("phone_formatted", 
                                       ''.join(filter(str.isdigit, self.phone)))
    
    @property
    def linkedin(self) -> str:
        return self.personal_info.get("linkedin", "")
    
    # ==================== PROFESSIONAL SUMMARY ====================
    
    @property
    def professional_summary(self) -> str:
        """Get professional summary."""
        return self.components.get("professional_summary", "")
    
    # ==================== WORK EXPERIENCE ====================
    
    @property
    def work_experience(self) -> List[Dict[str, Any]]:
        """Get all work experience entries."""
        return self.components.get("work_experience", [])
    
    @property
    def work_experience_count(self) -> int:
        """Get number of work experience entries."""
        return len(self.work_experience)
    
    def get_work_experience(self, index: int = 0) -> Optional[Dict[str, Any]]:
        """Get a specific work experience entry by index."""
        if 0 <= index < self.work_experience_count:
            return self.work_experience[index]
        return None
    
    def get_work_exp_job_title(self, index: int = 0) -> str:
        """Get job title for work experience at index."""
        exp = self.get_work_experience(index)
        return exp.get("job_title", "") if exp else ""
    
    def get_work_exp_company(self, index: int = 0) -> str:
        """Get company for work experience at index."""
        exp = self.get_work_experience(index)
        return exp.get("company", "") if exp else ""
    
    def get_work_exp_location(self, index: int = 0) -> str:
        """Get location for work experience at index."""
        exp = self.get_work_experience(index)
        return exp.get("location", "") if exp else ""
    
    def get_work_exp_currently_work_here(self, index: int = 0) -> bool:
        """Check if currently working at this position."""
        exp = self.get_work_experience(index)
        return exp.get("currently_work_here", False) if exp else False
    
    def get_work_exp_from_month(self, index: int = 0) -> str:
        """Get start month for work experience at index."""
        exp = self.get_work_experience(index)
        if exp:
            return exp.get("from", {}).get("month", "")
        return ""
    
    def get_work_exp_from_year(self, index: int = 0) -> str:
        """Get start year for work experience at index."""
        exp = self.get_work_experience(index)
        if exp:
            return exp.get("from", {}).get("year", "")
        return ""
    
    def get_work_exp_to_month(self, index: int = 0) -> str:
        """Get end month for work experience at index."""
        exp = self.get_work_experience(index)
        if exp:
            return exp.get("to", {}).get("month", "")
        return ""
    
    def get_work_exp_to_year(self, index: int = 0) -> str:
        """Get end year for work experience at index."""
        exp = self.get_work_experience(index)
        if exp:
            return exp.get("to", {}).get("year", "")
        return ""
    
    def get_work_exp_description(self, index: int = 0) -> str:
        """Get role description for work experience at index."""
        exp = self.get_work_experience(index)
        return exp.get("role_description", "") if exp else ""
    
    def get_work_exp_form_data(self, index: int = 0) -> Dict[str, Any]:
        """
        Get work experience formatted for form filling.
        
        Returns dict with keys matching typical form field names:
        - job_title
        - company
        - location
        - currently_work_here (bool)
        - from_month
        - from_year
        - to_month
        - to_year
        - role_description
        """
        exp = self.get_work_experience(index)
        if not exp:
            return {}
        
        return {
            "job_title": exp.get("job_title", ""),
            "company": exp.get("company", ""),
            "location": exp.get("location", ""),
            "currently_work_here": exp.get("currently_work_here", False),
            "from_month": exp.get("from", {}).get("month", ""),
            "from_year": exp.get("from", {}).get("year", ""),
            "to_month": exp.get("to", {}).get("month", ""),
            "to_year": exp.get("to", {}).get("year", ""),
            "role_description": exp.get("role_description", "")
        }
    
    # ==================== EDUCATION ====================
    
    @property
    def education(self) -> List[Dict[str, Any]]:
        """Get all education entries."""
        return self.components.get("education", [])
    
    @property
    def education_count(self) -> int:
        """Get number of education entries."""
        return len(self.education)
    
    def get_education(self, index: int = 0) -> Optional[Dict[str, Any]]:
        """Get a specific education entry by index."""
        if 0 <= index < self.education_count:
            return self.education[index]
        return None
    
    def get_edu_school(self, index: int = 0) -> str:
        """Get school/university name for education at index."""
        edu = self.get_education(index)
        return edu.get("school_or_university", "") if edu else ""
    
    def get_edu_degree(self, index: int = 0) -> str:
        """Get degree for education at index."""
        edu = self.get_education(index)
        return edu.get("degree", "") if edu else ""
    
    def get_edu_field_of_study(self, index: int = 0) -> str:
        """Get field of study for education at index."""
        edu = self.get_education(index)
        return edu.get("field_of_study", "") if edu else ""
    
    def get_edu_degree_with_field(self, index: int = 0) -> str:
        """Get combined degree and field (e.g., 'Master's in Business Analytics')."""
        degree = self.get_edu_degree(index)
        field = self.get_edu_field_of_study(index)
        if degree and field:
            return f"{degree} in {field}"
        return degree or field
    
    def get_edu_from_month(self, index: int = 0) -> str:
        """Get start month for education at index."""
        edu = self.get_education(index)
        if edu:
            return edu.get("from", {}).get("month", "")
        return ""
    
    def get_edu_from_year(self, index: int = 0) -> str:
        """Get start year for education at index."""
        edu = self.get_education(index)
        if edu:
            return edu.get("from", {}).get("year", "")
        return ""
    
    def get_edu_to_month(self, index: int = 0) -> str:
        """Get end month for education at index."""
        edu = self.get_education(index)
        if edu:
            return edu.get("to", {}).get("month", "")
        return ""
    
    def get_edu_to_year(self, index: int = 0) -> str:
        """Get end year for education at index."""
        edu = self.get_education(index)
        if edu:
            return edu.get("to", {}).get("year", "")
        return ""
    
    def get_edu_gpa(self, index: int = 0) -> Optional[str]:
        """Get GPA for education at index."""
        edu = self.get_education(index)
        return edu.get("gpa") if edu else None
    
    def get_edu_form_data(self, index: int = 0) -> Dict[str, Any]:
        """
        Get education formatted for form filling.
        
        Returns dict with keys matching typical form field names:
        - school
        - degree
        - field_of_study
        - from_month
        - from_year
        - to_month
        - to_year
        - gpa
        """
        edu = self.get_education(index)
        if not edu:
            return {}
        
        return {
            "school": edu.get("school_or_university", ""),
            "degree": edu.get("degree", ""),
            "field_of_study": edu.get("field_of_study", ""),
            "degree_with_field": self.get_edu_degree_with_field(index),
            "from_month": edu.get("from", {}).get("month", ""),
            "from_year": edu.get("from", {}).get("year", ""),
            "to_month": edu.get("to", {}).get("month", ""),
            "to_year": edu.get("to", {}).get("year", ""),
            "gpa": edu.get("gpa")
        }
    
    # ==================== SKILLS ====================
    
    @property
    def skills(self) -> List[str]:
        """Get all skills."""
        return self.components.get("skills", [])
    
    @property
    def skills_string(self) -> str:
        """Get skills as comma-separated string."""
        return ", ".join(self.skills)
    
    def has_skill(self, skill: str, case_sensitive: bool = False) -> bool:
        """Check if a skill is present."""
        if case_sensitive:
            return skill in self.skills
        return skill.lower() in [s.lower() for s in self.skills]
    
    # ==================== ACCOMPLISHMENTS ====================
    
    @property
    def accomplishments(self) -> List[Dict[str, str]]:
        """Get all accomplishments."""
        return self.components.get("accomplishments", [])
    
    def get_accomplishment(self, index: int = 0) -> Optional[Dict[str, str]]:
        """Get a specific accomplishment by index."""
        if 0 <= index < len(self.accomplishments):
            return self.accomplishments[index]
        return None
    
    def get_accomplishments_text(self) -> str:
        """Get all accomplishments as formatted text."""
        lines = []
        for acc in self.accomplishments:
            company = acc.get("company", "")
            desc = acc.get("description", "")
            lines.append(f"• {company}: {desc}")
        return "\n".join(lines)
    
    # ==================== METADATA ====================
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get metadata about the resume."""
        return self.components.get("metadata", {})
    
    @property
    def total_years_experience(self) -> int:
        """Get total years of experience."""
        return self.metadata.get("total_years_experience", 0)


def load_resume_components(config: Dict = None, components_path: str = None) -> ResumeComponentsLoader:
    """
    Convenience function to load resume components.
    
    Args:
        config: User config dict (will look for resume_components_path)
        components_path: Direct path to components file (takes precedence)
    
    Returns:
        ResumeComponentsLoader instance
    """
    if components_path:
        return ResumeComponentsLoader(components_path=components_path)
    
    if config:
        return ResumeComponentsLoader(config=config)
    
    # Try loading from default config
    from .config import load_config
    config = load_config()
    return ResumeComponentsLoader(config=config)


# Convenience function for quick access
def get_resume_data(config: Dict = None) -> Dict[str, Any]:
    """
    Get all resume data as a dictionary.
    
    Returns dict with:
    - personal_info
    - professional_summary
    - work_experience (list)
    - education (list)
    - skills (list)
    - accomplishments (list)
    """
    loader = load_resume_components(config)
    return loader.components


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        loader = ResumeComponentsLoader(components_path=sys.argv[1])
    else:
        # Load from default config
        from config import load_config
        config = load_config()
        loader = load_resume_components(config)
    
    # Print summary
    print(f"Name: {loader.full_name}")
    print(f"Email: {loader.email}")
    print(f"Total Experience: {loader.total_years_experience} years")
    print(f"\nWork Experience ({loader.work_experience_count} positions):")
    for i in range(loader.work_experience_count):
        data = loader.get_work_exp_form_data(i)
        print(f"  {i+1}. {data['job_title']} at {data['company']} ({data['from_year']}-{data['to_year'] or 'Present'})")
    
    print(f"\nEducation ({loader.education_count} entries):")
    for i in range(loader.education_count):
        data = loader.get_edu_form_data(i)
        print(f"  {i+1}. {data['degree_with_field']} - {data['school']}")
    
    print(f"\nSkills: {loader.skills_string[:100]}...")

