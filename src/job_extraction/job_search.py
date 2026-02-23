import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pandas as pd
import random
import time
import os
from datetime import datetime
import json
import logging
from job_extraction.utils import load_cookie_data
from job_extraction.config import search_parameters
from job_extraction.driver_utils import create_driver, cleanup_driver
import urllib3
import uuid
from job_metrics_tracker import JobMetricsTracker
from paths import DEBUG_DIR, SEARCH_RESULTS_DIR, search_results_for

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Reduce urllib3 retry logging noise
urllib3.disable_warnings()
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)

def press_shift_tab(driver):
    """Simulates pressing Shift+Tab."""
    try:
        actions = ActionChains(driver)
        actions.key_down(Keys.SHIFT).send_keys(Keys.TAB).key_up(Keys.SHIFT).perform()
        logging.debug("Pressed Shift+Tab")
    except Exception as e:
        logging.error(f"Error pressing Shift+Tab: {e}")

def load_cookies(driver, cookies):
    """Loads cookies into the Selenium browser."""
    try:
        if not cookies:
            logging.warning("No cookies to load.")
            return

        logging.info("Loading cookies...")
        driver.delete_all_cookies()
        cookies_loaded = 0
        
        for cookie in cookies:
            try:
                formatted_cookie = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie["domain"],
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                }
                driver.add_cookie(formatted_cookie)
                cookies_loaded += 1
            except Exception as e:
                logging.warning(f"Error adding cookie {cookie.get('name', 'unknown')}")
                continue
                
        logging.info(f"Successfully loaded {cookies_loaded} cookies")
        driver.refresh()
        time.sleep(5)
        
    except Exception as e:
        logging.error(f"Error in load_cookies: {str(e)}")
        raise


def generate_linkedin_job_url(job_title: str, settings: dict) -> str:
    """Generates LinkedIn job search URL based on job title and settings."""
    try:
        base_url = "https://www.linkedin.com/jobs/search/"
        keywords = f"%22{job_title.lower()}%22" if settings["search_type"] == "exact" else job_title.lower()
        salary_param = "&f_SB2=6" if settings["salary_range"] >= 140000 else "&f_SB2=7"
        
        # Join the work geography codes with '%2C' (URL-encoded comma)
        work_geo_param = "&f_WT=" + '%2C'.join(settings["work_geo_codes"])
        
        url = f"{base_url}?keywords={keywords}{work_geo_param}{salary_param}&geoId=103644278&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true"
        logging.info(f"Generated URL: {url}")
        return url
        
    except Exception as e:
        logging.error(f"Error generating LinkedIn URL: {e}")
        raise


def save_page_html(driver, file_name="page_source.html"):
    """Saves the entire HTML of the current page to a file for debugging."""
    try:
        page_html = driver.page_source
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(page_html)
        logging.info(f"Page HTML saved to {file_name}")
    except Exception as e:
        logging.error(f"Error saving page HTML: {e}")


def capture_debug_artifacts(driver, prefix="linkedin_search"):
    """Save HTML and screenshot for debugging when scraping fails."""
    try:
        debug_dir = str(DEBUG_DIR)
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        html_path = os.path.join(debug_dir, f"{prefix}_{timestamp}.html")
        screenshot_path = os.path.join(debug_dir, f"{prefix}_{timestamp}.png")

        save_page_html(driver, file_name=html_path)
        driver.save_screenshot(screenshot_path)
        logging.info(
            f"Saved debug artifacts: HTML -> {html_path}, Screenshot -> {screenshot_path}"
        )
    except Exception as e:
        logging.error(f"Failed to capture debug artifacts: {e}")


def locate_jobs_container(driver, timeout=15):
    """Locate the jobs list container using multiple fallback selectors."""
    selectors = [
        "div.jobs-search-two-pane__results-container ul.jobs-search__results-list",
        "ul.jobs-search__results-list",
        "div[class*='scaffold-layout__list']",
    ]

    for selector in selectors:
        try:
            logging.debug(f"Trying jobs container selector: {selector}")
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            logging.debug(f"Selector did not match: {selector}")
            continue

    raise TimeoutException("Could not locate jobs results container with known selectors")


