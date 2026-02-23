"""
Input Deduplicator
══════════════════
Merges, normalises, and deduplicates inputs in the Master Input Index.

Strategies (applied in order):
  1. Normalise: lowercase, strip, collapse whitespace
  2. Lemmatise: NLTK WordNet lemmatiser (scraping → scrape)
  3. Alias match: if A in B.aliases or B in A.aliases → merge
  4. Abbreviation expansion: SQL, ML, NLP, CRM, etc.
  5. Fuzzy match: difflib.SequenceMatcher ratio > 0.88

Merge policy:
  • Keep the record with more metadata / higher weight
  • Union aliases, seniority sets
  • Source → 'both' if sources differ
  • Weight → max of the two
"""

import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set

import nltk

for _pkg, _res in [
    ("wordnet", "corpora/wordnet"),
    ("omw-1.4", "corpora/omw-1.4"),
]:
    try:
        nltk.data.find(_res)
    except LookupError:
        nltk.download(_pkg, quiet=True)

from nltk.stem import WordNetLemmatizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ═══════════════════════════════════════════════════════════════════════════
# Common abbreviations – canonical → expansions
# ═══════════════════════════════════════════════════════════════════════════

ABBREVIATIONS: Dict[str, List[str]] = {
    "sql": ["structured query language"],
    "ml": ["machine learning"],
    "ai": ["artificial intelligence"],
    "nlp": ["natural language processing"],
    "crm": ["customer relationship management"],
    "etl": ["extract transform load", "extract-transform-load"],
    "elt": ["extract load transform"],
    "kpi": ["key performance indicator", "key performance indicators"],
    "roi": ["return on investment"],
    "roas": ["return on ad spend"],
    "cac": ["customer acquisition cost"],
    "ltv": ["lifetime value", "customer lifetime value", "clv"],
    "arpu": ["average revenue per user"],
    "seo": ["search engine optimization", "search engine optimisation"],
    "sem": ["search engine marketing"],
    "ppc": ["pay per click", "pay-per-click"],
    "ga4": ["google analytics 4"],
    "dbt": ["data build tool"],
    "aws": ["amazon web services"],
    "gcp": ["google cloud platform"],
    "ci/cd": ["continuous integration continuous deployment"],
    "ux": ["user experience"],
    "ui": ["user interface"],
    "api": ["application programming interface"],
    "okr": ["objectives and key results"],
    "dss": ["decision support system", "decision support systems"],
    "mmm": ["media mix model", "media mix modeling", "marketing mix model"],
    "mta": ["multi-touch attribution"],
    "clv": ["customer lifetime value", "ltv"],
    "b2b": ["business to business", "business-to-business"],
    "b2c": ["business to consumer", "business-to-consumer"],
    "saas": ["software as a service"],
    "plg": ["product-led growth"],
    "llm": ["large language model"],
    "rag": ["retrieval augmented generation"],
}

# Build reverse lookup: expansion → abbreviation
_EXPANSION_TO_ABBR: Dict[str, str] = {}
for abbr, expansions in ABBREVIATIONS.items():
    for exp in expansions:
        _EXPANSION_TO_ABBR[exp.lower()] = abbr.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Core deduplicator
# ═══════════════════════════════════════════════════════════════════════════


