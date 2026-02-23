"""
JD Term Extractor
═════════════════
Enriches the Master Input Index by scanning actual job descriptions
from the aggregated corpus.

For each JD:
  • Extract terms using JDInsightExtractor (from Pipeline 5)
  • Match against existing index entries (exact + alias + lemma)
  • Add new terms not yet in the index with source='jd'
  • Update jd_frequency and last_seen for existing terms
  • Infer seniority band from the job title text

Usage:
    from job_extraction.jd_term_extractor import enrich_index_from_jds
    updated_index = enrich_index_from_jds(index, job_title)
"""

import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from paths import (
    ALIGNMENT_DIR,
    MASTER_INPUT_INDEX,
    UNIFIED_MASTER_CSV,
    master_aggregated_csv,
)
from job_extraction.jd_insights import JDInsightExtractor, CATEGORY_KEYWORDS
from job_extraction.input_deduplicator import InputDeduplicator, deduplicate_inputs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ═══════════════════════════════════════════════════════════════════════════
# Seniority inference from job titles
# ═══════════════════════════════════════════════════════════════════════════

SENIORITY_PATTERNS: Dict[str, re.Pattern] = {
    "entry": re.compile(
        r"\b(entry|junior|jr\.?|associate|intern|trainee|graduate)\b", re.IGNORECASE
    ),
    "mid": re.compile(
        r"\b(analyst|specialist|coordinator|individual contributor|mid[- ]level)\b",
        re.IGNORECASE,
    ),
    "senior": re.compile(
        r"\b(senior|sr\.?|lead|principal|staff|iii)\b", re.IGNORECASE
    ),
    "director": re.compile(
        r"\b(director|head of|group lead|practice lead)\b", re.IGNORECASE
    ),
    "vp": re.compile(
        r"\b(vp|vice president|svp|evp|vice-president)\b", re.IGNORECASE
    ),
    "c-suite": re.compile(
        r"\b(chief|cto|cmo|cdo|cfo|coo|c-suite|ceo|cro)\b", re.IGNORECASE
    ),
}


def infer_seniority(job_title: str) -> List[str]:
    """Infer seniority band(s) from a job title string."""
    if not job_title or pd.isna(job_title):
        return ["mid", "senior"]  # safe default

    bands = []
    title_lower = str(job_title).lower()
    for band, pattern in SENIORITY_PATTERNS.items():
        if pattern.search(title_lower):
            bands.append(band)

    return bands if bands else ["mid", "senior"]


# ═══════════════════════════════════════════════════════════════════════════
# Category → input type mapping
# ═══════════════════════════════════════════════════════════════════════════

CATEGORY_TO_TYPE: Dict[str, str] = {
    "technical_skill": "skill",
    "tools_platforms": "tool",
    "analytics_function": "function",
    "soft_skill": "soft_skill",
    "data_management": "skill",
    "domain_expertise": "domain",
    "methodology_approach": "methodology",
    "uncategorized": "concept",
}


# ═══════════════════════════════════════════════════════════════════════════
# Processed URL tracker
# ═══════════════════════════════════════════════════════════════════════════


def _tracker_path() -> Path:
    return ALIGNMENT_DIR / "jd_term_processed_urls.json"


def _load_processed_urls() -> Set[str]:
    tp = _tracker_path()
    if tp.exists():
        try:
            data = json.loads(tp.read_text(encoding="utf-8"))
            return set(data.get("urls", []))
        except Exception:
            pass
    return set()


