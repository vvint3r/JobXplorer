#!/bin/bash

# Set error handling
set -e

# Navigate to project root (one level up from scripts/)
cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/.."

# Check if job title is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <job_title>"
    exit 1
fi

# Print start message
echo "Starting Job Analysis Pipeline..."
echo "--------------------------------"
date

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set"
    echo "Please set it before running this script:"
    echo "  export OPENAI_API_KEY='your-api-key-here'"
    exit 1
fi

# Job details setup
JOB_TITLE=$1
JOB_TITLE_CLEAN=$(echo "$JOB_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')

# Directory setup
JOB_DETAILS_DIR="data/job_details/${JOB_TITLE_CLEAN}"
INDIVIDUAL_ANALYSIS_DIR="data/analysis/${JOB_TITLE_CLEAN}/individual"
AGGREGATED_DIR="data/analysis/${JOB_TITLE_CLEAN}/aggregated"

# Create necessary directories
mkdir -p "$JOB_DETAILS_DIR"
mkdir -p "$INDIVIDUAL_ANALYSIS_DIR"
mkdir -p "$AGGREGATED_DIR"

# Function to check and install spaCy models
install_spacy_models() {
    local env_python=$1
    echo "Checking and installing spaCy models..."
    
    # Install basic English model
    $env_python -m spacy download en
    
    # Install small English model
    $env_python -m spacy download en_core_web_sm
    
    # Install large English model
    $env_python -m spacy download en_core_web_lg
}

# Function to setup environment if it doesn't exist
setup_env() {
    local env_name=$1
    local setup_cmd=$2
    
    if [ ! -d "$env_name" ]; then
        echo "Creating new $env_name environment..."
        python3 -m venv $env_name
        source $env_name/bin/activate
        # Upgrade pip first
        pip install --upgrade pip
        eval "$setup_cmd"
        
        # If this is the spaCy environment, install the models
        if [[ $env_name == *"spacy"* ]]; then
            install_spacy_models "python3"
        fi
        
        deactivate
    else
        echo "Using existing $env_name environment..."
        # Even for existing spaCy environment, verify models are installed
        if [[ $env_name == *"spacy"* ]]; then
            source $env_name/bin/activate
            install_spacy_models "python3"
            deactivate
        fi
    fi
}

# Setup commands for each environment
KEYBERT_SETUP="pip install -q torch transformers nltk pandas scikit-learn keybert && python3 -c 'import nltk; nltk.download(\"wordnet\"); nltk.download(\"averaged_perceptron_tagger\")'"
YAKE_SETUP="pip install -q yake nltk pandas scikit-learn sentence-transformers && python3 -c 'import nltk; nltk.download(\"wordnet\"); nltk.download(\"averaged_perceptron_tagger\")'"
SPACY_SETUP="pip install --upgrade pip && \
             pip install wheel setuptools && \
             pip install pandas scikit-learn nltk && \
             pip install spacy==3.8.3 && \
             pip install httpx==0.27.0 && \
             pip install openai==1.12.0 && \
             pip install sentence-transformers python-Levenshtein keybert yake transformers && \
             python3 -c 'import nltk; nltk.download(\"wordnet\"); nltk.download(\"averaged_perceptron_tagger\")'"

# Setup all environments
echo "Setting up environments..."
setup_env "venv_keybert" "$KEYBERT_SETUP"
setup_env "venv_yake" "$YAKE_SETUP"
setup_env "venv_spacy" "$SPACY_SETUP"

# Set PYTHONPATH to include src/
export PYTHONPATH="$(pwd)/src"

echo "Starting job text analysis for ${JOB_TITLE}..."

# First, merge all job details into an aggregated file
echo "Merging job details into aggregated file..."
python3 src/job_extraction/merge_job_details.py --job_title "$JOB_TITLE"
if [ $? -eq 0 ]; then
    echo "Successfully merged job details"
else
    echo "Error merging job details"
    exit 1
fi

# Process individual job files
echo "Processing individual job files..."
if [ -d "$JOB_DETAILS_DIR" ]; then
    # Find all job detail CSV files
    for job_file in "$JOB_DETAILS_DIR"/*.csv; do
        if [ -f "$job_file" ]; then
            echo "Analyzing individual job file: $(basename "$job_file")"
            # Run individual job analysis
            python -m job_text_analysis.job_processor --mode individual \
                --input "$job_file" \
                --job_title "$JOB_TITLE" \
                --output_dir "$INDIVIDUAL_ANALYSIS_DIR"
            
            if [ $? -eq 0 ]; then
                echo "Successfully analyzed $(basename "$job_file")"
            else
                echo "Error analyzing $(basename "$job_file")"
            fi
        fi
    done
else
    echo "No job details directory found at $JOB_DETAILS_DIR"
fi

# Process aggregated job files
echo "Processing aggregated job analysis..."
AGGREGATED_FILE="data/aggregated/${JOB_TITLE_CLEAN}/${JOB_TITLE_CLEAN}_aggregated.csv"
if [ -f "$AGGREGATED_FILE" ]; then
    echo "Analyzing aggregated jobs file: $AGGREGATED_FILE"
    # Run aggregated analysis
    python -m job_text_analysis.job_processor --mode aggregated \
        --input "$AGGREGATED_FILE" \
        --job_title "$JOB_TITLE" \
        --output_dir "$AGGREGATED_DIR"
    
    if [ $? -eq 0 ]; then
        echo "Successfully analyzed aggregated jobs"
    else
        echo "Error analyzing aggregated jobs"
        exit 1
    fi
else
    echo "No aggregated file found at $AGGREGATED_FILE"
    echo "This is unexpected as we just ran the merge step. Please check for errors above."
    exit 1
fi

echo "--------------------------------"
echo "Job analysis completed successfully!"
date

exit 0