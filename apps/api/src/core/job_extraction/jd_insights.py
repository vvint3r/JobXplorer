"""JD Insights — extracted from src/job_extraction/jd_insights.py.

Pure-function core: takes DataFrames/strings, returns dicts.
No file I/O — all persistence handled by the caller (Celery task / router).
"""

import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

logger = logging.getLogger(__name__)

# Ensure NLTK data is available
for resource in ("punkt", "punkt_tab", "stopwords", "wordnet", "averaged_perceptron_tagger",
                 "averaged_perceptron_tagger_eng"):
    try:
        nltk.data.find(f"tokenizers/{resource}" if "punkt" in resource else f"corpora/{resource}" if resource in ("stopwords", "wordnet") else f"taggers/{resource}")
    except LookupError:
        nltk.download(resource, quiet=True)


CUSTOM_STOP_WORDS = {
    "experience", "work", "team", "ability", "strong", "etc", "e.g",
    "including", "working", "required", "preferred", "must", "using",
    "well", "also", "may", "new", "role", "position", "candidate",
    "company", "years", "year", "job", "apply", "application",
    "please", "equal", "opportunity", "employer", "employment",
}

STOP_PHRASES = {
    "equal opportunity employer", "years experience", "fast paced",
    "team player", "self starter", "detail oriented", "results driven",
    "apply now", "join our team", "competitive salary",
}

CATEGORY_KEYWORDS: Dict[str, set] = {
    "technical_skill": {
        "python", "sql", "r", "java", "javascript", "scala", "spark",
        "hadoop", "machine learning", "deep learning", "nlp",
        "natural language processing", "computer vision", "statistics",
        "regression", "classification", "clustering", "forecasting",
        "data modeling", "etl", "data pipeline", "api", "rest",
        "html", "css", "react", "node", "docker", "kubernetes",
        "terraform", "ci/cd", "git", "agile", "scrum",
    },
    "tools_platforms": {
        "tableau", "power bi", "looker", "excel", "google analytics",
        "adobe analytics", "segment", "amplitude", "mixpanel",
        "salesforce", "hubspot", "marketo", "google ads", "facebook ads",
        "aws", "gcp", "azure", "snowflake", "redshift", "bigquery",
        "databricks", "airflow", "dbt", "fivetran", "jira", "confluence",
        "slack", "notion", "figma", "sketch",
    },
    "analytics_function": {
        "a/b testing", "experimentation", "attribution", "segmentation",
        "cohort analysis", "funnel analysis", "retention analysis",
        "ltv", "lifetime value", "customer lifetime value", "roi",
        "kpi", "dashboard", "reporting", "data visualization",
        "business intelligence", "predictive analytics", "descriptive analytics",
    },
    "soft_skill": {
        "communication", "collaboration", "leadership", "problem solving",
        "critical thinking", "analytical", "presentation", "storytelling",
        "stakeholder management", "cross-functional", "mentoring",
        "project management", "time management", "strategic thinking",
    },
    "data_management": {
        "data governance", "data quality", "data warehouse", "data lake",
        "data catalog", "metadata", "data lineage", "data dictionary",
        "master data management", "data privacy", "gdpr", "ccpa",
    },
    "domain_expertise": {
        "marketing", "finance", "healthcare", "ecommerce", "saas",
        "fintech", "adtech", "martech", "supply chain", "logistics",
        "real estate", "insurance", "banking", "retail", "media",
        "entertainment", "education", "government", "nonprofit",
    },
    "methodology_approach": {
        "six sigma", "lean", "kaizen", "okr", "balanced scorecard",
        "design thinking", "customer journey", "user research",
        "market research", "competitive analysis", "swot",
    },
}


