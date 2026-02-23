"""
Auto-application system for job search pipeline.
"""
from .config import load_config, save_config, get_config, validate_config
from .job_board_detector import detect_job_board, get_job_board_info
from .application_tracker import ApplicationTracker

__all__ = [
    'load_config',
    'save_config',
    'get_config',
    'validate_config',
    'detect_job_board',
    'get_job_board_info',
    'ApplicationTracker'
]