def scrape_job_data(driver, url, max_pages=3):
    """Scrapes job data from LinkedIn."""
    jobs = []
    page = 1
    try:
        logging.info("Starting job scraping...")
        driver.get(url)
        time.sleep(5)  # Wait for initial load
        
        while page <= max_pages:
            logging.info(f"Scraping page {page}")
            
            try:
                jobs_container = locate_jobs_container(driver, timeout=15)
            except TimeoutException as e:
                logging.error(f"Unable to locate jobs container on page {page}: {e}")
                logging.error(f"Current URL: {driver.current_url}")
                capture_debug_artifacts(driver, prefix=f"jobs_list_page{page}")
                break
            
            # Scroll through the jobs list
            for i in range(5):  # Scroll in chunks
                driver.execute_script("arguments[0].scrollBy(0, 300);", jobs_container)
                time.sleep(1)
            
            # Get job cards
            job_cards = jobs_container.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
            logging.info(f"Found {len(job_cards)} job cards on page {page}")
            
            if len(job_cards) == 0:
                logging.warning(f"No job cards detected on page {page}. Saving debug snapshot.")
                capture_debug_artifacts(driver, prefix=f"jobs_list_page{page}_empty")
            
            for job in job_cards:
                try:
                    job_data = extract_job_details(job)
                    if job_data:
                        jobs.append(job_data)
                        logging.info(f"Processed job: {job_data.get('job_title', 'Unknown Title')}")
                except Exception as e:
                    logging.error(f"Error processing job card: {e}")
                    continue
            
            # Try to go to next page
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "[aria-label='View next page']")
                if not next_button.is_enabled():
                    logging.info("No more pages left")
                    break
                next_button.click()
                time.sleep(3)
                page += 1
            except Exception:
                logging.info("No more pages left")
                break
                
        logging.info(f"Completed scraping. Total jobs found: {len(jobs)}")
        return jobs
        
    except Exception as e:
        logging.error(f"Error in scrape_job_data: {e}")
        logging.error(f"Current URL during failure: {driver.current_url}")
        capture_debug_artifacts(driver, prefix="scrape_error")
        return jobs

def get_search_parameters():
    """Get search parameters from user input."""
    try:
        print("\nPlease select search parameters:")
        
        # Salary range selection
        print("\nAvailable salary ranges:")
        for i, salary in enumerate(search_parameters['salary_ranges'], 1):
            print(f"{i}. ${salary:,}")
        while True:
            try:
                salary_choice = int(input("Select salary range (number): ").strip())
                if 1 <= salary_choice <= len(search_parameters['salary_ranges']):
                    salary_range = search_parameters['salary_ranges'][salary_choice - 1]
                    break
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Job type selection
        print("\nAvailable job types:")
        for i, job_type in enumerate(search_parameters['job_types'], 1):
            print(f"{i}. {job_type.replace('_', ' ').title()}")
        while True:
            try:
                job_type_choice = int(input("Select job type (number): ").strip())
                if 1 <= job_type_choice <= len(search_parameters['job_types']):
                    job_type = search_parameters['job_types'][job_type_choice - 1]
                    break
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Search type selection
        print("\nSearch types:")
        for i, search_type in enumerate(search_parameters['search_types'], 1):
            print(f"{i}. {search_type.title()}")
        while True:
            try:
                search_type_choice = int(input("Select search type (number): ").strip())
                if 1 <= search_type_choice <= len(search_parameters['search_types']):
                    search_type = search_parameters['search_types'][search_type_choice - 1]
                    break
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Work Geography selection
        print("\nWork Geography options:")
        for key, value in search_parameters['work_geo_options'].items():
            print(f"{key}. {value['name']}")
        while True:
            try:
                work_geo_input = input("Select work geography options (comma-separated numbers, e.g., '1,3' for Remote and Onsite): ").strip()
                selections = [int(x.strip()) for x in work_geo_input.split(',')]
                valid_selections = all(1 <= x <= len(search_parameters['work_geo_options']) for x in selections)
                if valid_selections:
                    # Get the corresponding codes for the selected options
                    work_geo_codes = [search_parameters['work_geo_options'][x]['code'] for x in selections]
                    break
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter valid numbers separated by commas.")
        
        params = {
            "salary_range": salary_range,
            "job_type": job_type,
            "search_type": search_type,
            "work_geo_codes": work_geo_codes  # Store the selected codes
        }
        
        logging.info(f"Selected parameters: {params}")
        return params
        
    except Exception as e:
        logging.error(f"Error getting search parameters: {e}")
        raise