class JDInsightExtractor:
    """Extract and classify terms/phrases from job descriptions."""

    def __init__(self):
        base_stops = set(stopwords.words("english"))
        self._stop_words = base_stops | CUSTOM_STOP_WORDS
        self._lemmatizer = WordNetLemmatizer()

    def _clean(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s/\-]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _tokenise(self, text: str) -> List[str]:
        tokens = word_tokenize(self._clean(text))
        return [t for t in tokens if t not in self._stop_words and len(t) > 2]

    def _lemma(self, word: str) -> str:
        return self._lemmatizer.lemmatize(word)

    def extract_terms(self, text: str) -> List[str]:
        """POS-tag and extract nouns, adjective-noun combos."""
        tokens = self._tokenise(text)
        tagged = nltk.pos_tag(tokens)
        terms = []
        prev_tag, prev_word = "", ""

        for word, tag in tagged:
            lemma = self._lemma(word)
            if tag.startswith("NN"):
                terms.append(lemma)
                if prev_tag.startswith("JJ") or prev_tag.startswith("NN"):
                    terms.append(f"{self._lemma(prev_word)} {lemma}")
            prev_tag, prev_word = tag, word

        return terms

    def extract_ngrams(self, text: str, ns: Tuple[int, ...] = (2, 3)) -> List[str]:
        """Extract n-gram phrases."""
        tokens = self._tokenise(text)
        phrases = []
        for n in ns:
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i : i + n])
                if self._is_valuable(phrase):
                    phrases.append(phrase)
        return phrases

    def _is_valuable(self, phrase: str) -> bool:
        if len(phrase) < 4:
            return False
        if phrase in STOP_PHRASES:
            return False
        words = phrase.split()
        if len(words) < 2:
            return False
        return True

    def classify(self, phrase: str) -> Optional[str]:
        """Match a phrase against CATEGORY_KEYWORDS. Returns category name or None."""
        phrase_lower = phrase.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if phrase_lower in keywords:
                return category
            for kw in keywords:
                if kw in phrase_lower or phrase_lower in kw:
                    return category
        return None

    def analyse_dataframe(self, df, description_col: str = "description", title_col: str = "job_title") -> Dict[str, Counter]:
        """Analyse a DataFrame of jobs. Returns a dict of Counters by category.

        This is the main pure-function entry point — no file I/O.
        """
        all_terms = Counter()
        all_title_terms = Counter()
        all_phrases = Counter()
        companies = Counter()
        locations = Counter()
        categories: Dict[str, Counter] = {cat: Counter() for cat in CATEGORY_KEYWORDS}

        for _, row in df.iterrows():
            desc = str(row.get(description_col, ""))
            title = str(row.get(title_col, ""))

            if desc and len(desc) > 50:
                terms = self.extract_terms(desc)
                all_terms.update(terms)

                ngrams = self.extract_ngrams(desc)
                all_phrases.update(ngrams)

                for item in terms + ngrams:
                    cat = self.classify(item)
                    if cat:
                        categories[cat][item] += 1

            if title:
                title_terms = self.extract_terms(title)
                all_title_terms.update(title_terms)

            company = str(row.get("company_title", row.get("company", "")))
            if company and company.lower() != "nan":
                companies[company] += 1

            location = str(row.get("location", ""))
            if location and location.lower() != "nan":
                locations[location] += 1

        return {
            "title_terms": all_title_terms,
            "description_terms": all_terms,
            "phrases": all_phrases,
            "companies": companies,
            "locations": locations,
            **categories,
        }


def counter_to_sorted_list(counter: Counter, limit: int = 25) -> List[Tuple[str, int]]:
    """Convert Counter to sorted (term, count) list, optionally limited."""
    items = counter.most_common(limit) if limit else counter.most_common()
    return items


def merge_insights(existing: Dict, new: Dict) -> Dict:
    """Merge two insight dicts (both are {category: [(term, count), ...]})."""
    merged = {}
    all_keys = set(list(existing.keys()) + list(new.keys()))
    for key in all_keys:
        old_counter = Counter(dict(existing.get(key, [])))
        new_counter = Counter(dict(new.get(key, [])))
        old_counter.update(new_counter)
        merged[key] = old_counter.most_common(25)
    return merged
