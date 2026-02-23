#!/bin/bash

# Navigate to project root (one level up from scripts/)
cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/.."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "env" ]; then
    source env/bin/activate
fi

# Set PYTHONPATH to include src/
export PYTHONPATH="$(pwd)/src"

# Run the main pipeline script
echo "Running Job Search Pipeline..."
python3 src/main_get_jobs.py