def create_search_directory(job_title):
    """Create and return the search directory path."""
    base_folder = str(SEARCH_RESULTS_DIR)
    # Replace spaces with underscores in job title
    formatted_title = job_title.lower().replace(' ', '_')
    # Remove the double folder creation - just use one level
    search_folder = os.path.join(base_folder, formatted_title)
    os.makedirs(search_folder, exist_ok=True)
    logging.info(f"Created search directory: {search_folder}")
    return search_folder

def generate_file_id():
    """Generate a unique file identifier."""
    # Create a random UUID and take first 8 characters
    random_id = str(uuid.uuid4())[:8]
    # Add timestamp for additional uniqueness
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"_{random_id}_{timestamp}"

def generate_unique_id():
    """Generate a unique ID using UUID4."""
    return str(uuid.uuid4())

def save_results(df, job_title, search_params, search_folder=None):
    """Save job results with the correct naming convention."""
    try:
        # Add unique IDs to each job record
        df['job_id'] = [generate_unique_id() for _ in range(len(df))]
        
        # Clean job title and ensure lowercase
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Use the search_folder directly instead of creating another subfolder
        if search_folder is None:
            search_folder = str(search_results_for(job_title_clean))
        job_folder = os.path.join(search_folder)
        os.makedirs(job_folder, exist_ok=True)
        
        # Generate random 5-digit number
        random_number = str(random.randint(10000, 99999))
        
        # Format the filename components (all lowercase)
        salary = f"js_{search_params['salary_range']}".lower()
        job_type = f"jt_{search_params['job_type'].lower().replace(' ', '_')}"
        search_type = f"st_{search_params['search_type'].lower()}"
        date_str = datetime.now().strftime('%Y%m%d')
        
        # Get work geography names for the selected codes
        work_geo_names = []
        for code in search_params['work_geo_codes']:
            for option in search_parameters['work_geo_options'].values():
                if option['code'] == code:
                    work_geo_names.append(option['name'].lower())
        
        work_geo_str = f"wg_{'_'.join(work_geo_names)}"  # Added 'wg_' prefix
        
        # Construct filename
        filename = f"{job_title_clean}__{salary}__{job_type}_{search_type}_{work_geo_str}_{date_str}_{random_number}"
        
        # Save both CSV and JSON versions
        csv_path = os.path.join(job_folder, f"{filename}.csv")
        json_path = os.path.join(job_folder, f"{filename}.json")
        
        # Reorder columns to have job_id first
        cols = ['job_id'] + [col for col in df.columns if col != 'job_id']
        df = df[cols]
        
        df.to_csv(csv_path, index=False)
        logging.info(f"Results saved to {csv_path}")
        
        # Save as JSON with metadata
        output_data = {
            "metadata": {
                "job_title": job_title_clean,
                "search_params": search_params,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file_id": random_number
            },
            "jobs": df.to_dict('records')
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {json_path}")
        
        return csv_path
        
    except Exception as e:
        logging.error(f"Error saving results: {e}")
        raise

def perform_linkedin_search(job_title, search_params):
    """Perform LinkedIn job search and return results as DataFrame."""
    driver = None
    try:
        logging.info(f"Starting LinkedIn search for {job_title}")
        driver = setup_driver()
        logging.info("Driver setup complete")
        
        url = generate_linkedin_job_url(job_title, search_params)
        logging.info(f"Attempting to navigate to URL: {url}")
        
        # First navigate to LinkedIn
        logging.info("Navigating to LinkedIn main page...")
        driver.get("https://www.linkedin.com")
        time.sleep(5)
        logging.info(f"Current URL before cookies: {driver.current_url}")
        capture_debug_artifacts(driver, prefix="feed_before_cookies")
        
        # Load cookies
        logging.info("Loading cookies...")
        cookies = load_cookie_data()
        load_cookies(driver, cookies)
        logging.info("Cookies loaded, waiting for page load...")
        time.sleep(5)
        logging.info(f"Current URL after cookies: {driver.current_url}")
        capture_debug_artifacts(driver, prefix="feed_after_cookies")
        
        # Now navigate to the search URL
        logging.info("Navigating to search URL...")
        driver.get(url)
        time.sleep(5)
        
        # Scrape the data
        logging.info("Starting job scraping...")
        jobs = scrape_job_data(driver, url)
        logging.info(f"Scraped {len(jobs)} jobs")
        
        if not jobs:
            logging.warning("No jobs found")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(jobs)
        logging.info(f"Created DataFrame with {len(df)} rows")
        return df
        
    except Exception as e:
        logging.error(f"Error in LinkedIn search: {e}")
        logging.error("Stack trace:", exc_info=True)
        return pd.DataFrame()
    finally:
        if driver:
            try:
                cleanup_driver(driver)
            except Exception as e:
                logging.error(f"Error closing driver: {e}")

def setup_driver():
    """Initialize and return Chrome driver with proper settings."""
    try:
        logging.info("Setting up Chrome driver via driver_utils...")
        driver = create_driver(headless=True, profile_name="linkedin_job_search")
        driver.set_window_size(1440, 8000)
        logging.info("Chrome driver initialized successfully")
        return driver
    except Exception as e:
        logging.error(f"Error initializing Chrome driver: {e}")
        raise


def get_dynamic_selectors(driver):
    """Determine the current dynamic class names by analyzing the page structure."""
    try:
        # Get the first job card to analyze
        first_job = driver.find_element(By.CSS_SELECTOR, "li[class*='occludable-update']")
        
        # Dictionary to store our dynamic selectors
        selectors = {}
        
        # Find company element by its structural position and store its class
        company_elements = first_job.find_elements(By.CSS_SELECTOR, "span[dir='ltr']")
        for element in company_elements:
            # Verify this is the company element by checking its parent or content
            if element.find_element(By.XPATH, "..").get_attribute("class").contains("artdeco-entity-lockup__subtitle"):
                selectors['company_class'] = element.get_attribute("class")
                break
                
        # Store other dynamic classes as needed
        # ... similar pattern for other elements
        
        logging.info("Successfully determined dynamic selectors")
        return selectors
        
    except Exception as e:
        logging.error(f"Error determining dynamic selectors: {e}")
        return None


def extract_job_details(job, selectors=None):
    """Extract details from a job card element."""
    try:
        # Get job title
        try:
            
            job_title_element = job.find_element(By.CSS_SELECTOR, "a[class*='job-card-container__link'] span[aria-hidden='true'] strong")
            job_title = job_title_element.text.strip()
            if not job_title:
                job_title_link = job.find_element(By.CSS_SELECTOR, "a[class*='job-card-container__link']")
                job_title = job_title_link.get_attribute("aria-label")
                job_title = job_title.replace(" with verification", "") if job_title else "Not Available"
            
        except NoSuchElementException:
            job_title = "Not Available"

        if not job_title or job_title == "Not Available":
            logging.warning(f"Could not find job title for a listing")

        # Job URL
        try:
            job_url_block = job.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
            job_url = job_url_block.get_attribute("href")
            job_url = job_url.split("?")[0]
        except NoSuchElementException:
            job_url = "Not Available"


        # Fallback selectors if dynamic ones aren't available
        default_selectors = {
            'company_class': 'dWJplLBRBAptgNcPwCBFsflKmzwrdqqy',
        }
        
        current_selectors = selectors or default_selectors
        
        # Try multiple approaches to find company name
        company_name = "Not Available"
        try:
            # Try dynamic class first
            company_element = job.find_element(By.CSS_SELECTOR, f"span[class*='{current_selectors['company_class']}']")
            company_name = company_element.text.strip()
        except NoSuchElementException:
            # Fallback approaches
            try:
                # Try by structure
                company_element = job.find_element(By.CSS_SELECTOR, "div.artdeco-entity-lockup__subtitle span")
                company_name = company_element.text.strip()
            except NoSuchElementException:
                # Try by XPath relative to job title
                company_element = job.find_element(By.XPATH, ".//div[contains(@class, 'artdeco-entity-lockup__title')]/../div[contains(@class, 'artdeco-entity-lockup__subtitle')]//span")
                company_name = company_element.text.strip()

        # Location
        try:
            location = job.find_element(By.CSS_SELECTOR, "ul.job-card-container__metadata-wrapper li span").text.strip()
        except NoSuchElementException:
            location = "Not Available"

        # Salary Range
        try:
            salary_tag = job.find_element(By.CSS_SELECTOR, "div.artdeco-entity-lockup__metadata span")
            salary_range = salary_tag.text.strip()
        except NoSuchElementException:
            salary_range = "N/A"

        # Remote Status
        try:
            remote_status_element = job.find_element(By.XPATH, ".//*[contains(text(), 'Remote') or contains(text(), 'Onsite') or contains(text(), 'Hybrid')]")
            remote_status = remote_status_element.text.strip()
        except NoSuchElementException:
            remote_status = "Not Specified"

        return {
            "company_title": company_name,
            "job_title": job_title,
            "job_url": job_url,
            "salary_range": salary_range,
            "location": location,
            "remote_status": remote_status
        }
    except Exception as e:
        logging.error(f"Error extracting job details: {e}")
        return None

def handle_pagination(driver, current_page):
    """Handle pagination and return True if next page exists."""
    try:
        next_page_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='View next page']"))
        )
        next_page_button.click()
        logging.info(f"Navigated to page {current_page + 1}")
        return True
    except NoSuchElementException:
        logging.info(f"No next page button found on page {current_page}")
        return False
    except Exception as e:
        logging.error(f"Error navigating to next page: {e}")
        return False

