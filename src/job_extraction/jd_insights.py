"""
Aggregated JD Insights
═══════════════════════
Runs over the master aggregated CSV for a job title and produces
centralised insight files:

  • Cumulative keyword / skill / tool / phrase counts
  • Category-level breakdowns (technical, analytical, soft, domain, etc.)
  • Top-N reports as CSV
  • Per-run + cumulative JSON snapshots

Designed to be called programmatically from the main pipeline
(main_get_jobs.py) and also as a standalone CLI.

Output directory:
    job_search/job_post_details/<title>/insights/
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
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from paths import master_aggregated_csv, insights_for, UNIFIED_MASTER_CSV

# ---------------------------------------------------------------------------
# NLP imports (NLTK – already in requirements.txt)
# ---------------------------------------------------------------------------
import nltk

for _pkg, _res in [
    ("punkt_tab", "tokenizers/punkt_tab"),
    ("stopwords", "corpora/stopwords"),
    ("wordnet", "corpora/wordnet"),
    ("averaged_perceptron_tagger_eng", "taggers/averaged_perceptron_tagger_eng"),
]:
    try:
        nltk.data.find(_res)
    except LookupError:
        nltk.download(_pkg, quiet=True)

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tag import pos_tag
from nltk.tokenize import word_tokenize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ═══════════════════════════════════════════════════════════════════════════
# Taxonomy – curated keyword sets for classification
# ═══════════════════════════════════════════════════════════════════════════

CATEGORY_KEYWORDS: Dict[str, set] = {
    "technical_skill": {
        "python", "sql", "r", "excel", "tableau", "power bi", "looker",
        "javascript", "typescript", "java", "scala", "spark", "hadoop",
        "cloud", "aws", "azure", "gcp", "snowflake", "databricks", "dbt",
        "api", "rest", "graphql", "machine learning", "ml", "deep learning",
        "statistics", "statistical", "predictive", "modeling", "nlp",
        "natural language processing", "computer vision", "neural network",
        "etl", "data pipeline", "data warehouse", "database",
        "github", "git", "docker", "kubernetes", "linux", "terraform",
        "airflow", "kafka", "redis", "mongodb", "postgresql", "mysql",
        "bigquery", "redshift", "fivetran", "stitch", "segment",
        "jupyter", "notebook", "pandas", "numpy", "scipy", "scikit-learn",
        "tensorflow", "pytorch", "keras", "xgboost", "lightgbm",
    },
    "tools_platforms": {
        "jira", "confluence", "asana", "monday", "trello", "notion",
        "salesforce", "hubspot", "marketo", "pardot", "segment",
        "google analytics", "ga4", "adobe analytics", "mixpanel",
        "amplitude", "heap", "fullstory", "hotjar", "optimizely",
        "braze", "iterable", "sendgrid", "twilio",
        "slack", "teams", "zoom", "figma", "miro",
        "datadog", "new relic", "splunk", "grafana",
        "github", "gitlab", "bitbucket", "jenkins", "circleci",
        "sap", "oracle", "workday", "netsuite",
        "powerpoint", "google slides", "google sheets",
    },
    "analytics_function": {
        "data analysis", "data analytics", "business intelligence",
        "reporting", "dashboard", "kpi", "metrics", "tracking",
        "forecasting", "trend analysis", "ad hoc", "ad hoc analysis",
        "data visualization", "visualization", "insights", "insight",
        "a/b testing", "experimentation", "analytical", "analysis",
        "exploratory analysis", "statistical analysis", "data mining",
        "cohort analysis", "funnel analysis", "retention analysis",
        "regression analysis", "time series", "causal inference",
        "attribution", "incrementality", "market research",
    },
    "soft_skill": {
        "communication", "collaboration", "teamwork", "leadership",
        "problem solving", "critical thinking", "time management",
        "self motivated", "proactive", "curious", "creative",
        "attention detail", "detail oriented", "analytical thinking",
        "interpersonal", "presentation", "storytelling", "influence",
        "stakeholder management", "cross functional", "mentoring",
        "coaching", "negotiation", "adaptability", "resilience",
    },
    "data_management": {
        "data quality", "data governance", "data cleaning",
        "data integrity", "data validation", "data modeling",
        "data architecture", "master data", "reference data",
        "data catalog", "metadata", "data privacy", "gdpr",
        "data engineering", "data lake", "data mesh",
        "data lineage", "data dictionary", "schema design",
    },
    "domain_expertise": {
        "marketing", "sales", "finance", "revenue", "customer",
        "product", "operations", "supply chain", "logistics",
        "healthcare", "pharma", "retail", "ecommerce",
        "digital marketing", "advertising", "campaign",
        "customer acquisition", "retention", "lifetime value",
        "crm", "seo", "sem", "ppc", "social media",
        "media mix", "roi", "roas", "cac", "ltv", "arpu",
        "fintech", "insurtech", "healthtech", "edtech",
        "saas", "b2b", "b2c", "marketplace",
    },
    "methodology_approach": {
        "agile", "scrum", "kanban", "waterfall", "sdlc", "ci/cd",
        "lean", "six sigma", "design thinking", "user research",
        "experimentation", "hypothesis testing", "scientific method",
        "okr", "north star", "roadmap", "sprint", "standup",
    },
}

STOP_PHRASES = {
    "color religion", "please note", "united states", "equal opportunity",
    "opportunity employer", "race color", "disability veteran",
    "veteran status", "national origin", "sexual orientation",
    "gender identity", "protected veteran", "note please",
    "may include", "include working", "tools include",
    "tools like", "variety tools", "available tools",
    "high quality", "employer equal",
}

CUSTOM_STOP_WORDS = {
    "job", "position", "role", "work", "team", "company", "business",
    "include", "including", "additionally", "also", "able", "ability",
    "experience", "experiences", "required", "require", "requirements",
    "skills", "skill", "knowledge", "preferred", "prefer",
    "must", "looking", "join", "will", "ideal", "candidate",
    "opportunity", "responsibilities", "qualifications",
}


# ═══════════════════════════════════════════════════════════════════════════
# Core Insight Extractor
# ═══════════════════════════════════════════════════════════════════════════


class JDInsightExtractor:
    """Extracts and aggregates insights from job descriptions."""

    def __init__(self):
        self.stop_words = set(stopwords.words("english")) | CUSTOM_STOP_WORDS
        self.lemmatizer = WordNetLemmatizer()

    # ── text helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        if pd.isna(text) or text in ("-", ""):
            return ""
        text = str(text).lower()
        text = re.sub(r"[^\w\s\-/]", " ", text)
        return " ".join(text.split())

    def _tokenise(self, text: str) -> List[str]:
        tokens = word_tokenize(text)
        return [t for t in tokens if t not in self.stop_words and len(t) > 2]

    def _lemma(self, word: str) -> str:
        return self.lemmatizer.lemmatize(word)

    # ── phrase extraction ─────────────────────────────────────────────────

    def extract_terms(self, text: str) -> List[str]:
        """Extract meaningful single & compound terms via POS tagging."""
        cleaned = self._clean(text)
        if not cleaned:
            return []
        tokens = self._tokenise(cleaned)
        tags = pos_tag(tokens)

        terms: List[str] = []

        # single nouns
        for w, p in tags:
            if p.startswith("N"):
                lem = self._lemma(w)
                if len(lem) > 2:
                    terms.append(lem)

        # adj-noun combos
        for i in range(len(tags) - 1):
            w1, p1 = tags[i]
            w2, p2 = tags[i + 1]
            if p1.startswith("J") and p2.startswith("N"):
                terms.append(f"{w1} {w2}")

        # consecutive nouns (multi-word skills)
        buf: List[str] = []
        for w, p in tags:
            if p.startswith("N"):
                buf.append(w)
            else:
                if len(buf) >= 2:
                    terms.append(" ".join(buf))
                buf = []
        if len(buf) >= 2:
            terms.append(" ".join(buf))

        return terms

    def extract_ngrams(self, text: str, ns: Tuple[int, ...] = (2, 3)) -> List[str]:
        """Extract n-gram phrases from text."""
        cleaned = self._clean(text)
        if not cleaned:
            return []
        tokens = self._tokenise(cleaned)
        phrases: List[str] = []
        for n in ns:
            for i in range(len(tokens) - n + 1):
                phrases.append(" ".join(tokens[i : i + n]))
        return phrases

    # ── classification ────────────────────────────────────────────────────

    @staticmethod
    def _is_valuable(phrase: str) -> bool:
        pl = phrase.lower().strip()
        if len(pl) < 4:
            return False
        if any(sp in pl for sp in STOP_PHRASES):
            return False
        words = pl.split()
        if len(words) > 5:
            return False
        return True

    @staticmethod
    def classify(phrase: str) -> str:
        pl = phrase.lower().strip()
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw in pl or pl in kw:
                    return cat
        return "uncategorized"

    # ── main analysis ─────────────────────────────────────────────────────

    def analyse_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyse a DataFrame of job postings and return raw counters."""
        counters: Dict[str, Counter] = {
            "title_terms": Counter(),
            "description_terms": Counter(),
            "phrases": Counter(),
            "companies": Counter(),
            "locations": Counter(),
        }
        total = 0

        for _, row in df.iterrows():
            total += 1
            if "job_title" in row and pd.notna(row["job_title"]):
                counters["title_terms"].update(self.extract_terms(str(row["job_title"])))
            if "description" in row and pd.notna(row["description"]):
                desc = str(row["description"])
                counters["description_terms"].update(self.extract_terms(desc))
                counters["phrases"].update(self.extract_ngrams(desc))
            for col in ("company", "company_title"):
                if col in row and pd.notna(row[col]):
                    v = str(row[col]).strip()
                    if v and v != "-":
                        counters["companies"][v] += 1
                        break
            if "location" in row and pd.notna(row["location"]):
                v = str(row["location"]).strip()
                if v and v != "-":
                    counters["locations"][v] += 1

        # categorise phrases
        categorised: Dict[str, Counter] = {cat: Counter() for cat in CATEGORY_KEYWORDS}
        categorised["uncategorized"] = Counter()
        for phrase, cnt in counters["phrases"].items():
            if self._is_valuable(phrase):
                categorised[self.classify(phrase)][phrase] = cnt

        return {
            "total_jobs": total,
            "title_terms": counters["title_terms"],
            "description_terms": counters["description_terms"],
            "phrases": counters["phrases"],
            "companies": counters["companies"],
            "locations": counters["locations"],
            **{f"phrases_{cat}": ctr for cat, ctr in categorised.items()},
        }


