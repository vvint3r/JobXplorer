"""
Alignment Scorer
════════════════
Pipeline 5.5 — Scores each job description against the user's resume
and supplementary terms, using the Master Input Index as the bridge.

Produces:
  • Per-job alignment score (0–1) + letter grade
  • Matched inputs (from resume and supplementary terms)
  • Gap analysis (missing high-weight inputs)
  • Per-title CSV + JSON reports
  • Columns appended to the master aggregated CSV

Usage:
    from job_extraction.alignment_scorer import score_all_jobs
    score_all_jobs(index, job_title)
"""

import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from paths import (
    ALIGNMENT_SCORES_DIR,
    BASE_RESUME_DIR,
    MASTER_INPUT_INDEX,
    SUPPLEMENTARY_TERMS,
    UNIFIED_MASTER_CSV,
    USER_CONFIG_JSON,
    alignment_scores_for,
    master_aggregated_csv,
)
from job_extraction.jd_term_extractor import IndexMatcher, infer_seniority
from job_extraction.input_deduplicator import InputDeduplicator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ═══════════════════════════════════════════════════════════════════════════
# Grade mapping
# ═══════════════════════════════════════════════════════════════════════════

GRADE_THRESHOLDS = [
    (0.90, "A+"),
    (0.85, "A"),
    (0.80, "A-"),
    (0.75, "B+"),
    (0.70, "B"),
    (0.65, "B-"),
    (0.60, "C+"),
    (0.55, "C"),
    (0.50, "C-"),
    (0.00, "D"),
]


def score_to_grade(score: float) -> str:
    """Convert a 0–1 alignment score to a letter grade."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "D"


# ═══════════════════════════════════════════════════════════════════════════
# Resume text extraction
# ═══════════════════════════════════════════════════════════════════════════


def _load_resume_text() -> str:
    """Load resume text from the components JSON for matching."""
    # Try user_config for path first
    components_path = None

    if USER_CONFIG_JSON.exists():
        try:
            cfg = json.loads(USER_CONFIG_JSON.read_text(encoding="utf-8"))
            cp = cfg.get("application_info", {}).get("resume_components_path", "")
            if cp and os.path.exists(cp):
                components_path = cp
        except Exception:
            pass

    # Fallback: scan base_resume dir for *_components.json
    if not components_path:
        for f in BASE_RESUME_DIR.glob("*_components.json"):
            components_path = str(f)
            break
        for f in BASE_RESUME_DIR.glob("*.json"):
            components_path = str(f)
            break

    if not components_path or not os.path.exists(components_path):
        logging.warning("No resume components JSON found.")
        return ""

    try:
        data = json.loads(Path(components_path).read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Could not load resume JSON: %s", exc)
        return ""

    # Concatenate all text fields
    parts: List[str] = []

    # Professional summary
    if "professional_summary" in data:
        parts.append(str(data["professional_summary"]))

    # Skills
    skills = data.get("skills", {})
    if isinstance(skills, dict):
        for category, items in skills.items():
            parts.append(str(category))
            if isinstance(items, list):
                parts.extend(str(i) for i in items)
            else:
                parts.append(str(items))
    elif isinstance(skills, list):
        parts.extend(str(s) for s in skills)

    # Work experience
    for exp in data.get("work_experience", []):
        if isinstance(exp, dict):
            parts.append(str(exp.get("job_title", "")))
            parts.append(str(exp.get("role_description", "")))
        else:
            parts.append(str(exp))

    # Education
    for edu in data.get("education", []):
        if isinstance(edu, dict):
            parts.append(str(edu.get("degree", "")))
            parts.append(str(edu.get("field_of_study", "")))
            parts.append(str(edu.get("description", "")))
        else:
            parts.append(str(edu))

    # Accomplishments / certifications
    for key in ("accomplishments", "certifications", "awards"):
        items = data.get(key, [])
        if isinstance(items, list):
            parts.extend(str(i) for i in items)

    return " ".join(parts).lower()


# ═══════════════════════════════════════════════════════════════════════════
# Supplementary terms
# ═══════════════════════════════════════════════════════════════════════════


def _load_supplementary_terms() -> List[Dict[str, Any]]:
    """Load user's supplementary terms from config."""
    if not SUPPLEMENTARY_TERMS.exists():
        return []

    try:
        data = json.loads(SUPPLEMENTARY_TERMS.read_text(encoding="utf-8"))
        return data.get("terms", [])
    except Exception as exc:
        logging.warning("Could not load supplementary terms: %s", exc)
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Term matching in text
# ═══════════════════════════════════════════════════════════════════════════