class InputDeduplicator:
    """Deduplicates a list of input dicts by normalisation + fuzzy matching."""

    FUZZY_THRESHOLD = 0.88

    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()

    # ── normalisation helpers ─────────────────────────────────────────────

    def normalise(self, text: str) -> str:
        """Lowercase, strip, collapse whitespace, remove trailing 's' plurals."""
        t = text.lower().strip()
        t = re.sub(r"\s+", " ", t)
        return t

    def lemmatise(self, text: str) -> str:
        """Lemmatise each word in the text."""
        words = text.split()
        lemmas = [self.lemmatizer.lemmatize(w) for w in words]
        return " ".join(lemmas)

    def canonical_key(self, text: str) -> str:
        """Produce a canonical dedup key: normalise → lemmatise → sort words for multi-word."""
        normed = self.normalise(text)
        lemmed = self.lemmatise(normed)
        return lemmed

    def expand_abbreviation(self, text: str) -> Optional[str]:
        """Return the full expansion if text is a known abbreviation."""
        normed = self.normalise(text)
        if normed in ABBREVIATIONS:
            return ABBREVIATIONS[normed][0]
        return _EXPANSION_TO_ABBR.get(normed)

    # ── merge logic ───────────────────────────────────────────────────────

    @staticmethod
    def _merge_two(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        """Merge input b into input a (a is the 'primary' record)."""
        # Keep the record with higher weight as the base
        if b.get("weight", 0) > a.get("weight", 0):
            a, b = b, a

        merged = dict(a)

        # Union aliases
        a_aliases = set(a.get("aliases", []))
        b_aliases = set(b.get("aliases", []))
        # Add b's input text as an alias if different
        if b.get("input", "").lower() != merged.get("input", "").lower():
            b_aliases.add(b["input"])
        merged["aliases"] = sorted(a_aliases | b_aliases)

        # Union seniority
        a_sen = set(a.get("seniority", []))
        b_sen = set(b.get("seniority", []))
        merged["seniority"] = sorted(a_sen | b_sen)

        # Source → both if different
        src_a = a.get("source", "research")
        src_b = b.get("source", "research")
        if src_a != src_b:
            merged["source"] = "both"

        # Weight → max
        merged["weight"] = max(a.get("weight", 0), b.get("weight", 0))

        # jd_frequency → max
        if "jd_frequency" in a or "jd_frequency" in b:
            merged["jd_frequency"] = max(
                a.get("jd_frequency", 0), b.get("jd_frequency", 0)
            )

        # first_seen → earliest
        if "first_seen" in a and "first_seen" in b:
            merged["first_seen"] = min(a["first_seen"], b["first_seen"])
        elif "first_seen" in b:
            merged["first_seen"] = b["first_seen"]

        # last_seen → latest
        if "last_seen" in a and "last_seen" in b:
            merged["last_seen"] = max(a["last_seen"], b["last_seen"])
        elif "last_seen" in b:
            merged["last_seen"] = b["last_seen"]

        return merged

    # ── main dedup ────────────────────────────────────────────────────────

    def deduplicate(self, inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate a list of input dicts.

        Returns a new list with duplicates merged.
        """
        if not inputs:
            return []

        # Phase 1: group by canonical key
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        key_map: Dict[str, str] = {}  # canonical_key → group_key

        for inp in inputs:
            text = inp.get("input", "")
            ckey = self.canonical_key(text)

            # Also check abbreviation expansion
            abbr_match = self.expand_abbreviation(text)
            if abbr_match:
                alt_key = self.canonical_key(abbr_match)
                # If either key already has a group, use that
                if alt_key in key_map:
                    ckey = key_map[alt_key]
                elif ckey in key_map:
                    pass  # use existing ckey
                else:
                    key_map[alt_key] = ckey

            key_map[ckey] = ckey
            groups[ckey].append(inp)

        # Phase 2: merge alias matches across groups
        # Build alias → group_key index
        alias_index: Dict[str, str] = {}
        for gkey, items in groups.items():
            for item in items:
                for alias in item.get("aliases", []):
                    akey = self.canonical_key(alias)
                    if akey not in alias_index:
                        alias_index[akey] = gkey

        # Check each group key against alias index for cross-merges
        merge_map: Dict[str, str] = {}  # from_key → to_key
        for gkey in list(groups.keys()):
            if gkey in alias_index and alias_index[gkey] != gkey:
                target = alias_index[gkey]
                if target in groups:
                    merge_map[gkey] = target

        # Apply alias merges
        for from_key, to_key in merge_map.items():
            if from_key in groups and to_key in groups:
                groups[to_key].extend(groups.pop(from_key))

        # Phase 3: collapse each group into a single record
        collapsed: List[Dict[str, Any]] = []
        for gkey, items in groups.items():
            merged = items[0]
            for item in items[1:]:
                merged = self._merge_two(merged, item)
            collapsed.append(merged)

        # Phase 4: fuzzy cross-match on remaining items
        collapsed = self._fuzzy_merge(collapsed)

        # Phase 5: assign canonical IDs
        for item in collapsed:
            item["id"] = self._make_id(item.get("input", "unknown"))

        return collapsed

    def _fuzzy_merge(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge items with fuzzy-similar names (SequenceMatcher > threshold).
        
        Only attempts fuzzy matching on items with short names (≤5 words)
        to keep runtime tractable on large indexes.
        """
        if len(items) <= 1:
            return items

        # Split into candidates for fuzzy matching vs pass-through
        # Only fuzzy-match short terms; long/unique phrases pass through
        MAX_WORDS_FOR_FUZZY = 5
        MAX_ITEMS_FOR_FUZZY = 2000  # safety cap

        candidates = []
        passthrough = []
        for item in items:
            words = item.get("input", "").split()
            if len(words) <= MAX_WORDS_FOR_FUZZY:
                candidates.append(item)
            else:
                passthrough.append(item)

        # If too many candidates, skip fuzzy (canonical + alias merge is enough)
        if len(candidates) > MAX_ITEMS_FOR_FUZZY:
            logging.info(
                "Fuzzy merge: skipping — %d candidates exceeds cap of %d.",
                len(candidates), MAX_ITEMS_FOR_FUZZY,
            )
            return items

        merged_indices: Set[int] = set()
        result: List[Dict[str, Any]] = []

        for i in range(len(candidates)):
            if i in merged_indices:
                continue
            current = candidates[i]
            for j in range(i + 1, len(candidates)):
                if j in merged_indices:
                    continue
                name_a = self.canonical_key(current.get("input", ""))
                name_b = self.canonical_key(candidates[j].get("input", ""))
                # Quick length check — very different lengths can't be fuzzy matches
                if abs(len(name_a) - len(name_b)) > max(len(name_a), len(name_b)) * 0.3:
                    continue
                ratio = SequenceMatcher(None, name_a, name_b).ratio()
                if ratio >= self.FUZZY_THRESHOLD:
                    current = self._merge_two(current, candidates[j])
                    merged_indices.add(j)
            result.append(current)

        return result + passthrough

    @staticmethod
    def _make_id(text: str) -> str:
        """Create a kebab-case ID from text."""
        cleaned = re.sub(r"[^a-z0-9\s-]", "", text.lower())
        return re.sub(r"\s+", "-", cleaned.strip()) or "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════════════════════


def deduplicate_inputs(inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Public helper — instantiate deduplicator and run."""
    deduper = InputDeduplicator()
    result = deduper.deduplicate(inputs)
    logging.info(
        "Deduplication: %d inputs → %d unique inputs", len(inputs), len(result)
    )
    return result
