"""
JD-Based Resume Optimizer
═════════════════════════
For each job in the master aggregated CSV, produce a tailored version
of the base resume that emphasises the skills, terms, and experience
most relevant to *that* job description.

Two modes:
  1. **LLM (OpenAI)** – rewrites summary + bullet ordering + skill
     emphasis using GPT-4o-mini.  Requires OPENAI_API_KEY.
  2. **Keyword-match fallback** – scores existing resume bullets
     against JD keywords and reorders + tags them.

Output per job:
    job_search/auto_application/resumes/optimized_resumes/
        <company>_<title>_<date>.json

The file follows the same schema as the base resume components JSON
so it can be loaded by ResumeComponentsLoader for form-filling.

Also appends an ``optimized_resume_path`` column to the master
aggregated CSV so the auto-apply pipeline knows which resume to use.
"""

import argparse
import json
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from paths import master_aggregated_csv, OPTIMIZED_RESUMES_DIR, USER_CONFIG_JSON, UNIFIED_MASTER_CSV

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DEFAULT_MODEL = "gpt-4o-mini"

OPTIMIZED_DIR = OPTIMIZED_RESUMES_DIR


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _sanitize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_json(path: str, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _extract_jd_keywords(description: str) -> List[str]:
    """Lightweight keyword extraction – no external NLP libs required."""
    stop = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can",
        "had", "her", "was", "one", "our", "out", "has", "have", "with",
        "this", "that", "will", "your", "from", "they", "been", "some",
        "than", "its", "who", "about", "which", "when", "what", "their",
        "would", "make", "like", "just", "over", "such", "into", "more",
        "other", "also", "must", "join", "work", "team", "role", "able",
        "ability", "position", "company", "including", "include",
        "experience", "required", "requirements", "skills", "skill",
        "preferred", "qualifications", "responsibilities",
    }
    words = re.findall(r"[a-z][a-z\-/]+", description.lower())
    filtered = [w for w in words if w not in stop and len(w) > 2]
    return [w for w, _ in Counter(filtered).most_common(60)]


def _score_bullet(bullet: str, keywords: Set[str]) -> int:
    """Count how many JD keywords appear in a bullet point."""
    bl = bullet.lower()
    return sum(1 for kw in keywords if kw in bl)


# ═══════════════════════════════════════════════════════════════════════════
# LLM-based optimization
# ═══════════════════════════════════════════════════════════════════════════


