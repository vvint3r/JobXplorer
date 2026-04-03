"""Job board detector — extracted from src/auto_application/job_board_detector.py.

Pure regex-based detection. No external dependencies.
"""

import re
from typing import Dict

JOB_BOARD_PATTERNS: Dict[str, list] = {
    "greenhouse": [r"greenhouse\.io", r"boards\.greenhouse\.io", r"job-boards\.greenhouse\.io"],
    "workday": [r"workday\.com", r"myworkdayjobs\.com", r"wd\d+\.myworkdayjobs"],
    "lever": [r"lever\.co", r"jobs\.lever\.co"],
    "smartrecruiters": [r"smartrecruiters\.com", r"jobs\.smartrecruiters\.com"],
    "icims": [r"icims\.com", r"careers-.*\.icims\.com"],
    "taleo": [r"taleo\.net", r"oracle\.com/.*taleo"],
    "jobvite": [r"jobvite\.com", r"jobs\.jobvite\.com"],
    "bamboohr": [r"bamboohr\.com"],
    "linkedin": [r"linkedin\.com/jobs"],
    "indeed": [r"indeed\.com"],
    "glassdoor": [r"glassdoor\.com"],
}

_COMPILED_PATTERNS: Dict[str, list] = {
    board: [re.compile(p, re.I) for p in patterns]
    for board, patterns in JOB_BOARD_PATTERNS.items()
}

BOARD_FEATURES: Dict[str, Dict[str, bool]] = {
    "greenhouse": {
        "auto_fill_supported": True,
        "file_upload_supported": True,
        "custom_questions": True,
        "requires_manual_review": False,
    },
    "workday": {
        "auto_fill_supported": True,
        "file_upload_supported": True,
        "custom_questions": True,
        "requires_manual_review": True,
    },
    "lever": {
        "auto_fill_supported": True,
        "file_upload_supported": True,
        "custom_questions": True,
        "requires_manual_review": False,
    },
    "generic": {
        "auto_fill_supported": False,
        "file_upload_supported": False,
        "custom_questions": True,
        "requires_manual_review": True,
    },
}


def detect_job_board(url: str) -> str:
    """Detect the ATS platform from a URL. Returns board type or 'generic'."""
    if not url:
        return "generic"

    url_lower = url.lower()
    for board, patterns in _COMPILED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(url_lower):
                return board

    return "generic"


def get_job_board_info(url: str) -> Dict:
    """Get board type and feature support for a URL."""
    board_type = detect_job_board(url)
    features = BOARD_FEATURES.get(board_type, BOARD_FEATURES["generic"])

    return {
        "type": board_type,
        "features": features,
    }
