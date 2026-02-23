# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

```bash
source venv/bin/activate
export PYTHONPATH="$(pwd)/src"
export OPENAI_API_KEY='your-key-here'   # required for LLM-powered pipelines
```

Dependencies: `python -m pip install -r requirements.txt`

Chrome/Chromium must be installed (used by Selenium/undetected-chromedriver). ChromeDriver binary is in `tools/chromedriver-141/`.

## Common Commands

All scripts must be run from the project root. The `venv` activation and `PYTHONPATH` are handled automatically by the shell scripts.

```bash
# Full pipeline: scrape → enrich → merge → insights → alignment score → resume optimize
./scripts/run_get_jobs.sh

# Auto-apply to collected jobs (defaults to data/aggregated/unified_master.csv)
./scripts/run_auto_apply.sh
./scripts/run_auto_apply.sh --csv_file <path> --limit 10 --headless --auto_submit

# Alignment scoring only (Pipeline 5.5)
./scripts/run_alignment_scoring.sh "job title"
./scripts/run_alignment_scoring.sh --refresh-index --reset-title "job title"

# Job analysis (NLP, legacy)
./scripts/run_job_analysis.sh "job title"

# Individual pipeline components
python3 src/job_extraction/jd_insights.py --job_title "JOB_TITLE"
python3 src/auto_application/resume_optimizer.py --job_title "JOB_TITLE"

# Setup / one-time
python3 src/job_extraction/manual_login.py          # generate LinkedIn cookies → config/linkedin_cookies.txt
python3 src/auto_application/setup_config.py        # interactive user config → config/user_config.json
python3 src/auto_application/check_prereqs.py       # validate setup
```

## Architecture

JobXplore is a six-stage job search automation pipeline. All Python source lives under `src/`, all generated data under `data/`, and all user-provided config under `config/`.

### Central path registry

`src/paths.py` — single source of truth for all file/directory paths. Import from here; never hard-code paths in modules.

### Pipeline stages (run in sequence by `run_get_jobs.sh` → `src/main_get_jobs.py`)

| # | Module | Input | Output |
|---|--------|-------|--------|
| 1 | `src/job_extraction/job_search.py` | Job title (interactive prompt) | `data/search_results/<title>/` CSVs |
| 2 | `src/job_extraction/job_url_details.py` | Latest search results CSV | `data/job_details/<title>/` CSVs (apply URLs + descriptions) |
| 3 | `src/job_extraction/merge_job_details.py` | Job details CSVs | `data/aggregated/<title>/` + **`data/aggregated/unified_master.csv`** |
| 5 | `src/job_extraction/jd_insights.py` | Master aggregated CSV | `data/insights/<title>/` cumulative JSON + CSV reports |
| 5.5 | `src/job_extraction/alignment_scorer.py` | Master aggregated CSV + `data/alignment/master_input_index.json` | `data/alignment/scores/<title>/` + appends columns to aggregated CSV |
| 6 | `src/auto_application/resume_optimizer.py` | Master aggregated CSV + `config/resumes/base_resume/` | `data/optimized_resumes/<company>_<title>_<date>.json` |

Pipeline 5.5 depends on three supporting modules in `src/job_extraction/`:
- `input_index_generator.py` — seeds the Master Input Index from OpenAI + topic docs in `docs/`
- `jd_term_extractor.py` — enriches the index by extracting terms from actual JDs
- `input_deduplicator.py` — deduplicates overlapping index entries
- `master_job_title.py` — persists the canonical target title to `config/master_job_title.json`

### Auto-application pipeline (`src/auto_application/`)

`main_apply.py` reads `data/aggregated/unified_master.csv` (or a specified CSV), detects job boards via `job_board_detector.py`, and dispatches to the appropriate form filler:
- `form_fillers/greenhouse.py` — Greenhouse ATS
- `form_fillers/workday.py` — Workday ATS
- `form_fillers/generic.py` — catch-all

Supports **Simplify-assisted autofill** mode (`--use_simplify`), which opens the apply URL in a persistent Chrome profile with the Simplify extension and waits for user to complete autofill before logging the result.

Application results are tracked in `data/application_logs/applications.csv` via `application_tracker.py`. Already-applied jobs are skipped on subsequent runs (timed-out entries may re-run).

### Key data files

| File | Purpose |
|------|---------|
| `data/aggregated/unified_master.csv` | Primary feed into auto-apply; combines all job titles with a `search_title` column |
| `data/alignment/master_input_index.json` | Weighted index of skills/tools/concepts used for alignment scoring |
| `config/user_config.json` | Personal info, resume path, work authorization (copy from `config/user_config.example.json`) |
| `config/linkedin_cookies.txt` | LinkedIn session cookies for scraping (regenerate when expired) |
| `config/supplementary_terms.json` | Extra terms to boost alignment scores beyond the resume |

### LLM usage

- `OPENAI_API_KEY` is used by `input_index_generator.py` (index seeding) and `resume_optimizer.py` (LLM mode uses `gpt-4o-mini`)
- If `OPENAI_API_KEY` is absent, `resume_optimizer.py` falls back to keyword-match heuristics
- `src/client.py` is a minimal REST client for the DataForSEO API (not OpenAI)

### Running scripts from the correct directory

All `python3` invocations that reference `src/` modules expect `PYTHONPATH` to include `src/` and the working directory to be the project root. The shell scripts set this up automatically. When running modules directly, set `export PYTHONPATH="$(pwd)/src"` first.
