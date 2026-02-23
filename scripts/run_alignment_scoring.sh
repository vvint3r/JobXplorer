#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Pipeline 5.5 — Job Alignment Scoring (standalone)
# ═══════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./scripts/run_alignment_scoring.sh <job_title>
#   ./scripts/run_alignment_scoring.sh "marketing analytics"
#   ./scripts/run_alignment_scoring.sh --refresh-index "marketing analytics"
#
# Flags:
#   --refresh-index    Regenerate the master input index from OpenAI + topic docs
#   --reset-title      Re-prompt for the master job title
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/env"

# Activate virtualenv
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$PROJECT_DIR"

REFRESH=""
RESET_TITLE=""
JOB_TITLE=""

for arg in "$@"; do
    case "$arg" in
        --refresh-index) REFRESH="--refresh" ;;
        --reset-title)   RESET_TITLE="--reset" ;;
        *)               JOB_TITLE="$arg" ;;
    esac
done

if [[ -z "$JOB_TITLE" ]]; then
    echo "Usage: $0 [--refresh-index] [--reset-title] <job_title>"
    exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║  Pipeline 5.5 — Job Alignment Scoring           ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# Step 1: Ensure master job title
if [[ -n "$RESET_TITLE" ]]; then
    python3 src/job_extraction/master_job_title.py --reset
else
    python3 src/job_extraction/master_job_title.py
fi

# Step 2: Generate / load index
if [[ -n "$REFRESH" ]]; then
    echo "  → Refreshing master input index..."
    python3 src/job_extraction/input_index_generator.py --refresh
else
    python3 src/job_extraction/input_index_generator.py
fi

# Step 3: Enrich from JDs
echo "  → Enriching index from job descriptions..."
python3 src/job_extraction/jd_term_extractor.py --job_title "$JOB_TITLE"

# Step 4: Score
echo "  → Scoring job descriptions..."
python3 src/job_extraction/alignment_scorer.py --job_title "$JOB_TITLE"

echo ""
echo "  ✓ Pipeline 5.5 complete"
echo ""
