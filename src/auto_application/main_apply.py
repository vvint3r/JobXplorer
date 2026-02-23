"""
Main script for auto-applying to jobs.
Reads job listings from CSV files and automatically fills out applications.
"""
import sys
import os
import argparse
import logging
import pandas as pd
import time
import random
import select
import glob

# Add src/ directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paths import UNIFIED_MASTER_CSV
from auto_application.config import load_config, validate_config
from auto_application.job_board_detector import detect_job_board, get_job_board_info
from auto_application.application_tracker import ApplicationTracker
from auto_application.form_fillers import GreenhouseFormFiller, WorkdayFormFiller, GenericFormFiller
from job_extraction.driver_utils import create_driver, cleanup_driver, cleanup_xvfb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_form_filler(job_board_type, driver, config):
    """
    Get the appropriate form filler for a job board type.
    
    Args:
        job_board_type: Type of job board (e.g., 'greenhouse', 'workday')
        driver: Selenium WebDriver instance
        config: User configuration
        
    Returns:
        FormFiller instance
    """
    fillers = {
        'greenhouse': GreenhouseFormFiller,
        'workday': WorkdayFormFiller,
        'generic': GenericFormFiller
    }
    
    filler_class = fillers.get(job_board_type, GenericFormFiller)
    return filler_class(driver, config)

def _wait_for_user_confirmation(timeout_seconds):
    """Wait for user to press Enter in the terminal within timeout_seconds."""
    prompt = (
        f"Waiting for Simplify autofill. Press Enter when done (timeout: {timeout_seconds}s)... "
    )
    sys.stdout.write(prompt)
    sys.stdout.flush()
    ready, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
    if ready:
        sys.stdin.readline()
        return True
    return False


def _setup_simplify_profile(driver):
    """Open a page and pause so the user can install/verify the Simplify extension."""
    from job_extraction.driver_utils import _xvfb_display

    if _xvfb_display:
        logging.warning(
            "Running on a headless server (Xvfb virtual display). "
            "You won't be able to see the browser window."
        )
        logging.info(
            "To use --setup_simplify_profile interactively, either:\n"
            "  1) SSH with X11 forwarding:  ssh -X user@server\n"
            "  2) Install a VNC server and connect via VNC client\n"
            "  3) Pre-install the extension manually (see instructions below)"
        )
        logging.info(
            "Manual extension install alternative:\n"
            "  a) Download the Simplify .crx file on your local machine\n"
            "  b) SCP it to the server\n"
            "  c) Run: google-chrome --user-data-dir=/home/wynt3r/.config/jobxplore-chrome "
            "--load-extension=/path/to/unpacked_extension\n"
            "  d) Or use the --headless mode which doesn't need Simplify"
        )
    else:
        logging.info("Opening Chrome for Simplify setup. Install/verify the extension, then press Enter to continue.")

    driver.get("chrome://extensions/")
    sys.stdout.write("Press Enter after Simplify is installed/enabled (or Ctrl+C to cancel)... ")
    sys.stdout.flush()
    sys.stdin.readline()


def _is_extension_installed(user_data_dir, extension_id):
    """Check if a Chrome extension ID exists in the user data directory."""
    if not user_data_dir or not extension_id:
        return True

    patterns = [
        os.path.join(user_data_dir, "Default", "Extensions", extension_id),
        os.path.join(user_data_dir, "Profile *", "Extensions", extension_id),
    ]

    for pattern in patterns:
        matches = glob.glob(pattern)
        if any(os.path.isdir(path) for path in matches):
            return True
    return False