# ═══════════════════════════════════════════════════════════════════════════
# Persistence helpers
# ═══════════════════════════════════════════════════════════════════════════


def _counter_to_dict(c: Counter, limit: int = 0) -> dict:
    items = c.most_common(limit) if limit else c.most_common()
    return dict(items)


def _merge_counter_dicts(a: dict, b: dict) -> dict:
    merged = Counter(a)
    merged.update(b)
    return dict(merged.most_common())


def _load_json(path: Path) -> Optional[dict]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Could not load %s: %s", path, exc)
    return None


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def run_jd_insights(job_title: str, base_path: str = None, csv_path: str = None) -> Optional[str]:
    """
    Run aggregated JD insights for *job_title*.

    Resolution order for the source CSV:
      1. Explicit *csv_path* argument.
      2. Per-title master aggregated CSV derived from *job_title*.
      3. Unified master CSV as a last-resort fallback.

    Reads the CSV, analyses only previously-unprocessed jobs, merges
    with cumulative results, and writes:
        data/insights/<title>/<title>_cumulative_insights.json
        data/insights/<title>/reports/*.csv

    Returns the path to the cumulative JSON or ``None`` on failure.
    """
    jt_clean = job_title.lower().replace(" ", "_")

    # ── locate master aggregated CSV ──────────────────────────────────────
    if csv_path and os.path.exists(csv_path):
        master_csv = csv_path
    else:
        master_csv = str(master_aggregated_csv(jt_clean))
        if not os.path.exists(master_csv):
            master_csv = str(UNIFIED_MASTER_CSV)

    if not os.path.exists(master_csv):
        logging.warning("Master aggregated CSV not found: %s", master_csv)
        return None

    df = pd.read_csv(master_csv)
    if df.empty:
        logging.warning("Master aggregated CSV is empty.")
        return None

    logging.info("JD Insights: loaded %d jobs from %s", len(df), master_csv)

    # ── tracker: skip already-processed job URLs ──────────────────────────
    insights_dir = insights_for(jt_clean)
    insights_dir.mkdir(parents=True, exist_ok=True)
    tracker_path = insights_dir / f"{jt_clean}_processed_urls.json"
    processed_urls: set = set()

    tracker_data = _load_json(tracker_path)
    if tracker_data:
        processed_urls = set(tracker_data.get("urls", []))
        logging.info("JD Insights: %d URLs already processed.", len(processed_urls))

    # filter to new rows only
    if "job_url" in df.columns:
        new_mask = ~df["job_url"].astype(str).isin(processed_urls)
        new_df = df[new_mask]
    else:
        new_df = df

    if new_df.empty:
        logging.info("JD Insights: no new jobs to analyse – skipping.")
        # Still return the cumulative path so downstream can use it.
        cum_path = insights_dir / f"{jt_clean}_cumulative_insights.json"
        return str(cum_path) if cum_path.exists() else None

    logging.info("JD Insights: analysing %d new jobs.", len(new_df))

    # ── run extraction ────────────────────────────────────────────────────
    extractor = JDInsightExtractor()
    run_results = extractor.analyse_dataframe(new_df)

    # serialise counters → dicts
    run_dict: Dict[str, Any] = {}
    for key, val in run_results.items():
        if isinstance(val, Counter):
            run_dict[key] = _counter_to_dict(val)
        else:
            run_dict[key] = val

    # ── save run snapshot ─────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dict["timestamp"] = ts
    run_snapshot = insights_dir / f"{jt_clean}_insights_{ts}.json"
    _save_json(run_snapshot, run_dict)
    logging.info("Saved run snapshot: %s", run_snapshot)

    # ── merge with cumulative ─────────────────────────────────────────────
    cum_path = insights_dir / f"{jt_clean}_cumulative_insights.json"
    cumulative = _load_json(cum_path) or {}

    for key, val in run_dict.items():
        if key in ("timestamp",):
            continue
        if key == "total_jobs":
            cumulative[key] = cumulative.get(key, 0) + val
        elif isinstance(val, dict):
            cumulative[key] = _merge_counter_dicts(cumulative.get(key, {}), val)
        else:
            cumulative[key] = val

    cumulative["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cumulative["analysis_runs"] = cumulative.get("analysis_runs", 0) + 1

    # ── compute summary statistics ────────────────────────────────────────
    top_n = 25
    summary: Dict[str, Any] = {
        "total_jobs_analysed": cumulative.get("total_jobs", 0),
        "analysis_runs": cumulative.get("analysis_runs", 0),
        "last_updated": cumulative["last_updated"],
    }
    for cat_key in [
        "technical_skill", "tools_platforms", "analytics_function",
        "soft_skill", "data_management", "domain_expertise",
        "methodology_approach", "uncategorized",
    ]:
        pkey = f"phrases_{cat_key}"
        if pkey in cumulative and cumulative[pkey]:
            top = Counter(cumulative[pkey]).most_common(top_n)
            summary[f"top_{cat_key}"] = [{"term": t, "count": c} for t, c in top]

    if "description_terms" in cumulative:
        top_desc = Counter(cumulative["description_terms"]).most_common(top_n)
        summary["top_description_terms"] = [{"term": t, "count": c} for t, c in top_desc]

    if "title_terms" in cumulative:
        top_title = Counter(cumulative["title_terms"]).most_common(top_n)
        summary["top_title_terms"] = [{"term": t, "count": c} for t, c in top_title]

    if "companies" in cumulative:
        top_co = Counter(cumulative["companies"]).most_common(top_n)
        summary["top_companies"] = [{"term": t, "count": c} for t, c in top_co]

    if "locations" in cumulative:
        top_loc = Counter(cumulative["locations"]).most_common(top_n)
        summary["top_locations"] = [{"term": t, "count": c} for t, c in top_loc]

    cumulative["summary"] = summary
    _save_json(cum_path, cumulative)
    logging.info("Saved cumulative insights: %s", cum_path)

    # ── write CSV reports ─────────────────────────────────────────────────
    reports_dir = insights_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    csv_report_specs = [
        ("description_terms", "Term", 200),
        ("title_terms", "Term", 100),
        ("phrases", "Phrase", 200),
        ("companies", "Company", 50),
        ("locations", "Location", 50),
    ]

    # generic reports
    for key, col_label, limit in csv_report_specs:
        if key in cumulative and cumulative[key]:
            top = Counter(cumulative[key]).most_common(limit)
            rdf = pd.DataFrame(top, columns=[col_label, "Count"])
            rdf.to_csv(reports_dir / f"{jt_clean}_{key}.csv", index=False)

    # category phrase reports
    for cat_key in [
        "technical_skill", "tools_platforms", "analytics_function",
        "soft_skill", "data_management", "domain_expertise",
        "methodology_approach", "uncategorized",
    ]:
        pkey = f"phrases_{cat_key}"
        if pkey in cumulative and cumulative[pkey]:
            top = Counter(cumulative[pkey]).most_common(100)
            rdf = pd.DataFrame(top, columns=["Phrase", "Count"])
            rdf.to_csv(reports_dir / f"{jt_clean}_{cat_key}.csv", index=False)

    logging.info("Saved CSV reports to: %s", reports_dir)

    # ── update processed-URL tracker ──────────────────────────────────────
    if "job_url" in new_df.columns:
        processed_urls.update(new_df["job_url"].astype(str).tolist())
    _save_json(tracker_path, {"urls": sorted(processed_urls)})
    logging.info("Updated processed-URL tracker (%d total).", len(processed_urls))

    return str(cum_path)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Run aggregated JD insights for a job title.")
    parser.add_argument("--job_title", required=True, help="Job title to analyse.")
    parser.add_argument("--csv_file", default=None,
                        help="Path to input CSV (default: per-title master, falls back to unified master).")
    args = parser.parse_args()

    result = run_jd_insights(args.job_title, csv_path=args.csv_file)
    if result:
        logging.info("Done – cumulative insights: %s", result)
    else:
        logging.warning("No insights generated.")


if __name__ == "__main__":
    main()
