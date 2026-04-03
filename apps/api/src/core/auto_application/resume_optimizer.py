"""Resume optimizer — adapted for SaaS (no file I/O).

Two modes:
  1. LLM (OpenAI) — rewrites summary + bullet ordering + skill emphasis.
  2. Keyword-match fallback — scores existing bullets against JD keywords.

Usage:
    from core.auto_application.resume_optimizer import optimise_resume_for_job
    result = optimise_resume_for_job(base_resume, job_title, company, description)
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"


def _extract_jd_keywords(description: str) -> List[str]:
    """Lightweight keyword extraction — no external NLP libs required."""
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


def _optimise_with_llm(
    base_resume: dict,
    job_title: str,
    company: str,
    description: str,
    openai_api_key: str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Use OpenAI to produce an optimised resume JSON."""
    from openai import OpenAI

    client = OpenAI(api_key=openai_api_key)

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
                    "job_description": description[:6000],
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

    # Reorder skills
    base_skills: List[str] = optimised.get("skills", [])
    scored_skills = sorted(
        base_skills,
        key=lambda s: _score_bullet(s, kw_set),
        reverse=True,
    )
    optimised["skills"] = scored_skills

    # Reorder bullets within each work experience entry
    for exp in optimised.get("work_experience", []):
        role_desc: str = exp.get("role_description", "")
        if not role_desc:
            continue
        bullets = [b.strip() for b in role_desc.split("\n") if b.strip()]
        bullets.sort(key=lambda b: _score_bullet(b, kw_set), reverse=True)
        exp["role_description"] = "\n".join(bullets)

    # Alignment notes
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
        "method": "keyword_match",
    }

    return optimised


def optimise_resume_for_job(
    base_resume: dict,
    job_title: str,
    company: str,
    description: str,
    openai_api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Return an optimised resume dict for a single job posting.

    Parameters
    ----------
    base_resume : dict
        The user's parsed resume components JSON.
    job_title : str
        Target job title.
    company : str
        Target company name.
    description : str
        Full job description text.
    openai_api_key : str | None
        If provided, uses LLM optimization. Falls back to keyword match.
    model : str
        OpenAI model to use (default: gpt-4o-mini).

    Returns
    -------
    dict  Optimised resume JSON with 'jd_alignment_notes' and '_optimised_for' keys.
    """
    method = "keyword_match"

    if openai_api_key:
        try:
            result = _optimise_with_llm(
                base_resume, job_title, company, description, openai_api_key, model
            )
            method = "llm"
        except Exception as exc:
            logger.warning("LLM optimisation failed (%s); falling back to keyword match.", exc)
            result = _optimise_with_keywords(base_resume, job_title, company, description)
    else:
        result = _optimise_with_keywords(base_resume, job_title, company, description)

    result["_optimised_for"] = {
        "job_title": job_title,
        "company": company,
        "optimised_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
    }

    return result
