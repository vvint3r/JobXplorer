"""
Detect the type of job board/ATS platform from a URL.
"""
import re
import logging
from urllib.parse import urlparse

# Known job board patterns
JOB_BOARD_PATTERNS = {
    'greenhouse': [
        r'greenhouse\.io',
        r'boards\.greenhouse\.io',
        r'job-boards\.greenhouse\.io'
    ],
    'workday': [
        r'workday\.com',
        r'myworkdayjobs\.com'
    ],
    'lever': [
        r'lever\.co',
        r'jobs\.lever\.co'
    ],
    'smartrecruiters': [
        r'smartrecruiters\.com'
    ],
    'icims': [
        r'icims\.com'
    ],
    'taleo': [
        r'taleo\.net',
        r'taleo\.com'
    ],
    'jobvite': [
        r'jobvite\.com'
    ],
    'bamboohr': [
        r'bamboohr\.com'
    ],
    'linkedin': [
        r'linkedin\.com/jobs'
    ],
    'indeed': [
        r'indeed\.com'
    ],
    'glassdoor': [
        r'glassdoor\.com'
    ],
    'generic': []  # Fallback for unknown platforms
}

def detect_job_board(url):
    """
    Detect the job board/ATS platform from a URL.
    
    Args:
        url (str): The job posting URL
        
    Returns:
        str: The detected job board type (e.g., 'greenhouse', 'workday', etc.)
    """
    if not url:
        return 'generic'
    
    url_lower = url.lower()
    
    # Check each job board pattern
    for board_type, patterns in JOB_BOARD_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                logging.info(f"Detected job board type: {board_type} for URL: {url[:50]}...")
                return board_type
    
    # If no pattern matches, return generic
    logging.warning(f"Could not detect job board type for URL: {url[:50]}... Defaulting to generic")
    return 'generic'

def get_job_board_info(url):
    """
    Get additional information about the job board.
    
    Args:
        url (str): The job posting URL
        
    Returns:
        dict: Information about the job board including type and supported features
    """
    board_type = detect_job_board(url)
    
    # Feature support matrix
    features = {
        'greenhouse': {
            'auto_fill_supported': True,
            'file_upload_supported': True,
            'custom_questions': True,
            'requires_manual_review': False
        },
        'workday': {
            'auto_fill_supported': True,
            'file_upload_supported': True,
            'custom_questions': True,
            'requires_manual_review': True  # Often has complex forms
        },
        'lever': {
            'auto_fill_supported': True,
            'file_upload_supported': True,
            'custom_questions': True,
            'requires_manual_review': False
        },
        'smartrecruiters': {
            'auto_fill_supported': True,
            'file_upload_supported': True,
            'custom_questions': True,
            'requires_manual_review': False
        },
        'linkedin': {
            'auto_fill_supported': True,
            'file_upload_supported': True,
            'custom_questions': False,
            'requires_manual_review': False
        },
        'generic': {
            'auto_fill_supported': True,  # Will attempt generic form filling
            'file_upload_supported': True,
            'custom_questions': True,
            'requires_manual_review': True  # Unknown forms may need review
        }
    }
    
    return {
        'type': board_type,
        'features': features.get(board_type, features['generic'])
    }