def _save_processed_urls(urls: Set[str]) -> None:
    tp = _tracker_path()
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(
        json.dumps({"urls": sorted(urls)}, indent=2), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Index lookup helpers
# ═══════════════════════════════════════════════════════════════════════════


class IndexMatcher:
    """Efficiently match extracted terms against the existing index."""

    def __init__(self, inputs: List[Dict[str, Any]]):
        self.deduper = InputDeduplicator()
        # Build lookup tables
        self._by_canonical: Dict[str, int] = {}  # canonical_key → index position
        self._by_alias: Dict[str, int] = {}

        for idx, inp in enumerate(inputs):
            ckey = self.deduper.canonical_key(inp.get("input", ""))
            self._by_canonical[ckey] = idx
            for alias in inp.get("aliases", []):
                akey = self.deduper.canonical_key(alias)
                if akey not in self._by_alias:
                    self._by_alias[akey] = idx

    def find(self, term: str) -> Optional[int]:
        """Return the index position of a matching input, or None."""
        ckey = self.deduper.canonical_key(term)

        # Exact canonical match
        if ckey in self._by_canonical:
            return self._by_canonical[ckey]

        # Alias match
        if ckey in self._by_alias:
            return self._by_alias[ckey]

        # Abbreviation expansion
        expanded = self.deduper.expand_abbreviation(term)
        if expanded:
            ekey = self.deduper.canonical_key(expanded)
            if ekey in self._by_canonical:
                return self._by_canonical[ekey]
            if ekey in self._by_alias:
                return self._by_alias[ekey]

        return None


# ═══════════════════════════════════════════════════════════════════════════
# Core enrichment
# ═══════════════════════════════════════════════════════════════════════════


def enrich_index_from_jds(
    index: Dict[str, Any],
    job_title: str,
    csv_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan job descriptions and enrich the Master Input Index.

    Parameters
    ----------
    index : dict
        The current master input index (with 'metadata' and 'inputs').
    job_title : str
        The search title (used to locate the aggregated CSV).
    csv_path : str, optional
        Explicit path to a CSV file with a 'description' column.

    Returns
    -------
    dict  The updated index.
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
        logging.warning("No aggregated CSV found for JD enrichment.")
        return index

    df = pd.read_csv(source_csv)
    if df.empty or "description" not in df.columns:
        logging.warning("CSV empty or missing 'description' column.")
        return index

    # Filter to unprocessed URLs
    processed = _load_processed_urls()
    if "job_url" in df.columns:
        new_mask = ~df["job_url"].astype(str).isin(processed)
        new_df = df[new_mask]
    else:
        new_df = df

    if new_df.empty:
        logging.info("JD Term Extractor: no new jobs to process.")
        return index

    logging.info("JD Term Extractor: processing %d new job descriptions.", len(new_df))

    inputs = list(index.get("inputs", []))
    matcher = IndexMatcher(inputs)
    extractor = JDInsightExtractor()
    today = datetime.now().strftime("%Y-%m-%d")
    total_jds = len(new_df)

    # Count how many JDs mention each term (for frequency calculation)
    term_jd_counts: Counter = Counter()
    new_terms: List[Dict[str, Any]] = []

    for _, row in new_df.iterrows():
        desc = str(row.get("description", ""))
        if not desc or desc in ("-", "nan"):
            continue

        job_title_text = str(row.get("job_title", ""))
        seniority = infer_seniority(job_title_text)

        # Extract terms and ngrams
        terms = extractor.extract_terms(desc)
        ngrams = extractor.extract_ngrams(desc)
        all_phrases = set(terms + ngrams)

        # Filter to valuable phrases
        valuable = [p for p in all_phrases if extractor._is_valuable(p)]

        for phrase in valuable:
            term_jd_counts[phrase] += 1
            idx = matcher.find(phrase)

            if idx is not None:
                # Update existing input
                inp = inputs[idx]
                inp["last_seen"] = today
                # Update source
                if inp.get("source") == "research":
                    inp["source"] = "both"
                # Union seniority
                existing_sen = set(inp.get("seniority", []))
                inp["seniority"] = sorted(existing_sen | set(seniority))
            else:
                # New term — collect for batch addition
                category = extractor.classify(phrase)
                input_type = CATEGORY_TO_TYPE.get(category, "concept")
                new_terms.append({
                    "input": phrase,
                    "type": input_type,
                    "weight": 0.3,  # preliminary; updated after frequency calc
                    "seniority": seniority,
                    "source": "jd",
                    "aliases": [],
                    "first_seen": today,
                    "last_seen": today,
                })

    # De-duplicate new terms among themselves
    if new_terms:
        new_terms = deduplicate_inputs(new_terms)

        # Re-check against existing index after dedup (some may now match)
        truly_new = []
        for nt in new_terms:
            idx = matcher.find(nt["input"])
            if idx is None:
                truly_new.append(nt)
            else:
                # Merge into existing
                inp = inputs[idx]
                if inp.get("source") == "research":
                    inp["source"] = "both"
                existing_sen = set(inp.get("seniority", []))
                inp["seniority"] = sorted(existing_sen | set(nt.get("seniority", [])))
                inp["last_seen"] = today

        inputs.extend(truly_new)
        logging.info("Added %d new terms from JDs.", len(truly_new))

    # Update jd_frequency for all inputs
    for inp in inputs:
        canon = InputDeduplicator().canonical_key(inp.get("input", ""))
        # Check exact and alias matches in term_jd_counts
        freq = term_jd_counts.get(inp.get("input", "").lower(), 0)
        for alias in inp.get("aliases", []):
            freq = max(freq, term_jd_counts.get(alias.lower(), 0))

        if total_jds > 0 and freq > 0:
            new_freq = freq / total_jds
            # Blend with existing frequency if present
            old_freq = inp.get("jd_frequency", 0)
            if old_freq > 0:
                inp["jd_frequency"] = round((old_freq + new_freq) / 2, 4)
            else:
                inp["jd_frequency"] = round(new_freq, 4)

            # Adjust weight based on JD frequency (blend research weight with market signal)
            research_weight = inp.get("weight", 0.3)
            market_weight = min(new_freq * 2, 1.0)  # scale up, cap at 1.0
            inp["weight"] = round(
                (research_weight * 0.6 + market_weight * 0.4), 3
            )

    # Update processed URLs
    if "job_url" in new_df.columns:
        processed.update(new_df["job_url"].astype(str).tolist())
    _save_processed_urls(processed)

    # Save updated index
    index["inputs"] = inputs
    index["metadata"]["total_inputs"] = len(inputs)
    index["metadata"]["updated_at"] = datetime.now().isoformat()

    # Recount sources
    source_counts = {"research": 0, "jd": 0, "both": 0}
    for inp in inputs:
        src = inp.get("source", "research")
        if src in source_counts:
            source_counts[src] += 1
    index["metadata"]["sources"] = source_counts

    MASTER_INPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    MASTER_INPUT_INDEX.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logging.info(
        "JD Term Extractor: index updated → %d total inputs (%d from JDs).",
        len(inputs), source_counts.get("jd", 0) + source_counts.get("both", 0),
    )

    return index


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich the Master Input Index from job descriptions."
    )
    parser.add_argument("--job_title", required=True, help="Job title to process.")
    parser.add_argument("--csv_file", default=None, help="Explicit CSV path.")
    args = parser.parse_args()

    # Load existing index
    if MASTER_INPUT_INDEX.exists():
        index = json.loads(MASTER_INPUT_INDEX.read_text(encoding="utf-8"))
    else:
        logging.error("Master input index not found. Run input_index_generator first.")
        sys.exit(1)

    updated = enrich_index_from_jds(index, args.job_title, csv_path=args.csv_file)
    n = len(updated.get("inputs", []))
    print(f"\n  ✓ Index enriched: {n} total inputs\n")


if __name__ == "__main__":
    main()
