"""
Input Index Generator
═════════════════════
Seeds the Master Input Index from three sources:

  1. OpenAI research — batched prompts for the master job title
  2. Topic index bootstrap — parses master_topic_index_enriched.md
     and master_topic_index.md in chunks
  3. Deduplication pass — merges overlapping inputs

Produces / updates: data/alignment/master_input_index.json

Usage:
    from job_extraction.input_index_generator import generate_or_load_index
    index = generate_or_load_index(master_job_title)
"""

import json
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paths import (
    MASTER_INPUT_INDEX,
    ALIGNMENT_DIR,
    PROJECT_ROOT,
)
from job_extraction.input_deduplicator import deduplicate_inputs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DEFAULT_MODEL = "gpt-4o-mini"

# ═══════════════════════════════════════════════════════════════════════════
# L1 domain → input type mapping (for topic index parsing)
# ═══════════════════════════════════════════════════════════════════════════

L1_TYPE_MAP: Dict[str, str] = {
    "foundations & core concepts": "concept",
    "statistical methods & probability": "skill",
    "mathematical foundations": "skill",
    "experimentation & causal inference": "methodology",
    "measurement & attribution": "methodology",
    "customer analytics & insights": "function",
    "predictive analytics & machine learning": "skill",
    "data infrastructure & engineering": "tool",
    "channel-specific analytics": "function",
    "tools & technology stack": "tool",
    "tools & technology ecosystem": "tool",
    "analytics strategy & governance": "concept",
    "data management & governance": "domain",
    "marketing analytics manager competencies": "function",
    "team leadership & career development": "soft_skill",
    "industry applications & specializations": "domain",
    "product & marketing context": "domain",
    "experimentation lifecycle & process": "methodology",
    "sql & query fundamentals": "skill",
    "analytics strategy": "concept",
    "analytics management": "soft_skill",
}

# Fallback for L2 headings when L1 is ambiguous
L2_TYPE_OVERRIDES: Dict[str, str] = {
    "probability & distributions": "skill",
    "statistical inference": "methodology",
    "regression analysis": "skill",
    "time series analysis": "skill",
    "bayesian statistics": "methodology",
    "a/b testing": "methodology",
    "experiment design": "methodology",
    "causal inference": "methodology",
    "linear algebra": "skill",
    "calculus": "skill",
    "optimization": "methodology",
    "data visualization": "tool",
    "business intelligence": "tool",
    "cloud & infrastructure": "tool",
    "programming & development": "skill",
    "leadership": "soft_skill",
    "stakeholder": "soft_skill",
    "management": "soft_skill",
    "communication": "soft_skill",
    "project management": "methodology",
}

# Default seniority for research-generated inputs (OpenAI will override)
DEFAULT_SENIORITY = ["mid", "senior", "director"]


# ═══════════════════════════════════════════════════════════════════════════
# OpenAI Seed Generation
# ═══════════════════════════════════════════════════════════════════════════


