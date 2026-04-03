"""Input index generator — adapted for SaaS (no file I/O).

Seeds the Master Input Index from OpenAI research for a given job title.
Produces a dict with 'metadata' and 'inputs' keys, ready for DB storage.

Usage:
    from core.job_extraction.input_index_generator import generate_index
    index = generate_index(master_job_title, openai_api_key)
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .input_deduplicator import deduplicate_inputs

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_SENIORITY = ["mid", "senior", "director"]

BATCH_PROMPTS = [
    {
        "category": "Tools & Platforms",
        "instruction": (
            "Generate a comprehensive list of TOOLS and PLATFORMS (software, "
            "applications, services, APIs) that appear in real job descriptions "
            "for this role and related roles at all seniority levels."
        ),
    },
    {
        "category": "Technical Skills & Functions",
        "instruction": (
            "Generate a comprehensive list of TECHNICAL SKILLS and ANALYTICS "
            "FUNCTIONS (hard skills, quantitative methods, programming languages, "
            "data techniques) that appear in real job descriptions for this role."
        ),
    },
    {
        "category": "Methodologies & Concepts",
        "instruction": (
            "Generate a comprehensive list of METHODOLOGIES, FRAMEWORKS, and "
            "CONCEPTS (statistical methods, business frameworks, analytical "
            "approaches, process methodologies) for this role."
        ),
    },
    {
        "category": "Domain Expertise & Soft Skills",
        "instruction": (
            "Generate a comprehensive list of DOMAIN EXPERTISE areas (industry "
            "knowledge, business functions, verticals) and SOFT SKILLS "
            "(leadership, communication, collaboration) for this role."
        ),
    },
]

SYSTEM_PROMPT = (
    "You are a job market analyst specialising in marketing analytics and data roles. "
    "You produce structured, accurate JSON based on real-world job market data."
)

BATCH_USER_TEMPLATE = """For the role "{master_job_title}", {instruction}

For EACH item return a JSON object with these exact keys:
- "input": the canonical term (lowercase, singular where appropriate)
- "type": one of ["skill", "tool", "function", "methodology", "domain", "soft_skill", "certification", "concept"]
- "weight": float 0.0-1.0 indicating how commonly this appears in job descriptions for this role
- "seniority": array of levels where this is relevant, from ["entry", "mid", "senior", "director", "vp", "c-suite"]
- "aliases": array of alternative phrasings, plurals, abbreviations, close synonyms

Return a JSON array of 60-100 items. Return ONLY valid JSON, no markdown fences or commentary."""


def _call_openai_batch(
    client, master_job_title: str, batch: dict, retries: int = 3
) -> List[Dict[str, Any]]:
    """Call OpenAI for a single batch. Returns list of input dicts."""
    prompt = BATCH_USER_TEMPLATE.format(
        master_job_title=master_job_title,
        instruction=batch["instruction"],
    )

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)

            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = next(
                    (v for v in data.values() if isinstance(v, list)), []
                )
            else:
                items = []

            validated = []
            for item in items:
                if not isinstance(item, dict) or "input" not in item:
                    continue
                validated.append({
                    "input": str(item.get("input", "")).strip(),
                    "type": str(item.get("type", "skill")).strip(),
                    "weight": float(item.get("weight", 0.5)),
                    "seniority": list(item.get("seniority", DEFAULT_SENIORITY)),
                    "source": "research",
                    "aliases": list(item.get("aliases", [])),
                })

            logger.info(
                "OpenAI batch '%s': %d items returned.",
                batch["category"], len(validated),
            )
            return validated

        except json.JSONDecodeError as exc:
            logger.warning(
                "OpenAI batch '%s' attempt %d: JSON parse error: %s",
                batch["category"], attempt + 1, exc,
            )
        except Exception as exc:
            logger.warning(
                "OpenAI batch '%s' attempt %d failed: %s",
                batch["category"], attempt + 1, exc,
            )
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                logger.info("Retrying in %ds...", wait)
                time.sleep(wait)

    logger.error("OpenAI batch '%s': all retries exhausted.", batch["category"])
    return []


def generate_openai_seed(
    master_job_title: str,
    openai_api_key: str,
) -> List[Dict[str, Any]]:
    """Generate the full seed from OpenAI across all batches.

    Parameters
    ----------
    master_job_title : str
        The canonical target role.
    openai_api_key : str
        The user's decrypted OpenAI API key.

    Returns
    -------
    list[dict]  Raw input items before dedup.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed — cannot generate index")
        return []

    client = OpenAI(api_key=openai_api_key)

    all_inputs: List[Dict[str, Any]] = []
    for batch in BATCH_PROMPTS:
        items = _call_openai_batch(client, master_job_title, batch)
        all_inputs.extend(items)
        if items:
            time.sleep(1)

    logger.info(
        "OpenAI seed: %d total items across %d batches.",
        len(all_inputs), len(BATCH_PROMPTS),
    )
    return all_inputs


def build_metadata(
    master_job_title: str, inputs: List[Dict[str, Any]], version: int = 1
) -> Dict[str, Any]:
    """Build the metadata block for the index."""
    source_counts = {"research": 0, "jd": 0, "both": 0}
    for inp in inputs:
        src = inp.get("source", "research")
        if src in source_counts:
            source_counts[src] += 1
        else:
            source_counts["research"] += 1

    now = datetime.now(timezone.utc).isoformat()
    return {
        "master_job_title": master_job_title,
        "version": version,
        "created_at": now,
        "updated_at": now,
        "total_inputs": len(inputs),
        "sources": source_counts,
    }


def generate_index(
    master_job_title: str,
    openai_api_key: str,
    existing_version: int = 0,
) -> Dict[str, Any]:
    """Generate a full input index for a job title using OpenAI.

    Parameters
    ----------
    master_job_title : str
        The target role title.
    openai_api_key : str
        Decrypted OpenAI API key.
    existing_version : int
        Current version number (new index gets version + 1).

    Returns
    -------
    dict  Full index with 'metadata' and 'inputs' keys, ready for DB storage.
    """
    logger.info("Generating master input index for: %s", master_job_title)

    all_inputs = generate_openai_seed(master_job_title, openai_api_key)

    if not all_inputs:
        logger.warning("No inputs generated — OpenAI may be unreachable or key is invalid")
        return {
            "metadata": build_metadata(master_job_title, [], existing_version + 1),
            "inputs": [],
        }

    logger.info("Pre-dedup total: %d items", len(all_inputs))
    deduped = deduplicate_inputs(all_inputs)
    logger.info("Post-dedup: %d items", len(deduped))

    version = existing_version + 1
    return {
        "metadata": build_metadata(master_job_title, deduped, version),
        "inputs": deduped,
    }
