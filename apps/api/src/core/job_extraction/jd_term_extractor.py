"""JD Term Extractor — extracted from src/job_extraction/jd_term_extractor.py.

Pure-function core: IndexMatcher class and infer_seniority().
No file I/O — all persistence handled by the caller.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .input_deduplicator import InputDeduplicator, ABBREVIATIONS

logger = logging.getLogger(__name__)

SENIORITY_PATTERNS: Dict[str, re.Pattern] = {
    "entry": re.compile(r"\b(entry[\s-]?level|junior|jr\.?|associate|intern|trainee|graduate)\b", re.I),
    "mid": re.compile(r"\b(analyst|specialist|coordinator|mid[\s-]?level)\b", re.I),
    "senior": re.compile(r"\b(senior|sr\.?|lead|principal|staff|iii)\b", re.I),
    "director": re.compile(r"\b(director|head\s+of|group\s+lead)\b", re.I),
    "vp": re.compile(r"\b(vp|vice\s+president|svp|evp)\b", re.I),
    "c-suite": re.compile(r"\b(chief|cto|cmo|cdo|cfo|coo|ceo|cro)\b", re.I),
}

CATEGORY_TO_TYPE: Dict[str, str] = {
    "technical_skill": "skill",
    "tools_platforms": "tool",
    "analytics_function": "function",
    "soft_skill": "soft_skill",
    "data_management": "skill",
    "domain_expertise": "domain",
    "methodology_approach": "methodology",
}


def infer_seniority(job_title: str) -> List[str]:
    """Infer seniority bands from a job title. Returns list of matching bands."""
    if not job_title:
        return ["mid", "senior"]

    matches = []
    for band, pattern in SENIORITY_PATTERNS.items():
        if pattern.search(job_title):
            matches.append(band)

    return matches if matches else ["mid", "senior"]


class IndexMatcher:
    """Efficient lookup of terms in a master input index."""

    def __init__(self, inputs: List[Dict[str, Any]]):
        self._deduplicator = InputDeduplicator()
        self._by_canonical: Dict[str, int] = {}
        self._by_alias: Dict[str, int] = {}

        for idx, inp in enumerate(inputs):
            text = inp.get("input", "")
            key = self._deduplicator.canonical_key(text)
            self._by_canonical[key] = idx

            for alias in inp.get("aliases", []):
                alias_key = self._deduplicator.canonical_key(alias)
                self._by_alias[alias_key] = idx

    def find(self, term: str) -> Optional[int]:
        """Find a term in the index. Returns index position or None."""
        key = self._deduplicator.canonical_key(term)

        # Direct match
        if key in self._by_canonical:
            return self._by_canonical[key]

        # Alias match
        if key in self._by_alias:
            return self._by_alias[key]

        # Abbreviation expansion
        expanded = self._deduplicator.expand_abbreviation(term)
        if expanded:
            exp_key = self._deduplicator.canonical_key(expanded)
            if exp_key in self._by_canonical:
                return self._by_canonical[exp_key]
            if exp_key in self._by_alias:
                return self._by_alias[exp_key]

        return None


def enrich_index_from_jds(
    index_inputs: List[Dict],
    jd_texts: List[Dict[str, str]],
) -> List[Dict]:
    """Enrich an input index using JD texts.

    Args:
        index_inputs: Current index entries (list of input dicts).
        jd_texts: List of dicts with 'job_title' and 'description' keys.

    Returns:
        Updated index entries list.
    """
    from .jd_insights import JDInsightExtractor

    extractor = JDInsightExtractor()
    matcher = IndexMatcher(index_inputs)
    new_terms: Dict[str, Dict] = {}

    for jd in jd_texts:
        desc = jd.get("description", "")
        title = jd.get("job_title", "")
        if not desc or len(desc) < 50:
            continue

        seniority = infer_seniority(title)

        # Extract terms and phrases
        terms = extractor.extract_terms(desc)
        ngrams = extractor.extract_ngrams(desc)

        for item in terms + ngrams:
            idx = matcher.find(item)
            if idx is not None:
                # Update existing entry
                entry = index_inputs[idx]
                entry["last_seen"] = jd.get("date", "")
                entry["jd_frequency"] = entry.get("jd_frequency", 0) + 1
                existing_sen = set(entry.get("seniority", []))
                entry["seniority"] = sorted(existing_sen | set(seniority))
                if entry.get("source") and entry["source"] != "jd":
                    entry["source"] = "both"
            else:
                # Collect new term
                category = extractor.classify(item)
                if category and item not in new_terms:
                    new_terms[item] = {
                        "input": item,
                        "type": CATEGORY_TO_TYPE.get(category, "concept"),
                        "weight": 0.3,
                        "source": "jd",
                        "aliases": [],
                        "seniority": seniority,
                        "jd_frequency": 1,
                    }
                elif item in new_terms:
                    new_terms[item]["jd_frequency"] += 1

    # Append new terms
    index_inputs.extend(new_terms.values())
    return index_inputs