def get_job_title():
    """Get job title from user input."""
    while True:
        job_title = input("\nEnter the job title to search for: ").strip()
        if job_title:
            confirm = input(f"Confirm job title '{job_title}'? (y/n): ").lower()
            if confirm == 'y':
                return job_title
        print("Please enter a valid job title.")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='LinkedIn Job Search')
    parser.add_argument('--job_title', required=True, help='Job title to search for')
    return parser.parse_args()

def main():
    parser = argparse.ArgumentParser(description='LinkedIn Job Search')
    parser.add_argument('--job_title', required=True, help='Job title to search for')
    args = parser.parse_args()

    job_title = args.job_title
    logging.info(f"Starting job search for: {job_title}")

    # Initialize metrics tracker
    metrics_tracker = JobMetricsTracker()

    # Get search parameters from user
    logging.info("Getting search parameters...")
    search_params = get_search_parameters()
    logging.info(f"Search parameters received: {search_params}")
    
    # Create search directory
    logging.info("Creating search directory...")
    search_folder = create_search_directory(job_title)
    logging.info(f"Search folder created: {search_folder}")
    
    # Perform LinkedIn search
    logging.info("Starting LinkedIn search...")
    df = perform_linkedin_search(job_title, search_params)
    logging.info("LinkedIn search completed")
    
    if df is not None and not df.empty:
        logging.info(f"Found {len(df)} jobs. Saving results...")
        # Save results using the same search_folder
        saved_path = save_results(df, job_title, search_params, search_folder)
        
        # Save run metrics
        metrics_tracker.save_run_metrics(
            job_title=job_title,
            total_jobs=len(df),
            salary_range=search_params.get('salary_range', 'Not specified'),
            job_type=search_params.get('job_type', 'Not specified'),
            search_type=search_params.get('search_type', 'Not specified'),
            geography=search_params.get('geography', 'Not specified')
        )
        
        # Update jobs aggregation
        metrics_tracker.update_jobs_aggregation(
            job_title=job_title,
            new_jobs=df.to_dict('records')
        )
        
        return saved_path
    else:
        logging.warning("No results found or DataFrame is empty")
        return None

if __name__ == "__main__":
    try:
        # Ensure output is properly flushed
        sys.stdout.flush()
        main()
    except Exception as e:
        logging.error(f"Script failed: {e}")
        logging.error("Stack trace:", exc_info=True)
        sys.exit(1)