def _optimise_with_llm(
    base_resume: dict,
    job_title: str,
    company: str,
    description: str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Use OpenAI to produce an optimised resume JSON."""
    from openai import OpenAI  # lazy

    client = OpenAI()

    system_prompt = (
        "You are a professional resume optimiser. Given a base resume (JSON) and "
        "a job description, return an OPTIMISED resume JSON that:\n"
        "1. Rewrites the professional_summary to mirror the language and priorities of this specific role.\n"
        "2. Reorders the skills list so the most JD-relevant skills appear first.\n"
        "3. For each work_experience entry, reorder bullet points (in role_description) so the most "
        "JD-relevant accomplishments appear first. You may lightly rephrase bullets to incorporate "
        "keywords from the JD, but do NOT fabricate new accomplishments.\n"
        "4. Add a new top-level key 'jd_alignment_notes' with a short list of the top 5-10 JD "
        "requirements you optimised for.\n"
        "Return ONLY valid JSON matching the original schema (plus jd_alignment_notes). "
        "Preserve all personal_info, education, accomplishments, and metadata fields exactly."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "target_job_title": job_title,
                    "target_company": company,
                    "job_description": description[:6000],  # trim to stay within limits
                    "base_resume": base_resume,
                },
                ensure_ascii=False,
            ),
        },
    ]

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    return json.loads(resp.choices[0].message.content)


# ═══════════════════════════════════════════════════════════════════════════
# Keyword-match fallback
# ═══════════════════════════════════════════════════════════════════════════


def _optimise_with_keywords(
    base_resume: dict,
    job_title: str,
    company: str,
    description: str,
) -> dict:
    """Score + reorder resume content using keyword overlap with the JD."""
    optimised = json.loads(json.dumps(base_resume))  # deep copy
    kw_list = _extract_jd_keywords(description)
    kw_set = set(kw_list)

    # --- Reorder skills ---
    base_skills: List[str] = optimised.get("skills", [])
    scored_skills = sorted(
        base_skills,
        key=lambda s: _score_bullet(s, kw_set),
        reverse=True,
    )
    optimised["skills"] = scored_skills

    # --- Reorder bullets within each work experience entry ---
    for exp in optimised.get("work_experience", []):
        role_desc: str = exp.get("role_description", "")
        if not role_desc:
            continue
        bullets = [b.strip() for b in role_desc.split("\n") if b.strip()]
        bullets.sort(key=lambda b: _score_bullet(b, kw_set), reverse=True)
        exp["role_description"] = "\n".join(bullets)

    # --- Append tailored professional summary addendum ---
    top_kws = kw_list[:15]
    original_summary = optimised.get("professional_summary", "")
    matched_kws = [kw for kw in top_kws if kw in original_summary.lower()]
    unmatched_kws = [kw for kw in top_kws if kw not in original_summary.lower()]

    optimised["jd_alignment_notes"] = {
        "target_job_title": job_title,
        "target_company": company,
        "top_jd_keywords": top_kws,
        "keywords_already_in_summary": matched_kws,
        "keywords_to_emphasise": unmatched_kws,
        "method": "keyword_match_fallback",
    }

    return optimised


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def optimise_resume_for_job(
    base_resume: dict,
    job_title: str,
    company: str,
    description: str,
    use_llm: bool = True,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Return an optimised resume dict for a single job posting."""
    if use_llm:
        try:
            return _optimise_with_llm(base_resume, job_title, company, description, model)
        except Exception as exc:
            logging.warning("LLM optimisation failed (%s); falling back to keyword match.", exc)

    return _optimise_with_keywords(base_resume, job_title, company, description)


def run_resume_optimisation(
    job_title: str,
    base_path: str = None,
    resume_components_path: Optional[str] = None,
    csv_path: Optional[str] = None,
) -> int:
    """
    Batch-optimise resumes for every job with a description in a master CSV.

    Resolution order for the source CSV:
      1. Explicit *csv_path* argument (e.g. the unified master).
      2. Per-title master aggregated CSV derived from *job_title*.
      3. Unified master CSV as a last-resort fallback.

    Returns the number of new optimised resumes generated this run.
    """
    jt_clean = job_title.lower().replace(" ", "_")

    # ── locate master CSV ─────────────────────────────────────────────────
    if csv_path and os.path.exists(csv_path):
        master_csv_path = csv_path
    else:
        master_csv_path = str(master_aggregated_csv(jt_clean))
        if not os.path.exists(master_csv_path):
            # Fallback to unified master
            master_csv_path = str(UNIFIED_MASTER_CSV)

    if not os.path.exists(master_csv_path):
        logging.warning("No master CSV found (tried per-title and unified): %s", master_csv_path)
        return 0

    df = pd.read_csv(master_csv_path)
    if df.empty:
        logging.warning("Master aggregated CSV is empty.")
        return 0

    # ── resolve base resume ───────────────────────────────────────────────
    if not resume_components_path:
        # attempt to load from user_config.json
        config_path = USER_CONFIG_JSON
        if config_path.exists():
            cfg = _load_json(str(config_path))
            resume_components_path = cfg.get("application_info", {}).get("resume_components_path")

    if not resume_components_path or not os.path.exists(resume_components_path):
        logging.error(
            "Base resume components JSON not found. Provide --resume_components_path "
            "or set application_info.resume_components_path in user_config.json."
        )
        return 0

    base_resume = _load_json(resume_components_path)
    logging.info("Loaded base resume from %s", resume_components_path)

    # ── determine LLM availability ────────────────────────────────────────
    use_llm = bool(os.environ.get("OPENAI_API_KEY"))
    if use_llm:
        logging.info("OPENAI_API_KEY detected – will use LLM optimisation.")
    else:
        logging.info("No OPENAI_API_KEY – using keyword-match fallback.")

    # ── tracker: skip already-optimised jobs ──────────────────────────────
    OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    tracker_path = OPTIMIZED_DIR / f"{jt_clean}_optimised_tracker.json"
    tracker_data = {}
    if tracker_path.exists():
        try:
            tracker_data = _load_json(str(tracker_path))
        except Exception:
            tracker_data = {}
    optimised_urls: Set[str] = set(tracker_data.get("urls", []))

    # ── filter to jobs that have descriptions & apply URLs ────────────────
    needs_desc = df["description"].notna() & (df["description"].astype(str).str.strip() != "")

    # Also filter to jobs with usable apply URLs (these are the ones going to auto-apply)
    has_apply = pd.Series([True] * len(df), index=df.index)
    if "application_url" in df.columns:
        has_apply = (
            df["application_url"].notna()
            & (df["application_url"].astype(str).str.strip() != "")
            & (df["application_url"].astype(str) != "Not Available")
        )
    has_job_url = df["job_url"].notna() & (df["job_url"].astype(str).str.strip() != "")

    eligible = df[needs_desc & (has_apply | has_job_url)].copy()
    logging.info("Resume Optimiser: %d eligible jobs (with description + URL).", len(eligible))

    # skip already done
    eligible = eligible[~eligible["job_url"].astype(str).isin(optimised_urls)]
    if eligible.empty:
        logging.info("Resume Optimiser: all eligible jobs already optimised – nothing to do.")
        return 0

    logging.info("Resume Optimiser: %d new jobs to optimise.", len(eligible))

    # ── optimise ──────────────────────────────────────────────────────────
    count = 0
    url_to_path: Dict[str, str] = dict(tracker_data.get("url_to_path", {}))

    for _, row in eligible.iterrows():
        company = str(row.get("company", row.get("company_title", "unknown"))).strip()
        title = str(row.get("job_title", "unknown")).strip()
        description = str(row["description"])
        job_url = str(row["job_url"])

        if not description.strip():
            continue

        try:
            opt = optimise_resume_for_job(
                base_resume=base_resume,
                job_title=title,
                company=company,
                description=description,
                use_llm=use_llm,
            )

            # add targeting metadata
            opt["_optimised_for"] = {
                "job_title": title,
                "company": company,
                "job_url": job_url,
                "optimised_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "method": "llm" if use_llm and "jd_alignment_notes" in opt and opt["jd_alignment_notes"].get("method") != "keyword_match_fallback" else "keyword_match",
            }

            fname = f"{_sanitize(company)}_{_sanitize(title)}_{datetime.now().strftime('%Y%m%d')}.json"
            out_path = OPTIMIZED_DIR / fname
            _save_json(str(out_path), opt)

            optimised_urls.add(job_url)
            url_to_path[job_url] = str(out_path)
            count += 1
            logging.info("  [%d] Optimised: %s @ %s → %s", count, title, company, out_path.name)

        except Exception as exc:
            logging.error("  Failed to optimise for %s @ %s: %s", title, company, exc)

    # ── persist tracker ───────────────────────────────────────────────────
    _save_json(str(tracker_path), {
        "urls": sorted(optimised_urls),
        "url_to_path": url_to_path,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    # ── update master CSV with optimized_resume_path column ───────────────
    try:
        master_df = pd.read_csv(master_csv_path)
        if "optimized_resume_path" not in master_df.columns:
            master_df["optimized_resume_path"] = ""

        for url, path in url_to_path.items():
            mask = master_df["job_url"].astype(str) == url
            master_df.loc[mask, "optimized_resume_path"] = path

        master_df.to_csv(master_csv_path, index=False)
        logging.info("Updated master CSV with optimized_resume_path column.")
    except Exception as exc:
        logging.warning("Could not update master CSV: %s", exc)

    logging.info("Resume Optimiser: %d new resumes generated.", count)
    return count


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Batch-optimise resumes for job postings.")
    parser.add_argument("--job_title", required=True, help="Job title to process.")
    parser.add_argument(
        "--csv_file",
        default=None,
        help="Path to input CSV (default: per-title master, falls back to unified master).",
    )
    parser.add_argument(
        "--resume_components_path",
        default=None,
        help="Path to base resume components JSON (defaults to user_config.json value).",
    )
    args = parser.parse_args()

    n = run_resume_optimisation(
        args.job_title,
        resume_components_path=args.resume_components_path,
        csv_path=args.csv_file,
    )
    logging.info("Done – %d resumes optimised.", n)


if __name__ == "__main__":
    main()
