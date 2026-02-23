"""
Form fillers for different job board platforms.

Each form filler inherits from BaseFormFiller which provides:
- Personal info filling (name, email, phone, etc.)
- Work experience section filling (from resume components)
- Education section filling (from resume components)
- File upload utilities
- Dropdown/checkbox handling

Resume components are automatically loaded from the path specified in user_config.json.

Supported platforms:
- Greenhouse: GreenhouseFormFiller
- Workday: WorkdayFormFiller
- Generic: GenericFormFiller (fallback for unknown platforms)
"""
from .base import BaseFormFiller
from .greenhouse import GreenhouseFormFiller
from .workday import WorkdayFormFiller
from .generic import GenericFormFiller

__all__ = ['BaseFormFiller', 'GreenhouseFormFiller', 'WorkdayFormFiller', 'GenericFormFiller']


