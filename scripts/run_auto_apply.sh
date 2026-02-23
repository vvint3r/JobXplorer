#!/bin/bash

# Script to run auto-application process
# Usage: ./scripts/run_auto_apply.sh [csv_file] [options]

# Navigate to project root (one level up from scripts/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "env" ]; then
    source env/bin/activate
fi

# Set PYTHONPATH to include src/
export PYTHONPATH="$(pwd)/src"

# Default values
CSV_FILE=""
LIMIT=""
DELAY="5.0"
HEADLESS=""
AUTO_SUBMIT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --csv_file|--csv)
            CSV_FILE="$2"
            shift 2
            ;;
        --limit|-l)
            LIMIT="$2"
            shift 2
            ;;
        --delay|-d)
            DELAY="$2"
            shift 2
            ;;
        --headless)
            HEADLESS="--headless"
            shift
            ;;
        --auto_submit)
            AUTO_SUBMIT="--auto_submit"
            shift
            ;;
        *)
            # If no flag, assume it's the CSV file
            if [ -z "$CSV_FILE" ]; then
                CSV_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Build command  (--csv_file is optional; main_apply defaults to unified master)
CMD="python3 src/auto_application/main_apply.py --delay_between $DELAY"

if [ ! -z "$CSV_FILE" ]; then
    if [ ! -f "$CSV_FILE" ]; then
        echo "Error: CSV file not found: $CSV_FILE"
        exit 1
    fi
    CMD="$CMD --csv_file \"$CSV_FILE\""
fi

if [ ! -z "$LIMIT" ]; then
    CMD="$CMD --limit $LIMIT"
fi

if [ ! -z "$HEADLESS" ]; then
    CMD="$CMD $HEADLESS"
fi

if [ ! -z "$AUTO_SUBMIT" ]; then
    CMD="$CMD $AUTO_SUBMIT"
fi

echo "Running auto-application process..."
echo "CSV File: $CSV_FILE"
echo "Command: $CMD"
echo ""

# Execute the command
eval $CMD

