# JobXplore — Commands Reference

## Prerequisites

```bash
export OPENAI_API_KEY='your-key-here'
```

---

## 1. Job Search + Enrichment + Scoring + Resume Optimization

Runs Pipelines 1 → 2 → 3 → 5 → 5.5 → 6 in sequence.

```bash
./scripts/run_get_jobs.sh
```

---

## 2. Alignment Scoring (standalone)

Run Pipeline 5.5 independently against an existing aggregated CSV.

```bash
./scripts/run_alignment_scoring.sh "job title"
```

| Flag | Description |
|------|-------------|
| `--refresh-index` | Regenerate the master input index from OpenAI + topic docs |
| `--reset-title` | Re-prompt for the master job title |

---

## 3. Auto-Apply

Applies to jobs using the unified master CSV (default) or a specific CSV.

```bash
./scripts/run_auto_apply.sh
```

| Flag | Description |
|------|-------------|
| `--csv_file <path>` | Use a specific CSV instead of the unified master |
| `--limit <n>` | Max number of jobs to apply to |
| `--delay <secs>` | Delay between applications (default: 5.0) |
| `--headless` | Run Chrome in headless mode |
| `--auto_submit` | Automatically submit applications |

---

## 4. Job Analysis

Deep analysis of job descriptions for a given title (requires `OPENAI_API_KEY`).

```bash
./scripts/run_job_analysis.sh "job title"
```

---

## Typical Workflow

```bash
# Step 1 — Scrape, enrich, score, and optimise resumes
./scripts/run_get_jobs.sh

# Step 2 — Apply to the collected jobs
./scripts/run_auto_apply.sh
```
