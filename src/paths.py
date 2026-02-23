"""
Central path configuration for the JobXplore project.

All data, config, and output paths are derived from PROJECT_ROOT.
Import from here instead of hard-coding paths in individual modules.
"""

import os
from pathlib import Path

# Project root = parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Config (user-provided inputs) ──────────────────────────────────────────
CONFIG_DIR          = PROJECT_ROOT / "config"
LINKEDIN_COOKIES    = CONFIG_DIR / "linkedin_cookies.txt"
LINKEDIN_URLS_FILE  = CONFIG_DIR / "jobs_linkedin_urls.txt"
USER_CONFIG_JSON    = CONFIG_DIR / "user_config.json"
USER_CONFIG_EXAMPLE = CONFIG_DIR / "user_config.example.json"
TEST_SINGLE_JOB_CSV = CONFIG_DIR / "test_single_job.csv"
RESUMES_DIR         = CONFIG_DIR / "resumes"
BASE_RESUME_DIR     = RESUMES_DIR / "base_resume"

# ── Data (all generated outputs) ───────────────────────────────────────────
DATA_DIR            = PROJECT_ROOT / "data"
SEARCH_RESULTS_DIR  = DATA_DIR / "search_results"
JOB_DETAILS_DIR     = DATA_DIR / "job_details"
AGGREGATED_DIR      = DATA_DIR / "aggregated"
METRICS_DIR         = DATA_DIR / "metrics"
APPLICATION_LOGS_DIR = DATA_DIR / "application_logs"
DEBUG_DIR           = DATA_DIR / "debug"
ANALYSIS_DIR        = DATA_DIR / "analysis"
INSIGHTS_DIR        = DATA_DIR / "insights"
VARIABLES_EXTRACTED_DIR = DATA_DIR / "variables_extracted"
OPTIMIZED_RESUMES_DIR   = DATA_DIR / "optimized_resumes"
ALIGNMENT_DIR           = DATA_DIR / "alignment"
ALIGNMENT_SCORES_DIR    = ALIGNMENT_DIR / "scores"
MASTER_INPUT_INDEX      = ALIGNMENT_DIR / "master_input_index.json"

# ── Config (alignment inputs) ─────────────────────────────────────────────
MASTER_JOB_TITLE_JSON   = CONFIG_DIR / "master_job_title.json"
SUPPLEMENTARY_TERMS     = CONFIG_DIR / "supplementary_terms.json"

# ── Tracking files ─────────────────────────────────────────────────────────
JOBS_RAN_CSV        = SEARCH_RESULTS_DIR / "jobs_ran.csv"
APPLICATIONS_CSV    = APPLICATION_LOGS_DIR / "applications.csv"
UNIFIED_MASTER_CSV  = AGGREGATED_DIR / "unified_master.csv"


# ── Helper to get per-title subdirectories ─────────────────────────────────
def search_results_for(job_title_clean: str) -> Path:
    """data/search_results/<title>/"""
    return SEARCH_RESULTS_DIR / job_title_clean

def job_details_for(job_title_clean: str) -> Path:
    """data/job_details/<title>/"""
    return JOB_DETAILS_DIR / job_title_clean

def aggregated_for(job_title_clean: str) -> Path:
    """data/aggregated/<title>/"""
    return AGGREGATED_DIR / job_title_clean

def insights_for(job_title_clean: str) -> Path:
    """data/insights/<title>/"""
    return INSIGHTS_DIR / job_title_clean

def master_aggregated_csv(job_title_clean: str) -> Path:
    """data/aggregated/<title>/<title>_master_aggregated.csv"""
    return aggregated_for(job_title_clean) / f"{job_title_clean}_master_aggregated.csv"

def alignment_scores_for(job_title_clean: str) -> Path:
    """data/alignment/scores/<title>/"""
    return ALIGNMENT_SCORES_DIR / job_title_clean