class TextMatcher:
    """Check whether an input (or its aliases) appears in a body of text."""

    def __init__(self):
        self.deduper = InputDeduplicator()

    def matches(self, inp: Dict[str, Any], text: str) -> bool:
        """Return True if the input or any alias is found in the text."""
        text_lower = text.lower()

        # Check main input
        term = inp.get("input", "").lower().strip()
        if term and term in text_lower:
            return True

        # Check lemmatised form
        lemma = self.deduper.lemmatise(term)
        if lemma and lemma in text_lower:
            return True

        # Check aliases
        for alias in inp.get("aliases", []):
            al = alias.lower().strip()
            if al and al in text_lower:
                return True

        return False


# ═══════════════════════════════════════════════════════════════════════════
# Core scoring engine
# ═══════════════════════════════════════════════════════════════════════════


def score_single_job(
    jd_text: str,
    job_title: str,
    inputs: List[Dict[str, Any]],
    resume_text: str,
    supplementary: List[Dict[str, Any]],
    matcher: IndexMatcher,
    text_matcher: TextMatcher,
) -> Dict[str, Any]:
    """
    Score a single job description against the resume + supplementary terms.

    Returns a detailed score dict.
    """
    if not jd_text or jd_text in ("-", "nan"):
        return {"alignment_score": None, "alignment_grade": None, "error": "empty_jd"}

    jd_lower = jd_text.lower()
    job_seniority = infer_seniority(job_title)

    # Build supplementary term lookup
    supp_lookup: Dict[str, Dict[str, Any]] = {}
    for st in supplementary:
        key = st.get("term", "").lower().strip()
        if key:
            supp_lookup[key] = st

    # Find which index inputs appear in this JD
    jd_inputs: List[Dict[str, Any]] = []
    for inp in inputs:
        if text_matcher.matches(inp, jd_text):
            jd_inputs.append(inp)

    if not jd_inputs:
        return {
            "alignment_score": 0.0,
            "alignment_grade": "D",
            "inputs_found": 0,
            "inputs_matched": 0,
            "inputs_gap": 0,
            "matched_inputs": [],
            "supplementary_matches": [],
            "gaps": [],
            "seniority_fit": job_seniority,
        }

    # Score each JD input against resume
    matched_inputs = []
    supplementary_matches = []
    gaps = []

    total_weighted = 0.0
    matched_weighted = 0.0

    for inp in jd_inputs:
        weight = inp.get("weight", 0.5)
        inp_seniority = set(inp.get("seniority", []))

        # Seniority fit penalty
        seniority_overlap = bool(set(job_seniority) & inp_seniority)
        seniority_factor = 1.0 if seniority_overlap or not inp_seniority else 0.8

        effective_weight = weight * seniority_factor
        total_weighted += effective_weight

        # Check resume match
        if text_matcher.matches(inp, resume_text):
            match_score = 1.0
            matched_inputs.append({
                "input": inp.get("input"),
                "type": inp.get("type"),
                "weight": weight,
                "match": "resume",
            })
        else:
            # Check supplementary terms
            supp_match = None
            term_lower = inp.get("input", "").lower()
            if term_lower in supp_lookup:
                supp_match = supp_lookup[term_lower]
            else:
                # Check aliases against supplementary
                for alias in inp.get("aliases", []):
                    al = alias.lower()
                    if al in supp_lookup:
                        supp_match = supp_lookup[al]
                        break

            if supp_match:
                proficiency = supp_match.get("proficiency", "intermediate").lower()
                if proficiency in ("expert", "advanced"):
                    match_score = 0.7
                else:
                    match_score = 0.5
                supplementary_matches.append({
                    "input": inp.get("input"),
                    "type": inp.get("type"),
                    "weight": weight,
                    "match": "supplementary",
                    "proficiency": proficiency,
                })
            else:
                match_score = 0.0
                gaps.append({
                    "input": inp.get("input"),
                    "type": inp.get("type"),
                    "weight": weight,
                    "seniority": inp.get("seniority", []),
                })

        matched_weighted += effective_weight * match_score

    # Compute score
    alignment_score = round(matched_weighted / total_weighted, 4) if total_weighted > 0 else 0.0

    # Sort gaps by weight descending
    gaps.sort(key=lambda x: x.get("weight", 0), reverse=True)

    return {
        "alignment_score": alignment_score,
        "alignment_grade": score_to_grade(alignment_score),
        "inputs_found": len(jd_inputs),
        "inputs_matched": len(matched_inputs) + len(supplementary_matches),
        "inputs_gap": len(gaps),
        "matched_inputs": matched_inputs,
        "supplementary_matches": supplementary_matches,
        "gaps": gaps[:20],  # top 20 gaps
        "seniority_fit": job_seniority,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Batch scoring
# ═══════════════════════════════════════════════════════════════════════════


def score_all_jobs(
    index: Dict[str, Any],
    job_title: str,
    csv_path: Optional[str] = None,
) -> int:
    """
    Score all jobs for a given title and produce reports.

    Parameters
    ----------
    index : dict
        Master input index.
    job_title : str
        The search title.
    csv_path : str, optional
        Explicit CSV path.

    Returns
    -------
    int  Number of jobs scored.
    """
    jt_clean = job_title.lower().replace(" ", "_")

    # Locate CSV
    if csv_path and os.path.exists(csv_path):
        source_csv = csv_path
    else:
        source_csv = str(master_aggregated_csv(jt_clean))
        if not os.path.exists(source_csv):
            source_csv = str(UNIFIED_MASTER_CSV)

    if not os.path.exists(source_csv):
        logging.warning("No aggregated CSV found for scoring.")
        return 0

    df = pd.read_csv(source_csv)
    if df.empty:
        logging.warning("Aggregated CSV is empty.")
        return 0

    inputs = index.get("inputs", [])
    if not inputs:
        logging.warning("Master input index is empty — nothing to score against.")
        return 0

    # Load resume + supplementary terms
    resume_text = _load_resume_text()
    if not resume_text:
        logging.warning(
            "Could not load resume text. Scoring will show all inputs as gaps."
        )

    supplementary = _load_supplementary_terms()
    logging.info(
        "Scoring %d jobs against %d index inputs, %d supplementary terms.",
        len(df), len(inputs), len(supplementary),
    )

    # Prepare matchers
    idx_matcher = IndexMatcher(inputs)
    text_matcher = TextMatcher()

    # Score each job
    results: List[Dict[str, Any]] = []
    scores: List[Optional[float]] = []
    grades: List[Optional[str]] = []
    top_gaps_col: List[str] = []

    for _, row in df.iterrows():
        jd = str(row.get("description", ""))
        jt = str(row.get("job_title", ""))
        company = str(row.get("company_title", row.get("company", "")))
        job_url = str(row.get("job_url", ""))

        result = score_single_job(
            jd_text=jd,
            job_title=jt,
            inputs=inputs,
            resume_text=resume_text,
            supplementary=supplementary,
            matcher=idx_matcher,
            text_matcher=text_matcher,
        )

        result["job_url"] = job_url
        result["job_title"] = jt
        result["company"] = company
        results.append(result)

        scores.append(result.get("alignment_score"))
        grades.append(result.get("alignment_grade"))

        # Top gaps as pipe-separated string for CSV column
        gap_terms = [g.get("input", "") for g in result.get("gaps", [])[:5]]
        top_gaps_col.append(" | ".join(gap_terms))

    # ── Save outputs ──────────────────────────────────────────────────────

    scores_dir = alignment_scores_for(jt_clean)
    scores_dir.mkdir(parents=True, exist_ok=True)

    # 1. Detailed JSON
    detail_path = scores_dir / f"{jt_clean}_alignment_detail.json"
    detail_json = {
        "metadata": {
            "job_title": job_title,
            "scored_at": datetime.now().isoformat(),
            "total_jobs": len(results),
            "index_inputs": len(inputs),
            "resume_loaded": bool(resume_text),
            "supplementary_terms": len(supplementary),
        },
        "scores": results,
    }
    detail_path.write_text(
        json.dumps(detail_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 2. Score CSV
    score_df = pd.DataFrame([
        {
            "job_url": r.get("job_url"),
            "job_title": r.get("job_title"),
            "company": r.get("company"),
            "alignment_score": r.get("alignment_score"),
            "alignment_grade": r.get("alignment_grade"),
            "inputs_found": r.get("inputs_found"),
            "inputs_matched": r.get("inputs_matched"),
            "inputs_gap": r.get("inputs_gap"),
            "top_gaps": " | ".join(
                g.get("input", "") for g in r.get("gaps", [])[:5]
            ),
        }
        for r in results
    ])
    score_csv_path = scores_dir / f"{jt_clean}_alignment_scores.csv"
    score_df.to_csv(score_csv_path, index=False)

    # 3. Gap analysis CSV (term × frequency across all scored jobs)
    all_gaps: Dict[str, Dict[str, Any]] = {}
    for r in results:
        for g in r.get("gaps", []):
            term = g.get("input", "")
            if term not in all_gaps:
                all_gaps[term] = {
                    "input": term,
                    "type": g.get("type", ""),
                    "weight": g.get("weight", 0),
                    "gap_count": 0,
                }
            all_gaps[term]["gap_count"] += 1

    gap_df = pd.DataFrame(list(all_gaps.values()))
    if not gap_df.empty:
        gap_df = gap_df.sort_values("gap_count", ascending=False)
    gap_csv_path = scores_dir / f"{jt_clean}_gap_analysis.csv"
    gap_df.to_csv(gap_csv_path, index=False)

    # 4. Append columns to master aggregated CSV
    try:
        master_df = pd.read_csv(source_csv)
        master_df["alignment_score"] = scores
        master_df["alignment_grade"] = grades
        master_df["top_gaps"] = top_gaps_col
        master_df.to_csv(source_csv, index=False)
        logging.info("Appended alignment columns to %s", source_csv)
    except Exception as exc:
        logging.warning("Could not update master CSV: %s", exc)

    # Summary stats
    valid_scores = [s for s in scores if s is not None]
    avg = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    logging.info(
        "Alignment scoring complete: %d jobs scored, avg score %.2f",
        len(valid_scores), avg,
    )
    logging.info("Reports saved to: %s", scores_dir)

    return len(valid_scores)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Score job descriptions against resume alignment."
    )
    parser.add_argument("--job_title", required=True, help="Job title to score.")
    parser.add_argument("--csv_file", default=None, help="Explicit CSV path.")
    args = parser.parse_args()

    # Load index
    if MASTER_INPUT_INDEX.exists():
        index = json.loads(MASTER_INPUT_INDEX.read_text(encoding="utf-8"))
    else:
        logging.error("Master input index not found. Run input_index_generator first.")
        sys.exit(1)

    n = score_all_jobs(index, args.job_title, csv_path=args.csv_file)
    print(f"\n  ✓ Scored {n} jobs\n")


if __name__ == "__main__":
    main()
