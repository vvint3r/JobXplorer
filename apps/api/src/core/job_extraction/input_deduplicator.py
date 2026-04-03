"""Input deduplicator — extracted from src/job_extraction/input_deduplicator.py.

Pure-function core: no file I/O. Takes lists of input dicts, returns deduplicated lists.
"""

import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set

import nltk
from nltk.stem import WordNetLemmatizer

logger = logging.getLogger(__name__)

try:
    nltk.data.find("corpora/wordnet")
except LookupError:
    nltk.download("wordnet", quiet=True)

ABBREVIATIONS: Dict[str, List[str]] = {
    "sql": ["structured query language"],
    "ml": ["machine learning"],
    "ai": ["artificial intelligence"],
    "nlp": ["natural language processing"],
    "crm": ["customer relationship management"],
    "etl": ["extract transform load"],
    "erp": ["enterprise resource planning"],
    "bi": ["business intelligence"],
    "kpi": ["key performance indicator"],
    "roi": ["return on investment"],
    "seo": ["search engine optimization"],
    "sem": ["search engine marketing"],
    "ppc": ["pay per click"],
    "ltv": ["lifetime value", "customer lifetime value"],
    "cac": ["customer acquisition cost"],
    "api": ["application programming interface"],
    "aws": ["amazon web services"],
    "gcp": ["google cloud platform"],
    "ci/cd": ["continuous integration continuous deployment"],
    "ux": ["user experience"],
    "ui": ["user interface"],
}

_EXPANSION_TO_ABBR: Dict[str, str] = {}
for abbr, expansions in ABBREVIATIONS.items():
    for exp in expansions:
        _EXPANSION_TO_ABBR[exp.lower()] = abbr


class InputDeduplicator:
    FUZZY_THRESHOLD = 0.88

    def __init__(self):
        self._lemmatizer = WordNetLemmatizer()

    def normalise(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().strip())

    def lemmatise(self, text: str) -> str:
        words = self.normalise(text).split()
        return " ".join(self._lemmatizer.lemmatize(w) for w in words)

    def canonical_key(self, text: str) -> str:
        return self.lemmatise(text)

    def expand_abbreviation(self, text: str) -> Optional[str]:
        normalized = self.normalise(text)
        if normalized in ABBREVIATIONS:
            return ABBREVIATIONS[normalized][0]
        if normalized in _EXPANSION_TO_ABBR:
            return _EXPANSION_TO_ABBR[normalized]
        return None

    def _merge_two(self, a: Dict, b: Dict) -> Dict:
        """Merge two input records, keeping the higher-weight one as base."""
        if b.get("weight", 0) > a.get("weight", 0):
            a, b = b, a

        result = dict(a)

        # Merge aliases
        a_aliases = set(a.get("aliases", []))
        b_aliases = set(b.get("aliases", []))
        b_input = b.get("input", "")
        if b_input and b_input.lower() != a.get("input", "").lower():
            b_aliases.add(b_input)
        result["aliases"] = sorted(a_aliases | b_aliases)

        # Merge seniority
        a_sen = set(a.get("seniority", []))
        b_sen = set(b.get("seniority", []))
        result["seniority"] = sorted(a_sen | b_sen)

        # Source
        a_src = a.get("source", "")
        b_src = b.get("source", "")
        if a_src != b_src and b_src:
            result["source"] = "both"

        # Max weight
        result["weight"] = max(a.get("weight", 0), b.get("weight", 0))

        # Timestamps
        if b.get("first_seen") and (not a.get("first_seen") or b["first_seen"] < a.get("first_seen", "")):
            result["first_seen"] = b["first_seen"]
        if b.get("last_seen") and (not a.get("last_seen") or b["last_seen"] > a.get("last_seen", "")):
            result["last_seen"] = b["last_seen"]

        # Max frequency
        result["jd_frequency"] = max(a.get("jd_frequency", 0), b.get("jd_frequency", 0))

        return result

    def deduplicate(self, inputs: List[Dict]) -> List[Dict]:
        """Deduplicate inputs using 5-phase algorithm."""
        if not inputs:
            return []

        # Phase 1: Group by canonical key
        groups: Dict[str, List[Dict]] = defaultdict(list)
        for inp in inputs:
            text = inp.get("input", "")
            key = self.canonical_key(text)

            # Also check abbreviation expansion
            expanded = self.expand_abbreviation(text)
            if expanded:
                expanded_key = self.canonical_key(expanded)
                key = min(key, expanded_key)  # Deterministic grouping

            groups[key].append(inp)

        # Phase 2: Alias cross-reference
        alias_index: Dict[str, str] = {}
        for key, group in groups.items():
            for inp in group:
                for alias in inp.get("aliases", []):
                    alias_key = self.canonical_key(alias)
                    if alias_key in groups and alias_key != key:
                        # Merge groups
                        groups[key].extend(groups[alias_key])
                        del groups[alias_key]
                    alias_index[alias_key] = key

        # Phase 3: Collapse each group
        collapsed = []
        for key, group in groups.items():
            merged = group[0]
            for item in group[1:]:
                merged = self._merge_two(merged, item)
            collapsed.append(merged)

        # Phase 4: Fuzzy match across collapsed items
        collapsed = self._fuzzy_merge(collapsed)

        # Phase 5: Assign IDs
        for item in collapsed:
            if "id" not in item:
                item["id"] = self._make_id(item.get("input", "unknown"))

        return collapsed

    def _fuzzy_merge(self, items: List[Dict]) -> List[Dict]:
        """Fuzzy-match short terms (<=5 words) across items."""
        if len(items) > 2000:
            return items

        short_items = [(i, it) for i, it in enumerate(items) if len(it.get("input", "").split()) <= 5]
        merged_indices: Set[int] = set()
        result = list(items)

        for i, (idx_a, item_a) in enumerate(short_items):
            if idx_a in merged_indices:
                continue
            for idx_b, item_b in short_items[i + 1 :]:
                if idx_b in merged_indices:
                    continue
                ratio = SequenceMatcher(
                    None,
                    self.canonical_key(item_a.get("input", "")),
                    self.canonical_key(item_b.get("input", "")),
                ).ratio()
                if ratio >= self.FUZZY_THRESHOLD:
                    result[idx_a] = self._merge_two(result[idx_a], result[idx_b])
                    merged_indices.add(idx_b)

        return [it for i, it in enumerate(result) if i not in merged_indices]

    def _make_id(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def deduplicate_inputs(inputs: List[Dict]) -> List[Dict]:
    """Convenience wrapper."""
    return InputDeduplicator().deduplicate(inputs)