def process_job_application(job_row, driver, config, tracker, auto_submit=False, use_simplify=False, simplify_timeout=300):
    """
    Process a single job application.
    
    Args:
        job_row: Pandas Series with job information
        driver: Selenium WebDriver instance
        config: User configuration
        tracker: ApplicationTracker instance
        auto_submit: Whether to auto-submit applications (default: False)
        
    Returns:
        dict: Result of the application attempt
    """
    # Prefer application_url over job_url, fallback to job_url if application_url not available
    application_url = job_row.get('application_url', '')
    job_url = job_row.get('job_url', '')
    job_id = job_row.get('job_id', '')
    
    # Determine which URL to use for application
    url_to_use = application_url if application_url and application_url != 'Not Available' and application_url != '' else job_url
    
    if not url_to_use:
        logging.warning("No application URL or job URL found in job row")
        return {'success': False, 'message': 'No URL found', 'submitted': False}
    
    # Check if already applied (use both URLs for tracking)
    if tracker.is_already_applied(url_to_use, job_id) or tracker.is_already_applied(job_url, job_id):
        logging.info(f"Already applied to: {job_row.get('job_title', 'Unknown')} at {job_row.get('company', 'Unknown')}")
        return {'success': True, 'message': 'Already applied', 'submitted': False}
    
    # Detect job board type from the URL we'll use
    job_board_type = detect_job_board(url_to_use)
    job_board_info = get_job_board_info(url_to_use)
    
    logging.info(f"Processing application for: {job_row.get('job_title', 'Unknown')} at {job_row.get('company', 'Unknown')}")
    logging.info(f"Using URL: {url_to_use}")
    logging.info(f"Job board type: {job_board_type}")
    
    # Get appropriate form filler
    try:
        job_data = {
            'job_id': job_id,
            'job_title': job_row.get('job_title', ''),
            'company': job_row.get('company', '') or job_row.get('company_title', ''),
            'job_url': job_url,
            'application_url': application_url,
            'location': job_row.get('location', ''),
            'description': job_row.get('description', '') or job_row.get('job_description', '')
        }

        if use_simplify:
            logging.info("Simplify mode enabled: opening application URL for autofill.")
            driver.get(url_to_use)
            confirmed = _wait_for_user_confirmation(simplify_timeout)
            if confirmed:
                result = {
                    'success': True,
                    'status': 'success',
                    'message': 'Simplify autofill completed (user confirmed).',
                    'submitted': False
                }
            else:
                result = {
                    'success': False,
                    'status': 'timed_out',
                    'message': 'Timed Out',
                    'submitted': False
                }

            tracker.log_application(job_data, result, 'simplify_manual')
            return result

        form_filler = get_form_filler(job_board_type, driver, config)
        
        # Fill the application using the appropriate URL
        result = form_filler.fill_application(url_to_use, job_data)
        
        # Auto-submit if requested (use with caution!)
        if auto_submit and result.get('success') and not result.get('submitted'):
            logging.warning("Auto-submit is enabled. Submitting application...")
            # Note: This would require adding a submit method to form fillers
            # For safety, we'll leave this as a manual step for now
        
        # Log the application
        tracker.log_application(job_data, result, job_board_type)
        
        return result
        
    except Exception as e:
        logging.error(f"Error processing application: {e}")
        error_result = {
            'success': False,
            'message': f'Error: {str(e)}',
            'submitted': False,
            'error': str(e)
        }
        tracker.log_application(
            {
                'job_id': job_id,
                'job_title': job_row.get('job_title', ''),
                'company': job_row.get('company', ''),
                'job_url': job_url
            },
            error_result,
            job_board_type
        )
        return error_result

def load_jobs_from_csv(csv_path, limit=None, filter_applied=True):
    """
    Load jobs from a CSV file.
    
    Args:
        csv_path: Path to the CSV file
        limit: Maximum number of jobs to process (None for all)
        filter_applied: Whether to filter out already applied jobs
        
    Returns:
        DataFrame: Jobs to process
    """
    try:
        df = pd.read_csv(csv_path)
        logging.info(f"Loaded {len(df)} jobs from {csv_path}")
        
        # Filter out jobs without URLs (check both job_url and application_url)
        # Keep jobs that have either job_url or application_url
        has_job_url = df['job_url'].notna() & (df['job_url'] != '')
        
        # Check if application_url column exists
        if 'application_url' in df.columns:
            has_application_url = df['application_url'].notna() & (df['application_url'] != '') & (df['application_url'] != 'Not Available')
            df = df[has_job_url | has_application_url]
        else:
            df = df[has_job_url]
        
        logging.info(f"After filtering for URLs: {len(df)} jobs")
        
        # Limit number of jobs if specified
        if limit:
            df = df.head(limit)
            logging.info(f"Limited to {limit} jobs")
        
        return df
    except Exception as e:
        logging.error(f"Error loading jobs from CSV: {e}")
        return pd.DataFrame()

