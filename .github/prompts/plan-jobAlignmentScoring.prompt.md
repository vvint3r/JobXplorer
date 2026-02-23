# Plan: Job Alignment Scoring — Pipeline 5.5

## Objective

Insert a new pipeline step **between Pipeline 5 (JD Insights) and Pipeline 6 (Resume Optimisation)** that scores how well each job description aligns with the user's resume and supplementary skill inputs. The step also generates and maintains a **Master Input Index** — a weighted, classified catalogue of job-relevant terms seeded by OpenAI research and continuously enriched from real job descriptions.

---

## Terminology

| Term | Definition |
|------|-----------|
| **Input** | A single skill, tool, function, phrase, methodology, or domain term relevant to the master job title |
| **Master Job Title** | The user's canonical target role (e.g., "Sr. Director, Marketing Analytics"). Entered once on first run, persisted forever |
| **Weight** | 0.0–1.0 float indicating how aligned an input is with current job market demand |
| **Input Type** | One of: `skill`, `tool`, `function`, `methodology`, `domain`, `soft_skill`, `certification`, `concept` |
| **Seniority Band** | Which levels this input is relevant to: `entry`, `mid`, `senior`, `director`, `vp`, `c-suite` (list) |
| **Source** | `research` (OpenAI-generated), `jd` (extracted from job descriptions), or `both` |

---

## Architecture Overview

```
Pipeline 5 (JD Insights)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Pipeline 5.5 — Job Alignment Scoring               │
│                                                     │
│  ┌─────────────────┐    ┌────────────────────────┐  │
│  │ Master Input    │◄───│ OpenAI Research         │  │
│  │ Index Generator │    │ (one-time seed +        │  │
│  │                 │◄───│  periodic refresh)      │  │
│  └────────┬────────┘    └────────────────────────┘  │
│           │                                         │
│  ┌────────▼────────┐    ┌────────────────────────┐  │
│  │ JD Term         │◄───│ Aggregated JD corpus    │  │
│  │ Extractor       │    │ (from Pipeline 5)       │  │
│  └────────┬────────┘    └────────────────────────┘  │
│           │                                         │
│  ┌────────▼────────┐    ┌────────────────────────┐  │
│  │ Alignment       │◄───│ Resume Components JSON  │  │
│  │ Scorer          │◄───│ + Supplementary Terms   │  │
│  └────────┬────────┘    └────────────────────────┘  │
│           │                                         │
│  ┌────────▼────────┐                                │
│  │ Score Output    │ → per-job score CSV + JSON     │
│  └─────────────────┘                                │
└─────────────────────────────────────────────────────┘
        │
        ▼
Pipeline 6 (Resume Optimisation)
```

---

## Detailed Design

### 1. Master Job Title — First-Run Prompt

**File:** `src/job_extraction/master_job_title.py`

- On first run, prompt the user via CLI: `"Enter your master job title (e.g., 'Sr. Director, Marketing Analytics'):"`.
- Persist to `config/master_job_title.json`:
  ```json
  {
    "master_job_title": "Sr. Director, Marketing Analytics",
    "created_at": "2026-02-22T14:00:00Z",
    "updated_at": "2026-02-22T14:00:00Z"
  }
  ```
- On subsequent runs, read from file silently. Provide a `--reset-title` CLI flag for override.
- Add `MASTER_JOB_TITLE_JSON` constant to `src/paths.py`.

---

### 2. Master Input Index — Seed Generation via OpenAI

**File:** `src/job_extraction/input_index_generator.py`

#### 2a. OpenAI Research Seed

Call GPT-4o-mini with a structured prompt to generate an exhaustive list of inputs for the master job title. Process in **batches** to respect token limits:

- **Batch 1 — Tools & Platforms** (request ~100 items)
- **Batch 2 — Technical Skills & Functions** (~100 items)
- **Batch 3 — Methodologies & Concepts** (~80 items)
- **Batch 4 — Domain Expertise & Soft Skills** (~80 items)
- **Batch 5 — Seniority-Differentiated Inputs** (re-weight existing items by seniority)

Each batch returns JSON:
```json
[
  {
    "input": "Python",
    "type": "tool",
    "weight": 0.72,
    "seniority": ["mid", "senior", "director"],
    "source": "research",
    "aliases": ["python3", "python programming", "cpython"]
  }
]
```

**Prompt template** (per batch):
```
You are a job market analyst. For the role "{master_job_title}", generate a comprehensive
list of {batch_category} that appear in real job descriptions for this role and related
roles at all seniority levels (entry through C-suite).

For each item return:
- "input": the canonical term (lowercase, singular where appropriate)
- "type": one of [skill, tool, function, methodology, domain, soft_skill, certification, concept]
- "weight": 0.0-1.0 how commonly this appears in job descriptions for this role
- "seniority": array of levels where this is relevant [entry, mid, senior, director, vp, c-suite]
- "aliases": array of alternative phrasings, plurals, abbreviations, close synonyms

Return valid JSON array only.
```

