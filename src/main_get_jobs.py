import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import logging
import subprocess
import glob
from datetime import datetime

from paths import (
    SEARCH_RESULTS_DIR, JOBS_RAN_CSV,
    search_results_for,
)
from job_extraction.jd_insights import run_jd_insights
from job_extraction.master_job_title import ensure_master_job_title
from job_extraction.input_index_generator import generate_or_load_index
from job_extraction.jd_term_extractor import enrich_index_from_jds
from job_extraction.alignment_scorer import score_all_jobs
from auto_application.resume_optimizer import run_resume_optimisation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def ensure_jobs_ran_file_exists():
    """Create jobs_ran.csv if it doesn't exist."""
    log_dir = str(SEARCH_RESULTS_DIR)
    log_file = str(JOBS_RAN_CSV)
    
    # Create directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Create file with headers if it doesn't exist
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            f.write("timestamp,job_keyword,search_status\n")
        logging.info(f"Created new jobs_ran.csv file at {log_file}")

def find_latest_csv(job_title, search_folder=None):
    """Find the latest CSV file for a given job title."""
    try:
        # Clean job title for filename matching
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Look in the job-specific subdirectory
        if search_folder is None:
            search_folder = str(SEARCH_RESULTS_DIR)
        job_folder = os.path.join(search_folder, job_title_clean)
        
        # Get all matching CSV files from the subdirectory
        pattern = os.path.join(job_folder, f"{job_title_clean}__*.csv")
        matching_files = glob.glob(pattern)
        
        if not matching_files:
            raise FileNotFoundError(f"No CSV files found for job title: {job_title} in {job_folder}")
            
        # Get the most recent file
        latest_file = max(matching_files, key=os.path.getctime)
        logging.info(f"Found latest CSV file: {latest_file}")
        return latest_file
        
    except Exception as e:
        logging.error(f"Error finding latest CSV: {e}")
        raise

def record_job_search(job_title, status="completed"):
    """Record a job search in the jobs_ran.csv file."""
    log_file = str(JOBS_RAN_CSV)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"{timestamp},{job_title},{status}\n")
    logging.info(f"Recorded job search for '{job_title}' with status '{status}'")


def run_job_search_pipeline():
    """Run the complete job search pipeline."""
    try:
        logging.info("Starting job search pipeline...")
        
        # Ensure jobs_ran.csv exists
        ensure_jobs_ran_file_exists()
        
        # Prompt for job title if not provided
        job_title = input("Enter the job title to search for: ").strip()
        
        # PIPELINE 1: Run job search
        logging.info("PIPELINE 1: Running the JOB SEARCH pipeline:")
        cmd = ['python3', './src/job_extraction/job_search.py', '--job_title', job_title]
        
        result = subprocess.run(
            cmd,
            stdin=None,
            stdout=None,
            stderr=None,
        )
        
        if result.returncode != 0:
            record_job_search(job_title, "failed")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        
        # Record successful search
        record_job_search(job_title, "completed")
        
        # Get the job title that was used (from the latest run in jobs_ran.csv)
        log_file = str(JOBS_RAN_CSV)
        logging.info(f"Looking for log file at: {log_file}")
        
        if os.path.exists(log_file):
            logging.info("Found jobs_ran.csv file")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                logging.info(f"Found {len(lines)} lines in jobs_ran.csv")
                if len(lines) > 1:  # Header + at least one entry
                    last_line = lines[-1]
                    logging.info(f"Last line from jobs_ran.csv: {last_line.strip()}")
                    job_title = last_line.split(',')[1]  # Assuming job_keyword is second column
                    logging.info(f"Extracted job title: {job_title}")
                    
                    # Find the latest CSV file for this job title
                    try:
                        latest_csv = find_latest_csv(job_title)
                        logging.info(f"Found latest CSV file: {latest_csv}")
                        
                        # PIPELINE 2: Run URL details collection
                        logging.info("PIPELINE 2: Running the JOB URL DETAILS pipeline:")
                        cmd = ['python3', './src/job_extraction/job_url_details.py', '--job_title', job_title, '--filename', latest_csv]
                        logging.info(f"Running command: {' '.join(cmd)}")
                        
                        result = subprocess.run(
                            cmd,
                            stdin=None,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        if result.returncode != 0:
                            logging.error(f"Pipeline 2 failed with output: {result.stdout}\nError: {result.stderr}")
                            raise subprocess.CalledProcessError(result.returncode, cmd)
                        else:
                            logging.info("Pipeline 2 completed successfully")
                            
                            # PIPELINE 3: Merge job details
                            logging.info("PIPELINE 3: Running the JOB DETAILS MERGE pipeline:")
                            cmd = ['python3', './src/job_extraction/merge_job_details.py', '--job_title', job_title]
                            logging.info(f"Running command: {' '.join(cmd)}")
                            
                            result = subprocess.run(
                                cmd,
                                stdin=None,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            if result.returncode != 0:
                                logging.error(f"Pipeline 3 failed with output: {result.stdout}\nError: {result.stderr}")
                                raise subprocess.CalledProcessError(result.returncode, cmd)
                            else:
                                logging.info("Pipeline 3 completed successfully")
                                
                                # PIPELINE 5: Aggregated JD Insights
                                logging.info("PIPELINE 5: Running the JD INSIGHTS pipeline:")
                                try:
                                    insights_path = run_jd_insights(job_title)
                                    if insights_path:
                                        logging.info(f"Pipeline 5 completed – insights: {insights_path}")
                                    else:
                                        logging.warning("Pipeline 5 produced no new insights (may already be up to date)")
                                except Exception as e:
                                    logging.error(f"Pipeline 5 (JD Insights) failed: {e}")
                                    logging.info("Continuing to next pipeline...")
                                
                                # PIPELINE 5.5: Job Alignment Scoring
                                logging.info("PIPELINE 5.5: Running the JOB ALIGNMENT SCORING pipeline:")
                                try:
                                    master_title = ensure_master_job_title()
                                    alignment_index = generate_or_load_index(master_title)
                                    alignment_index = enrich_index_from_jds(alignment_index, job_title)
                                    n_scored = score_all_jobs(alignment_index, job_title)
                                    logging.info(f"Pipeline 5.5 completed – {n_scored} jobs scored")
                                except Exception as e:
                                    logging.error(f"Pipeline 5.5 (Alignment Scoring) failed: {e}")
                                    logging.info("Continuing to next pipeline...")
                                
                                # PIPELINE 6: JD-Based Resume Optimisation
                                logging.info("PIPELINE 6: Running the RESUME OPTIMISATION pipeline:")
                                try:
                                    n_optimised = run_resume_optimisation(job_title)
                                    logging.info(f"Pipeline 6 completed – {n_optimised} resumes optimised")
                                except Exception as e:
                                    logging.error(f"Pipeline 6 (Resume Optimisation) failed: {e}")
                                    logging.info("Continuing...")
                                
                                logging.info("Job search pipeline completed successfully")
                    except FileNotFoundError as e:
                        logging.error(f"Could not find CSV file: {e}")
                    except Exception as e:
                        logging.error(f"Error in Pipeline 2 or 3: {e}")
                else:
                    logging.error("No job entries found in jobs_ran.csv")
        else:
            logging.error(f"Log file not found at {log_file}")
        
        logging.info("Job search pipeline completed")
        
    except Exception as e:
        logging.error(f"Pipeline error: {e}")
        raise

if __name__ == "__main__":
    run_job_search_pipeline()