def _get_openai_client():
    """Lazy-load OpenAI client. Returns None if no API key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logging.warning("OPENAI_API_KEY not set – skipping OpenAI seed generation.")
        return None
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        logging.warning("openai package not installed – skipping OpenAI seed.")
        return None


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

SYSTEM_PROMPT = """You are a job market analyst specialising in marketing analytics and data roles.
You produce structured, accurate JSON based on real-world job market data."""

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

            # Handle both {"items": [...]} and [...] responses
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Find the first list value
                items = next(
                    (v for v in data.values() if isinstance(v, list)), []
                )
            else:
                items = []

            # Validate and normalise
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

            logging.info(
                "OpenAI batch '%s': %d items returned.",
                batch["category"], len(validated),
            )
            return validated

        except json.JSONDecodeError as exc:
            logging.warning(
                "OpenAI batch '%s' attempt %d: JSON parse error: %s",
                batch["category"], attempt + 1, exc,
            )
        except Exception as exc:
            logging.warning(
                "OpenAI batch '%s' attempt %d failed: %s",
                batch["category"], attempt + 1, exc,
            )
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                logging.info("Retrying in %ds...", wait)
                time.sleep(wait)

    logging.error("OpenAI batch '%s': all retries exhausted.", batch["category"])
    return []


def generate_openai_seed(master_job_title: str) -> List[Dict[str, Any]]:
    """Generate the full seed from OpenAI across all batches."""
    client = _get_openai_client()
    if not client:
        return []

    all_inputs: List[Dict[str, Any]] = []
    for batch in BATCH_PROMPTS:
        items = _call_openai_batch(client, master_job_title, batch)
        all_inputs.extend(items)
        # Brief pause between batches to be polite to rate limits
        if items:
            time.sleep(1)

    logging.info("OpenAI seed: %d total items across %d batches.",
                 len(all_inputs), len(BATCH_PROMPTS))
    return all_inputs


# ═══════════════════════════════════════════════════════════════════════════
# Topic Index Parsing
# ═══════════════════════════════════════════════════════════════════════════

# Regex patterns for the enriched index (with aliases)
RE_L1 = re.compile(r"^#\s+L1:\s*(.+)", re.IGNORECASE)
RE_L2 = re.compile(r"^##\s+L2:\s*(.+?)(?:\s*→\s*\*\[(.+?)\]\*)?", re.IGNORECASE)
RE_L3 = re.compile(r"^###\s+L3:\s*(.+?)(?:\s*→\s*\*\[(.+?)\]\*)?", re.IGNORECASE)
RE_L4_BOLD = re.compile(
    r"^\s*-\s*\*\*L4:\s*(.+?)\*\*\s*(?:→\s*\*\[(.+?)\]\*)?(?:\s*[-–—]\s*(.+))?",
    re.IGNORECASE,
)
RE_L5_BOLD = re.compile(
    r"^\s*-\s*\*\*L5:\s*(.+?)\*\*\s*(?:→\s*\*\[(.+?)\]\*)?",
    re.IGNORECASE,
)
RE_L5_PLAIN = re.compile(
    r"^\s*-\s*L5:\s*(.+?)(?:\s*→\s*\*\[(.+?)\]\*)?$",
    re.IGNORECASE,
)
RE_L4_PLAIN = re.compile(
    r"^\s*-\s*L4:\s*(.+?)(?:\s*→\s*\*\[(.+?)\]\*)?(?:\s*[-–—]\s*(.+))?$",
    re.IGNORECASE,
)
# Base index L4/L5 (no aliases, uses dash descriptions)
RE_L4_BASE = re.compile(
    r"^\s*-\s*\*\*L4:\s*(.+?)\*\*\s*(?:[-–—]\s*(.+))?$",
    re.IGNORECASE,
)
RE_L5_BASE = re.compile(
    r"^\s*-\s*L5:\s*(.+?)$",
    re.IGNORECASE,
)
RE_L6_BASE = re.compile(
    r"^\s*-\s*L6:\s*(.+?)$",
    re.IGNORECASE,
)


def _resolve_type(l1: str, l2: str, l3: str) -> str:
    """Determine the input type from hierarchy context."""
    # Check L2 overrides first
    l2_lower = l2.lower().strip()
    for key, typ in L2_TYPE_OVERRIDES.items():
        if key in l2_lower:
            return typ

    # Check L1 mapping
    l1_lower = l1.lower().strip()
    for key, typ in L1_TYPE_MAP.items():
        if key in l1_lower:
            return typ

    return "concept"  # safe default


def _parse_aliases(alias_str: Optional[str]) -> List[str]:
    """Parse comma-separated alias string from the enriched index."""
    if not alias_str:
        return []
    # Split on comma, clean each
    aliases = [a.strip() for a in alias_str.split(",")]
    return [a for a in aliases if a and len(a) > 1]


def parse_topic_index_enriched(filepath: Path) -> List[Dict[str, Any]]:
    """
    Parse master_topic_index_enriched.md and extract inputs with aliases.

    Processes the file in chunks, tracking L1/L2/L3 hierarchy state.
    """
    if not filepath.exists():
        logging.warning("Enriched topic index not found: %s", filepath)
        return []

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    inputs: List[Dict[str, Any]] = []
    current_l1 = ""
    current_l2 = ""
    current_l3 = ""
    today = datetime.now().strftime("%Y-%m-%d")

    for line in lines:
        # Track hierarchy
        m = RE_L1.match(line)
        if m:
            current_l1 = m.group(1).strip()
            continue

        m = RE_L2.match(line)
        if m:
            current_l2 = m.group(1).strip()
            # L2 can have aliases too
            aliases = _parse_aliases(m.group(2) if m.lastindex >= 2 else None)
            if current_l2 and len(current_l2) > 2:
                inputs.append({
                    "input": current_l2,
                    "type": _resolve_type(current_l1, current_l2, ""),
                    "weight": 0.3,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": aliases,
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

        m = RE_L3.match(line)
        if m:
            current_l3 = m.group(1).strip()
            aliases = _parse_aliases(m.group(2) if m.lastindex >= 2 else None)
            if current_l3 and len(current_l3) > 2:
                inputs.append({
                    "input": current_l3,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.35,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": aliases,
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

        # L4 (bold or plain)
        m = RE_L4_BOLD.match(line) or RE_L4_PLAIN.match(line)
        if m:
            name = m.group(1).strip()
            aliases = _parse_aliases(m.group(2) if m.lastindex >= 2 else None)
            if name and len(name) > 2:
                inputs.append({
                    "input": name,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.4,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": aliases,
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

        # L5 (bold or plain)
        m = RE_L5_BOLD.match(line) or RE_L5_PLAIN.match(line)
        if m:
            name = m.group(1).strip()
            aliases = _parse_aliases(m.group(2) if m.lastindex >= 2 else None)
            if name and len(name) > 2:
                inputs.append({
                    "input": name,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.45,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": aliases,
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

    logging.info(
        "Parsed enriched topic index: %d items from %d lines.",
        len(inputs), len(lines),
    )
    return inputs


def parse_topic_index_base(filepath: Path) -> List[Dict[str, Any]]:
    """
    Parse master_topic_index.md (no aliases) and extract inputs.

    Larger file — processes in full since it's just regex line-by-line.
    """
    if not filepath.exists():
        logging.warning("Base topic index not found: %s", filepath)
        return []

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    inputs: List[Dict[str, Any]] = []
    current_l1 = ""
    current_l2 = ""
    current_l3 = ""
    today = datetime.now().strftime("%Y-%m-%d")

    for line in lines:
        m = RE_L1.match(line)
        if m:
            current_l1 = m.group(1).strip()
            continue

        # L2: ## L2: ...
        if line.strip().startswith("## L2:"):
            current_l2 = line.strip().replace("## L2:", "").strip()
            continue

        # L3: ### L3: ...
        if line.strip().startswith("### L3:"):
            current_l3 = line.strip().replace("### L3:", "").strip()
            if current_l3 and len(current_l3) > 2:
                inputs.append({
                    "input": current_l3,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.35,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": [],
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

        # L4
        m = RE_L4_BASE.match(line)
        if m:
            name = m.group(1).strip()
            if name and len(name) > 2:
                inputs.append({
                    "input": name,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.4,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": [],
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

        # L5
        m = RE_L5_BASE.match(line)
        if m:
            name = m.group(1).strip()
            if name and len(name) > 2:
                inputs.append({
                    "input": name,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.45,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": [],
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

        # L6
        m = RE_L6_BASE.match(line)
        if m:
            name = m.group(1).strip()
            if name and len(name) > 2:
                inputs.append({
                    "input": name,
                    "type": _resolve_type(current_l1, current_l2, current_l3),
                    "weight": 0.4,
                    "seniority": DEFAULT_SENIORITY,
                    "source": "research",
                    "aliases": [],
                    "first_seen": today,
                    "last_seen": today,
                })
            continue

    logging.info(
        "Parsed base topic index: %d items from %d lines.",
        len(inputs), len(lines),
    )
    return inputs


# ═══════════════════════════════════════════════════════════════════════════
# Index Assembly
# ═══════════════════════════════════════════════════════════════════════════


def _build_metadata(
    master_job_title: str, inputs: List[Dict[str, Any]], version: int = 1
) -> Dict[str, Any]:
    """Build the metadata block for the index JSON."""
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


def _save_index(
    master_job_title: str,
    inputs: List[Dict[str, Any]],
    version: int = 1,
) -> Dict[str, Any]:
    """Save the master input index to disk."""
    ALIGNMENT_DIR.mkdir(parents=True, exist_ok=True)

    index = {
        "metadata": _build_metadata(master_job_title, inputs, version),
        "inputs": inputs,
    }

    MASTER_INPUT_INDEX.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logging.info(
        "Saved master input index: %d inputs → %s",
        len(inputs), MASTER_INPUT_INDEX,
    )
    return index


def load_index() -> Optional[Dict[str, Any]]:
    """Load the existing master input index, or None."""
    if MASTER_INPUT_INDEX.exists():
        try:
            return json.loads(MASTER_INPUT_INDEX.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Could not load index: %s", exc)
    return None


def generate_or_load_index(
    master_job_title: str,
    refresh: bool = False,
) -> Dict[str, Any]:
    """
    Main entry point: load existing index or generate a new one.

    Parameters
    ----------
    master_job_title : str
        The canonical target role.
    refresh : bool
        If True, regenerate from scratch even if an index exists.

    Returns
    -------
    dict  The full index JSON structure with 'metadata' and 'inputs'.
    """
    # Try loading existing
    if not refresh:
        existing = load_index()
        if existing and existing.get("inputs"):
            title_match = (
                existing.get("metadata", {}).get("master_job_title", "").lower()
                == master_job_title.lower()
            )
            if title_match:
                logging.info(
                    "Loaded existing index: %d inputs.",
                    len(existing["inputs"]),
                )
                return existing
            else:
                logging.info(
                    "Index exists but for different title ('%s' vs '%s'). Regenerating.",
                    existing.get("metadata", {}).get("master_job_title"),
                    master_job_title,
                )

    logging.info("Generating master input index for: %s", master_job_title)

    all_inputs: List[Dict[str, Any]] = []

    # Source 1: OpenAI research
    logging.info("── Source 1: OpenAI research seed ──")
    openai_items = generate_openai_seed(master_job_title)
    all_inputs.extend(openai_items)

    # Source 2: Enriched topic index (has aliases)
    logging.info("── Source 2: Enriched topic index ──")
    enriched_path = PROJECT_ROOT / "docs" / "master_topic_index_enriched.md"
    enriched_items = parse_topic_index_enriched(enriched_path)
    all_inputs.extend(enriched_items)

    # Source 3: Base topic index (more items, no aliases)
    logging.info("── Source 3: Base topic index ──")
    base_path = PROJECT_ROOT / "docs" / "master_topic_index.md"
    base_items = parse_topic_index_base(base_path)
    all_inputs.extend(base_items)

    logging.info(
        "Pre-dedup total: %d items (OpenAI: %d, enriched: %d, base: %d)",
        len(all_inputs), len(openai_items), len(enriched_items), len(base_items),
    )

    # Deduplicate
    deduped = deduplicate_inputs(all_inputs)

    # Determine version
    existing = load_index()
    version = (existing.get("metadata", {}).get("version", 0) + 1) if existing else 1

    # Save
    index = _save_index(master_job_title, deduped, version)
    return index


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate or refresh the Master Input Index."
    )
    parser.add_argument(
        "--title",
        help="Master job title. If omitted, reads from config/master_job_title.json.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force regeneration even if an index exists.",
    )
    args = parser.parse_args()

    if args.title:
        title = args.title
    else:
        from job_extraction.master_job_title import ensure_master_job_title
        title = ensure_master_job_title()

    index = generate_or_load_index(title, refresh=args.refresh)
    n = len(index.get("inputs", []))
    print(f"\n  ✓ Master input index: {n} inputs → {MASTER_INPUT_INDEX}\n")


if __name__ == "__main__":
    main()