#### 2b. Topic Index Bootstrap

Parse both `docs/master_topic_index.md` and `docs/master_topic_index_enriched.md` to extract pre-researched inputs:

- **Chunk processing**: Both files are large (master_topic_index.md ~11,825 lines; enriched ~1,334 lines). The parser will:
  1. Read each file in chunks of ~500 lines
  2. Use regex to extract L4/L5/L6 items and their semantic associations (from enriched version's `→ *[...]* ` syntax)
  3. Map the L1/L2 hierarchy into `type` classification
  4. Merge with OpenAI-generated items by fuzzy matching

- **Hierarchy-to-type mapping**:
  | L1 Domain | → Input Type |
  |-----------|-------------|
  | FOUNDATIONS & CORE CONCEPTS | `concept` |
  | STATISTICAL METHODS & PROBABILITY | `skill` / `methodology` |
  | MATHEMATICAL FOUNDATIONS | `skill` |
  | EXPERIMENTATION & CAUSAL INFERENCE | `methodology` |
  | MACHINE LEARNING & AI | `skill` / `tool` |
  | DATA ENGINEERING & INFRASTRUCTURE | `tool` / `skill` |
  | MARKETING ANALYTICS & MEASUREMENT | `function` / `domain` |
  | DIGITAL ANALYTICS & WEB | `function` / `tool` |
  | BUSINESS INTELLIGENCE & VISUALIZATION | `tool` / `function` |
  | LEADERSHIP & MANAGEMENT | `soft_skill` |
  | PROFESSIONAL DEVELOPMENT | `soft_skill` / `concept` |
  | DATA ETHICS & PRIVACY | `domain` / `concept` |

#### 2c. Deduplication & Alias Aggregation

**File:** `src/job_extraction/input_deduplicator.py`

Dedicated module to collapse similar inputs:

1. **Exact match after normalization**: lowercase, strip whitespace, remove trailing 's' for plurals
2. **Lemmatization**: NLTK WordNet lemmatizer (already in use by `jd_insights.py`) — e.g., "scraping" → "scrape", "scraped" → "scrape"
3. **Alias matching**: If input A's text appears in input B's `aliases` array (or vice versa), merge
4. **Fuzzy matching**: Use `difflib.SequenceMatcher` (ratio > 0.88) for close matches (e.g., "data visualization" vs "data visualisation")
5. **Abbreviation expansion**: Maintain a lookup for common abbreviations (SQL, ML, NLP, CRM, etc.)
6. **Merge strategy**: When two inputs merge, keep the one with more metadata; union the `aliases`, `seniority`, and `source` fields; take the higher `weight`; if sources differ, set to `both`

---

### 3. Master Input Index — Storage

**File:** `data/alignment/master_input_index.json`

Add to `src/paths.py`:
```python
ALIGNMENT_DIR        = DATA_DIR / "alignment"
MASTER_INPUT_INDEX   = ALIGNMENT_DIR / "master_input_index.json"
SUPPLEMENTARY_TERMS  = CONFIG_DIR / "supplementary_terms.json"
ALIGNMENT_SCORES_DIR = ALIGNMENT_DIR / "scores"
```

**Schema:**
```json
{
  "metadata": {
    "master_job_title": "Sr. Director, Marketing Analytics",
    "version": 1,
    "created_at": "2026-02-22T14:00:00Z",
    "updated_at": "2026-02-22T14:00:00Z",
    "total_inputs": 847,
    "sources": {
      "research": 412,
      "jd": 289,
      "both": 146
    }
  },
  "inputs": [
    {
      "id": "python",
      "input": "Python",
      "type": "tool",
      "weight": 0.72,
      "seniority": ["mid", "senior", "director"],
      "source": "both",
      "aliases": ["python3", "python programming", "cpython"],
      "jd_frequency": 0.34,
      "first_seen": "2026-02-22",
      "last_seen": "2026-02-22"
    }
  ]
}
```

- `id`: kebab-case canonical key derived from the lemmatized input
- `jd_frequency`: fraction of JDs in the corpus that mention this input (updated each run)
- `first_seen` / `last_seen`: tracks currency of the term in the market

---

### 4. Supplementary Terms Input

**File:** `config/supplementary_terms.json`

User-maintained file for terms relevant to their background but not in their resume:

```json
{
  "terms": [
    {
      "term": "causal inference",
      "type": "methodology",
      "proficiency": "advanced",
      "notes": "Published research but not listed on resume"
    },
    {
      "term": "dbt",
      "type": "tool",
      "proficiency": "intermediate"
    }
  ]
}
```

- On first run, if the file doesn't exist, create a template and notify the user.
- The scorer treats supplementary terms as a secondary positive signal (weighted lower than resume matches unless `proficiency` is `expert` or `advanced`).

---

### 5. JD Term Extraction — Enriching the Index from Job Descriptions

**File:** `src/job_extraction/jd_term_extractor.py`

For each job description in the aggregated corpus:

1. Reuse `JDInsightExtractor.extract_terms()` and `extract_ngrams()` from existing Pipeline 5 (`jd_insights.py`)
2. Classify each extracted term against the Master Input Index:
   - **Known input**: increment `jd_frequency`, update `last_seen`, ensure `source` includes `jd` → set to `both` if was `research`
   - **New term**: add to index with `source: "jd"`, assign `type` via `JDInsightExtractor.classify()`, estimate `weight` from corpus frequency, infer `seniority` from the job title text (regex: VP/Director/Senior/Lead → band mapping)
3. Run deduplication pass after each batch of new terms
4. Track which job URLs have been processed (same pattern as `jd_insights.py`'s `_load_processed_urls()`)

**Seniority inference from job title:**
```python
SENIORITY_PATTERNS = {
    "entry":    r"\b(entry|junior|jr|associate|intern)\b",
    "mid":      r"\b(mid|analyst|specialist|coordinator)\b",
    "senior":   r"\b(senior|sr|lead|principal|staff)\b",
    "director": r"\b(director|head of|group lead)\b",
    "vp":       r"\b(vp|vice president|svp|evp)\b",
    "c-suite":  r"\b(chief|cto|cmo|cdo|cfo|coo|c-suite)\b",
}
```

---

### 6. Alignment Scorer

**File:** `src/job_extraction/alignment_scorer.py`

#### Inputs
1. **Master Input Index** (`data/alignment/master_input_index.json`)
2. **Resume Components** (`config/resumes/base_resume/*_components.json`)
3. **Supplementary Terms** (`config/supplementary_terms.json`)
4. **Job Description** (per-job text from aggregated CSV)

#### Scoring Algorithm

For each job:

**Step 1 — Extract JD inputs**: tokenize the JD text, match against the Master Input Index (exact + alias matching + lemmatized fuzzy)

**Step 2 — Score each JD input against resume**:
```
resume_match_score(input_i) =
    1.0  if input_i appears in resume text (exact or alias match)
    0.7  if input_i appears in supplementary terms with proficiency >= advanced
    0.5  if input_i appears in supplementary terms with proficiency < advanced
    0.0  otherwise (gap)
```

**Step 3 — Weighted alignment score**:
```
alignment_score = Σ (weight_i × resume_match_score_i) / Σ (weight_i)
```
where the sum is over all inputs found in the JD.

**Step 4 — Seniority fit bonus/penalty**:
- If the job's inferred seniority band is in the input's `seniority` array → no adjustment
- If not → apply 0.8× penalty to that input's contribution

**Step 5 — Gap analysis**: List all JD inputs where `resume_match_score = 0.0`, sorted by weight descending. These are the "skill gaps" for this job.

#### Output per job:
```json
{
  "job_url": "https://linkedin.com/jobs/...",
  "job_title": "Director, Marketing Analytics",
  "company": "Acme Corp",
  "alignment_score": 0.78,
  "alignment_grade": "B+",
  "matched_inputs": [
    {"input": "Python", "type": "tool", "weight": 0.72, "match": "resume"}
  ],
  "supplementary_matches": [
    {"input": "causal inference", "type": "methodology", "weight": 0.65, "match": "supplementary", "proficiency": "advanced"}
  ],
  "gaps": [
    {"input": "dbt", "type": "tool", "weight": 0.55, "seniority": ["senior", "director"]}
  ],
  "seniority_fit": "director",
  "inputs_found": 42,
  "inputs_matched": 31,
  "inputs_gap": 11
}
```

**Grade mapping:**
| Score Range | Grade |
|------------|-------|
| 0.90–1.00  | A+    |
| 0.85–0.89  | A     |
| 0.80–0.84  | A-    |
| 0.75–0.79  | B+    |
| 0.70–0.74  | B     |
| 0.65–0.69  | B-    |
| 0.60–0.64  | C+    |
| 0.55–0.59  | C     |
| 0.50–0.54  | C-    |
| < 0.50     | D     |

---

### 7. Output Files

| Output | Path | Format |
|--------|------|--------|
| Master Input Index | `data/alignment/master_input_index.json` | JSON |
| Per-title score report | `data/alignment/scores/<title>/<title>_alignment_scores.csv` | CSV |
| Per-title score detail | `data/alignment/scores/<title>/<title>_alignment_detail.json` | JSON |
| Aggregated gap report | `data/alignment/scores/<title>/<title>_gap_analysis.csv` | CSV (inputs × jobs) |
| Score summary for Pipeline 6 | Added as columns to the master aggregated CSV | `alignment_score`, `alignment_grade`, `top_gaps` |

---

### 8. Pipeline Integration

**File changes:** `src/main_get_jobs.py`

```python
# After Pipeline 5 (JD Insights), before Pipeline 6 (Resume Optimisation):

# ── Pipeline 5.5: Job Alignment Scoring ──
from job_extraction.master_job_title import ensure_master_job_title
from job_extraction.input_index_generator import generate_or_load_index
from job_extraction.jd_term_extractor import enrich_index_from_jds
from job_extraction.alignment_scorer import score_all_jobs

master_title = ensure_master_job_title()
index = generate_or_load_index(master_title)
index = enrich_index_from_jds(index, title)
score_all_jobs(index, title)
```

**Script:** Add `run_alignment_scoring.sh` to `scripts/` for standalone execution.

---

### 9. New Files Summary

| File | Purpose |
|------|---------|
| `src/job_extraction/master_job_title.py` | Master job title prompt & persistence |
| `src/job_extraction/input_index_generator.py` | OpenAI seed generation + topic index parsing |
| `src/job_extraction/input_deduplicator.py` | Alias merging, lemma-based dedup, fuzzy matching |
| `src/job_extraction/jd_term_extractor.py` | Enrich index from real JD corpus |
| `src/job_extraction/alignment_scorer.py` | Per-job scoring engine |
| `config/supplementary_terms.json` | User's supplementary terms (template on first run) |
| `config/master_job_title.json` | Persisted master job title |
| `scripts/run_alignment_scoring.sh` | Standalone runner |
| `data/alignment/` | All alignment outputs (created at runtime) |

---

### 10. Dependencies

**No new pip packages required.** Leveraging:
- `openai` (already in requirements.txt, v1.12.0)
- `nltk` (already in use by `jd_insights.py`)
- `pandas` (already in use throughout)
- `difflib` (stdlib — for fuzzy matching)
- `json`, `re`, `pathlib` (stdlib)

---

### 11. Topic Index Processing Strategy

Both `master_topic_index.md` (11,825 lines) and `master_topic_index_enriched.md` (1,334 lines) are too large for a single OpenAI call or in-memory regex pass without care.

**Processing approach:**

1. **Enriched index first** (smaller, richer): Parse `master_topic_index_enriched.md` in ~3 chunks of ~450 lines each. Extract:
   - L4/L5 term names via regex: `r"^\s*-\s*\*\*L[45]:\s*(.+?)\*\*"` and `r"^\s*-\s*L5:\s*(.+?)→"`
   - Semantic aliases via regex: `r"→\s*\*\[(.+?)\]\*"` → split on `, `
   - L1/L2 context for type classification (maintained as parser state)

2. **Base index second** (larger, structural): Parse `master_topic_index.md` in ~24 chunks of ~500 lines. Extract items not already present from enriched parse. This file has more L6 detail but no aliases.

3. **Merge**: Deduplicate against the OpenAI-seeded items. Items from topic indices get `source: "research"` since they represent curated domain knowledge.

---

### 12. Incremental Updates

The Master Input Index is designed for **incremental enrichment**:
- First run: OpenAI seed + topic index bootstrap → full index
- Subsequent runs: Only new (unprocessed) JDs are scanned → new terms appended, frequencies updated
- Periodic refresh: `--refresh-index` flag re-generates the OpenAI seed and re-merges (useful when changing master job title or after significant market shifts)

---

### 13. Error Handling & Fallbacks

| Scenario | Fallback |
|----------|----------|
| No OpenAI API key | Skip OpenAI seed; rely solely on topic index + JD extraction |
| OpenAI rate limit / timeout | Retry 3× with exponential backoff; partial index is still usable |
| Resume components JSON missing | Score against PDF-extracted text (via `resume_parser.py`) |
| Supplementary terms file missing | Create template, proceed with resume-only scoring |
| Empty JD text for a job | Skip scoring, mark as `alignment_score: null` |

---

### 14. Implementation Sequence

| Step | Task | Est. Effort |
|------|------|-------------|
| 1 | Add paths to `src/paths.py` | 5 min |
| 2 | `master_job_title.py` — prompt + persist | 20 min |
| 3 | `input_deduplicator.py` — dedup engine | 45 min |
| 4 | `input_index_generator.py` — OpenAI seed + topic index parser | 90 min |
| 5 | `jd_term_extractor.py` — JD corpus enrichment | 45 min |
| 6 | `alignment_scorer.py` — scoring engine | 60 min |
| 7 | Integrate into `main_get_jobs.py` pipeline | 20 min |
| 8 | `supplementary_terms.json` template | 10 min |
| 9 | `run_alignment_scoring.sh` script | 10 min |
| 10 | Testing & refinement | 60 min |
