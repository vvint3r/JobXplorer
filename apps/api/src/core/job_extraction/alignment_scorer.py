"""Alignment scorer — extracted from src/job_extraction/alignment_scorer.py.

Pure-function core: score_single_job() takes data, returns dict.
No file I/O — all persistence handled by the caller.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .input_deduplicator import InputDeduplicator
from .jd_term_extractor import IndexMatcher, infer_seniority

logger = logging.getLogger(__name__)

GRADE_THRESHOLDS: List[Tuple[float, str]] = [
    (0.90, "A+"),
    (0.85, "A"),
    (0.80, "A-"),
    (0.75, "B+"),
    (0.70, "B"),
    (0.65, "B-"),
    (0.55, "C+"),
    (0.45, "C"),
    (0.35, "C-"),
    (0.25, "D+"),
    (0.00, "D"),
]


def score_to_grade(score: float) -> str:
    """Convert a 0–1 alignment score to a letter grade."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "D"


class TextMatcher:
    """Check whether an input term (or its aliases) appears in text."""

    def __init__(self):
        self._dedup = InputDeduplicator()

    def matches(self, inp: Dict, text: str) -> bool:
        """Return True if the input term or any alias is found in the text."""
        text_lower = text.lower()
        term = inp.get("input", "")

        # Direct match
        if term.lower() in text_lower:
            return True

        # Lemmatized match
        lemma = self._dedup.lemmatise(term)
        if lemma in text_lower:
            return True

        # Alias match
        for alias in inp.get("aliases", []):
            if alias.lower() in text_lower:
                return True

        return False


def score_single_job(
    jd_text: str,
    job_title: str,
    inputs: List[Dict],
    resume_text: str,
    supplementary_terms: List[Dict],
    matcher: IndexMatcher,
    text_matcher: TextMatcher,
) -> Dict[str, Any]:
    """Score a single job against the user's resume and input index.

    Args:
        jd_text: Full job description text.
        job_title: Job title string.
        inputs: Master input index entries.
        resume_text: Full resume text (concatenated).
        supplementary_terms: Extra terms from user's supplementary config.
        matcher: IndexMatcher instance for the index.
        text_matcher: TextMatcher instance for resume matching.

    Returns:
        Dict with alignment_score, grade, matched/gap details.
        Empty dict if JD is empty.
    """
    if not jd_text or len(jd_text.strip()) < 50:
        return {}

    job_seniority = set(infer_seniority(job_title))

    # Build supplementary lookup
    supp_lookup: Dict[str, Dict] = {}
    for term in supplementary_terms:
        supp_lookup[term.get("term", "").lower()] = term

    # Find which inputs appear in the JD
    jd_inputs = []
    for inp in inputs:
        if text_matcher.matches(inp, jd_text):
            jd_inputs.append(inp)

    if not jd_inputs:
        return {
            "alignment_score": 0.0,
            "grade": "D",
            "inputs_found": 0,
            "inputs_matched": 0,
            "inputs_gap": 0,
            "matched_inputs": [],
            "supplementary_matches": [],
            "gaps": [],
            "seniority_fit": list(job_seniority),
        }

    total_weight = 0.0
    weighted_score = 0.0
    matched = []
    supplementary_matched = []
    gaps = []

    for inp in jd_inputs:
        weight = inp.get("weight", 0.5)
        term = inp.get("input", "")

        # Seniority overlap factor
        inp_seniority = set(inp.get("seniority", ["mid", "senior"]))
        seniority_overlap = len(job_seniority & inp_seniority) > 0
        seniority_factor = 1.0 if seniority_overlap else 0.8

        effective_weight = weight * seniority_factor
        total_weight += effective_weight

        # Check resume match
        if text_matcher.matches(inp, resume_text):
            weighted_score += effective_weight * 1.0
            matched.append({"input": term, "weight": weight, "source": "resume"})
        elif term.lower() in supp_lookup:
            # Supplementary term match
            supp = supp_lookup[term.lower()]
            proficiency = supp.get("proficiency", "intermediate")
            score_val = 0.7 if proficiency == "expert" else 0.5
            weighted_score += effective_weight * score_val
            supplementary_matched.append({
                "input": term,
                "weight": weight,
                "proficiency": proficiency,
            })
        else:
            weighted_score += 0.0
            gaps.append({"input": term, "weight": weight, "type": inp.get("type", "skill")})

    alignment_score = weighted_score / total_weight if total_weight > 0 else 0.0
    grade = score_to_grade(alignment_score)

    # Sort gaps by weight (highest first), limit to 20
    gaps.sort(key=lambda g: g["weight"], reverse=True)

    return {
        "alignment_score": round(alignment_score, 4),
        "grade": grade,
        "inputs_found": len(jd_inputs),
        "inputs_matched": len(matched),
        "inputs_gap": len(gaps),
        "matched_inputs": matched,
        "supplementary_matches": supplementary_matched,
        "gaps": gaps[:20],
        "seniority_fit": list(job_seniority),
    }