def main():
    """Main function to run the auto-application process."""
    parser = argparse.ArgumentParser(description='Auto-apply to jobs from CSV file')
    parser.add_argument('--csv_file', type=str, default=None,
                       help='Path to CSV file with job listings (default: data/aggregated/unified_master.csv)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum number of jobs to process')
    parser.add_argument('--auto_submit', action='store_true',
                       help='Automatically submit applications (use with caution!)')
    parser.add_argument('--headless', action='store_true', default=False,
                       help='Run browser in headless mode (default: False - visible browser)')
    parser.add_argument('--delay_between', type=float, default=5.0,
                       help='Delay between applications in seconds (default: 5.0)')
    parser.add_argument('--use_simplify', action='store_true',
                       help='Use Simplify extension for manual autofill (pauses per job).')
    parser.add_argument('--simplify_timeout', type=int, default=300,
                       help='Timeout in seconds while waiting for Simplify (default: 300).')
    parser.add_argument('--chrome_user_data_dir', type=str, default=None,
                       help='Chrome user-data-dir to persist extensions (recommended for Simplify).')
    parser.add_argument('--keep_user_data_dir', action='store_true',
                       help='Do not delete the Chrome user-data-dir after run.')
    parser.add_argument('--setup_simplify_profile', action='store_true',
                       help='Open Chrome for Simplify extension setup, then exit.')
    parser.add_argument('--simplify_extension_id', type=str, default=None,
                       help='Simplify Chrome extension ID (used to verify installation).')
    
    args = parser.parse_args()

    # Resolve CSV path: explicit arg → unified master → error
    csv_file = args.csv_file
    if not csv_file:
        csv_file = str(UNIFIED_MASTER_CSV)
        if not os.path.exists(csv_file):
            logging.error(
                "No --csv_file provided and unified master CSV not found at %s. "
                "Run the job search pipeline first, or pass --csv_file explicitly.",
                csv_file,
            )
            return
        logging.info("No --csv_file specified – using unified master: %s", csv_file)

    if args.use_simplify and args.headless:
        logging.warning("Simplify mode requires a visible browser. Forcing headless=False.")
        args.headless = False
    
    # Load and validate configuration
    config = load_config()
    if not validate_config(config):
        logging.error("Configuration validation failed. Please fill in required fields in user_config.json")
        return
    
    # Initialize browser driver (visible by default)
    driver = None
    try:
        logging.info("Initializing browser...")
        driver = create_driver(
            headless=args.headless,
            profile_name="auto_application",
            user_data_dir=args.chrome_user_data_dir,
            keep_user_data_dir=args.keep_user_data_dir,
        )

        if args.setup_simplify_profile:
            _setup_simplify_profile(driver)
            return

        if args.use_simplify and args.simplify_extension_id and args.chrome_user_data_dir:
            if not _is_extension_installed(args.chrome_user_data_dir, args.simplify_extension_id):
                logging.error("Simplify extension not found in the provided Chrome profile.")
                logging.error("Run with --setup_simplify_profile to install the extension, then retry.")
                return

        # Load jobs
        jobs_df = load_jobs_from_csv(csv_file, limit=args.limit)
        if jobs_df.empty:
            logging.error("No jobs to process")
            return
        
        # Initialize tracker
        tracker = ApplicationTracker()
        
        # Filter out already applied jobs (always do this)
        original_count = len(jobs_df)
        jobs_df = jobs_df[~jobs_df['job_url'].apply(tracker.is_already_applied)]
        filtered_count = len(jobs_df)
        if original_count != filtered_count:
            logging.info(f"Filtered out {original_count - filtered_count} already applied jobs")
        
        if jobs_df.empty:
            logging.info("No new jobs to apply to")
            return
        
        # Process each job
        total_jobs = len(jobs_df)
        successful = 0
        failed = 0
        
        for idx, (_, job_row) in enumerate(jobs_df.iterrows(), 1):
            logging.info(f"\n{'='*60}")
            logging.info(f"Processing job {idx}/{total_jobs}")
            logging.info(f"{'='*60}")
            
            result = process_job_application(
                job_row,
                driver,
                config,
                tracker,
                args.auto_submit,
                use_simplify=args.use_simplify,
                simplify_timeout=args.simplify_timeout,
            )
            
            if result.get('success'):
                successful += 1
            else:
                failed += 1
            
            # Delay between applications (except for the last one)
            if idx < total_jobs:
                delay = args.delay_between + random.uniform(-1, 1)
                logging.info(f"Waiting {delay:.1f} seconds before next application...")
                time.sleep(delay)
        
        # Print summary
        logging.info(f"\n{'='*60}")
        logging.info("APPLICATION SUMMARY")
        logging.info(f"{'='*60}")
        logging.info(f"Total jobs processed: {total_jobs}")
        logging.info(f"Successful fills: {successful}")
        logging.info(f"Failed fills: {failed}")
        
        stats = tracker.get_application_stats()
        logging.info(f"\nOverall application stats:")
        logging.info(f"  Total applications logged: {stats['total']}")
        logging.info(f"  Successful: {stats['successful']}")
        logging.info(f"  Failed: {stats['failed']}")
        logging.info(f"  Submitted: {stats['submitted']}")
        
    except KeyboardInterrupt:
        logging.info("\nProcess interrupted by user")
    except Exception as e:
        logging.error(f"Error in main process: {e}")
    finally:
        if driver:
            cleanup_driver(driver)
            logging.info("Browser closed")
        cleanup_xvfb()

if __name__ == "__main__":
    main()

