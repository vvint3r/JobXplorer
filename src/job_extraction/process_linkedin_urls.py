#!/usr/bin/env python3

import sys
import os
import time
import random

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import logging
import pandas as pd
from datetime import datetime
from job_url_details import get_job_details, load_cookies
from utils import load_cookie_data
from driver_utils import create_driver, cleanup_driver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def read_urls_from_file(filename):
    """Read LinkedIn URLs from a text file."""
    try:
        with open(filename, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        logging.info(f"Successfully loaded {len(urls)} URLs from {filename}")
        return urls
    except Exception as e:
        logging.error(f"Error reading URLs from file: {e}")
        return []

def process_urls(urls):
    """Process URLs and collect job details."""
    driver = None
    try:
        # Initialize driver with random port and unique profile
        logging.info("Initializing Chrome driver...")
        driver = create_driver(profile_name="linkedin_urls_processor")
        
        # Load cookies
        logging.info("Loading cookies...")
        cookies = load_cookie_data()
        if cookies:
            load_cookies(driver, cookies)
        else:
            logging.warning("No cookies loaded")
        
        # Process job links and collect detailed information
        logging.info("Starting to process job links...")
        detailed_jobs = []
        total_urls = len(urls)
        
        for idx, url in enumerate(urls, 1):
            try:
                logging.info(f"Processing URL {idx}/{total_urls}: {url}")
                job_details = get_job_details(driver, url)
                if job_details:
                    job_dict = {
                        'job_title': job_details[0],
                        'company': job_details[1],
                        'description': job_details[2],
                        'date_posted': job_details[3],
                        'location': job_details[4],
                        'remote': job_details[5],
                        'salary': job_details[6],
                        'job_url': job_details[7],
                        'days_since_posted': job_details[8],
                        'application_url': job_details[9]
                    }
                    detailed_jobs.append(job_dict)
                    logging.info(f"Successfully processed URL {idx}")
            except Exception as e:
                logging.error(f"Error processing URL {url}: {e}")
                continue
        
        return detailed_jobs
        
    except Exception as e:
        logging.error(f"Error in process_urls: {e}")
        return []
    finally:
        cleanup_driver(driver)

def save_results(jobs, output_file):
    """Save job details to CSV file."""
    try:
        df = pd.DataFrame(jobs)
        df.to_csv(output_file, index=False)
        logging.info(f"Results saved to {output_file}")
        return True
    except Exception as e:
        logging.error(f"Error saving results: {e}")
        return False

def main():
    # Get the project root directory (2 levels up from this script)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Define input and output files with full paths
    input_file = os.path.join(project_root, "config/jobs_linkedin_urls.txt")
    output_file = os.path.join(project_root, "data/jobs_linkedin_urls_adhoc.csv")
    
    # Read URLs
    urls = read_urls_from_file(input_file)
    if not urls:
        logging.error("No URLs found to process. Exiting.")
        return
    
    # Process URLs
    job_details = process_urls(urls)
    if not job_details:
        logging.error("No job details collected. Exiting.")
        return
    
    # Save results
    save_results(job_details, output_file)

if __name__ == "__main__":
    main()