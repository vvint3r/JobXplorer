import time
import random
import pandas as pd
import re
import json
import logging
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import subprocess
from job_extraction.utils import load_cookie_data
from pyvirtualdisplay import Display
from job_metrics_tracker import JobMetricsTracker
import uuid
import shutil
from job_extraction.driver_utils import create_driver, cleanup_driver
from paths import DEBUG_DIR, job_details_for

# Set up logging
logging.basicConfig(
    level=logging.INFO,  # Set to INFO to suppress DEBUG messages
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def df_to_dict_safe(df):
    """Convert DataFrame to dict, replacing NaT, NaN, and Timestamp values for JSON serialization."""
    # Make a copy to avoid modifying the original
    df_clean = df.copy()
    
    # Replace NaT (Not a Time) values with None
    df_clean = df_clean.replace({pd.NaT: None})
    # Replace NaN values with None
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    
    # Convert to dict first
    records = df_clean.to_dict('records')
    
    # Post-process to convert Timestamp objects to strings and handle any remaining NaT/NaN
    for record in records:
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif pd.isna(value) or value is pd.NaT:
                record[key] = None
    
    return records

def random_delay(base=1, variance=1):
    time.sleep(base + random.uniform(0, variance))

def get_chrome_version():
    """Get the version of Chrome installed on the system."""
    try:
        version = subprocess.check_output(['google-chrome', '--version'])
        return version.decode().strip().split()[-1]
    except:
        return None

def parse_cookies(raw_cookie_data):
    try:
        return json.loads(raw_cookie_data)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {e}")
        return None

def load_cookies(driver, cookies):
    if not cookies:
        logging.warning("No cookies to load.")
        return

    driver.get("https://www.linkedin.com/feed/")
    time.sleep(2)
    
    # Delete existing cookies before adding new ones
    driver.delete_all_cookies()
    
    cookies_loaded = 0
    for cookie in cookies:
        try:
            driver.add_cookie({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"],
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
            })
            cookies_loaded += 1
        except KeyError as e:
            logging.error(f"Skipping cookie due to missing field: {e}")
    
    logging.info(f"Loaded {cookies_loaded} cookies")
    driver.refresh()
    time.sleep(3)


def capture_url_debug_snapshot(driver, prefix="apply_debug"):
    """Capture debug snapshot for application URL extraction debugging."""
    try:
        debug_dir = str(DEBUG_DIR)
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        html_path = os.path.join(debug_dir, f"{prefix}_{timestamp}.html")
        screenshot_path = os.path.join(debug_dir, f"{prefix}_{timestamp}.png")
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot(screenshot_path)
        logging.info(f"Saved debug artifacts: {html_path}, {screenshot_path}")
    except Exception as e:
        logging.warning(f"Failed to capture debug snapshot: {e}")


def extract_application_url(driver, wait):
    """Extract the application URL by clicking the Apply button on LinkedIn job posting."""
    original_window = None
    original_url = None
    application_url = None
    
    try:
        # Store original window and URL
        original_window = driver.current_window_handle
        original_url = driver.current_url
        
        logging.info(f"Starting application URL extraction for: {original_url}")
        
        # Try multiple selectors to find the Apply button
        apply_button_selectors = [
            'button#jobs-apply-button-id',
            'button.jobs-apply-button',
            'button[aria-label*="Apply"][aria-label*="company website"]',
            'button[data-live-test-job-apply-button]',
            'div.jobs-apply-button--top-card button',
            'button.artdeco-button--primary[aria-label*="Apply"]'
        ]
        
        apply_button = None
        for selector in apply_button_selectors:
            try:
                # Use shorter timeout for each attempt
                short_wait = WebDriverWait(driver, 3)
                apply_button = short_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                if apply_button:
                    logging.info(f"Found Apply button using selector: {selector}")
                    break
            except Exception as e:
                logging.debug(f"Selector {selector} did not find button: {e}")
                continue
        
        if not apply_button:
            logging.warning("Apply button not found with any selector")
            # Try one more time with a broader search
            try:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in all_buttons:
                    btn_text = btn.text.strip().lower()
                    aria_label = btn.get_attribute("aria-label") or ""
                    if ("apply" in btn_text or "apply" in aria_label.lower()) and "company website" in aria_label.lower():
                        apply_button = btn
                        logging.info("Found Apply button using broader search")
                        break
            except Exception as e:
                logging.debug(f"Broader button search failed: {e}")
        
        if not apply_button:
            logging.warning("Apply button not found after all attempts - capturing debug snapshot")
            capture_url_debug_snapshot(driver, "apply_button_not_found")
            return "Not Available"
        
        # Check if this is an "Easy Apply" button - these are LinkedIn's internal applications, not external URLs
        try:
            button_text = apply_button.text.strip().lower()
            aria_label = (apply_button.get_attribute("aria-label") or "").lower()
            
            if "easy apply" in button_text or "easy apply" in aria_label:
                logging.info("Found 'Easy Apply' button - this is LinkedIn internal, skipping external URL extraction")
                return "Easy Apply (LinkedIn)"
            
            # Also check if it's missing "company website" in aria-label (indicates external)
            if "company website" not in aria_label and "apply" in button_text:
                # Double-check by looking for external link icon
                try:
                    external_icon = apply_button.find_element(By.CSS_SELECTOR, 'svg[data-test-icon="link-external-small"]')
                    if not external_icon:
                        logging.info("No external link icon found - likely not an external application")
                except:
                    # No external link icon means this might be Easy Apply
                    if "company website" not in aria_label:
                        logging.info("Button lacks external URL indicators - likely Easy Apply")
                        return "Easy Apply (LinkedIn)"
        except Exception as e:
            logging.debug(f"Error checking button type: {e}")
        
        # Verify button is visible and enabled
        try:
            is_displayed = apply_button.is_displayed()
            is_enabled = apply_button.is_enabled()
            logging.info(f"Button visibility check - displayed: {is_displayed}, enabled: {is_enabled}")
            if not is_displayed:
                logging.warning("Apply button is not visible")
                return "Not Available"
            if not is_enabled:
                logging.warning("Apply button is not enabled")
                return "Not Available"
        except Exception as e:
            logging.warning(f"Could not verify button state: {e}")
        
        # First, try to extract URL from button attributes (non-destructive)
        # Check if button is wrapped in an anchor tag
        try:
            parent_anchor = apply_button.find_element(By.XPATH, "./ancestor::a[@href]")
            href = parent_anchor.get_attribute("href")
            if href and href.startswith("http") and "linkedin.com" not in href:
                return href
        except:
            pass
        
        # Check for data attributes
        data_attributes = ['data-href', 'data-url', 'data-apply-url', 'data-application-url']
        for attr in data_attributes:
            try:
                url = apply_button.get_attribute(attr)
                if url and url.startswith("http") and "linkedin.com" not in url:
                    return url
            except:
                continue
        
        # If URL not found in attributes, click the button to reveal it
        try:
            # Scroll button into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", apply_button)
            time.sleep(0.5)
            
            # Get current window handles and URL before clicking
            windows_before = set(driver.window_handles)
            original_url_before_click = driver.current_url
            
            logging.info("Attempting to click Apply button...")
            logging.info(f"Button text: {apply_button.text.strip()}")
            logging.info(f"Button aria-label: {apply_button.get_attribute('aria-label')}")
            
            # Inject JavaScript to intercept window.open calls
            intercept_script = """
            window._linkedinApplicationUrl = null;
            var originalOpen = window.open;
            window.open = function(url, name, features) {
                window._linkedinApplicationUrl = url;
                console.log('Intercepted window.open with URL:', url);
                return originalOpen.apply(this, arguments);
            };
            """
            driver.execute_script(intercept_script)
            
            # Try multiple click methods
            click_successful = False
            try:
                # Method 1: JavaScript click (most reliable)
                driver.execute_script("arguments[0].click();", apply_button)
                click_successful = True
                logging.info("Clicked button using JavaScript")
            except Exception as e1:
                logging.warning(f"JavaScript click failed: {e1}")
                try:
                    # Method 2: Regular click
                    apply_button.click()
                    click_successful = True
                    logging.info("Clicked button using regular click")
                except Exception as e2:
                    logging.warning(f"Regular click failed: {e2}")
                    try:
                        # Method 3: ActionChains click
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(driver).move_to_element(apply_button).click().perform()
                        click_successful = True
                        logging.info("Clicked button using ActionChains")
                    except Exception as e3:
                        logging.warning(f"All click methods failed: {e3}")
            
            # Check if we intercepted a window.open call
            time.sleep(0.5)  # Brief wait for JavaScript to execute
            try:
                intercepted_url = driver.execute_script("return window._linkedinApplicationUrl;")
                if intercepted_url:
                    logging.info(f"Intercepted application URL from window.open: {intercepted_url}")
                    application_url = intercepted_url
                    # Still need to check if window opened to close it
                    time.sleep(1)
                    windows_after = set(driver.window_handles)
                    new_windows = windows_after - windows_before
                    if new_windows:
                        new_window = new_windows.pop()
                        driver.switch_to.window(new_window)
                        driver.close()
                        driver.switch_to.window(original_window)
                    return application_url
            except Exception as e:
                logging.debug(f"Could not check intercepted URL: {e}")
            
            if not click_successful:
                logging.warning("Could not click Apply button")
                return "Not Available"
            
            # Check if LinkedIn is asking for authentication
            time.sleep(1)  # Brief wait to see if auth modal appears
            try:
                # Check for sign-in prompts or modals
                sign_in_selectors = [
                    'div[data-test-modal="sign-in-modal"]',
                    'div.sign-in-modal',
                    'button[data-test-id="sign-in-button"]',
                    'a[href*="/login"]'
                ]
                for selector in sign_in_selectors:
                    try:
                        sign_in_element = driver.find_element(By.CSS_SELECTOR, selector)
                        if sign_in_element.is_displayed():
                            logging.warning("LinkedIn sign-in required - cannot extract application URL without authentication")
                            return "Not Available"
                    except:
                        continue
            except:
                pass
            
            # Wait and check for new window/tab (check multiple times)
            max_wait_time = 10  # Increased wait time for new windows
            check_interval = 0.3
            waited = 0
            
            logging.info(f"Waiting up to {max_wait_time} seconds for new window or navigation...")
            logging.info(f"Windows before click: {len(windows_before)} - {list(windows_before)}")
            
            while waited < max_wait_time:
                time.sleep(check_interval)
                waited += check_interval
                
                # Check for new windows
                try:
                    windows_after = set(driver.window_handles)
                    new_windows = windows_after - windows_before
                    
                    if new_windows:
                        logging.info(f"New window detected! Total windows: {len(windows_after)}, New: {len(new_windows)}")
                        # New window opened - switch to it and get URL
                        new_window = new_windows.pop()
                        logging.info(f"Switching to new window: {new_window}")
                        driver.switch_to.window(new_window)
                        time.sleep(2)  # Wait for page to load
                        application_url = driver.current_url
                        logging.info(f"Found application URL in new window: {application_url}")
                        
                        # Validate it's not a LinkedIn page
                        if "linkedin.com" in application_url:
                            logging.warning(f"New window opened but still on LinkedIn: {application_url}")
                            # Close this window and continue waiting
                            driver.close()
                            driver.switch_to.window(original_window)
                            continue
                        
                        # Close the new window and switch back
                        driver.close()
                        driver.switch_to.window(original_window)
                        logging.info("Closed new window and switched back to original")
                        break
                except Exception as window_error:
                    logging.debug(f"Error checking windows: {window_error}")
                
                # Check if current URL changed (navigation in same window)
                try:
                    current_url = driver.current_url
                    if current_url != original_url_before_click:
                        logging.info(f"URL changed from {original_url_before_click} to {current_url}")
                        if "linkedin.com" not in current_url:
                            # Navigated to external URL
                            application_url = current_url
                            logging.info(f"Found application URL via navigation: {application_url}")
                            # Navigate back to original page
                            driver.get(original_url)
                            time.sleep(2)
                            break
                        elif current_url != original_url:
                            # URL changed but still on LinkedIn - might be redirecting
                            logging.debug(f"URL changed to LinkedIn page: {current_url}")
                except Exception as url_error:
                    logging.debug(f"Error checking URL: {url_error}")
            
            if waited >= max_wait_time and not application_url:
                logging.warning(f"Timeout after {max_wait_time} seconds - no new window or navigation detected")
                # Check one more time for windows (sometimes they open slowly)
                try:
                    final_windows = set(driver.window_handles)
                    final_new_windows = final_windows - windows_before
                    if final_new_windows:
                        logging.info(f"Found new window on final check: {len(final_new_windows)}")
                        new_window = final_new_windows.pop()
                        driver.switch_to.window(new_window)
                        time.sleep(1)
                        application_url = driver.current_url
                        if "linkedin.com" not in application_url:
                            logging.info(f"Found application URL in delayed new window: {application_url}")
                            driver.close()
                            driver.switch_to.window(original_window)
                        else:
                            driver.close()
                            driver.switch_to.window(original_window)
                            application_url = None
                except Exception as e:
                    logging.debug(f"Error in final window check: {e}")
            
            # If still no URL found, check for redirects or links that appeared
            if not application_url:
                # Wait a bit more for async redirects
                time.sleep(2)
                final_url = driver.current_url
                
                if final_url != original_url_before_click and "linkedin.com" not in final_url:
                    application_url = final_url
                    logging.info(f"Found application URL after additional wait: {application_url}")
                    driver.get(original_url)
                    time.sleep(2)
                else:
                    # Try to find external links that might have appeared
                    try:
                        # Look for links in modals or overlays that might have appeared
                        # First check if a modal/overlay appeared
                        try:
                            # Check for common modal/overlay patterns
                            modal_selectors = [
                                'div[role="dialog"]',
                                'div.modal',
                                'div.overlay',
                                'div[class*="modal"]',
                                'div[class*="overlay"]',
                                'aside[role="dialog"]'
                            ]
                            for modal_selector in modal_selectors:
                                try:
                                    modal = driver.find_element(By.CSS_SELECTOR, modal_selector)
                                    if modal.is_displayed():
                                        logging.info(f"Found modal/overlay: {modal_selector}")
                                        # Look for external links in the modal
                                        modal_links = modal.find_elements(By.CSS_SELECTOR, "a[href*='http']:not([href*='linkedin.com'])")
                                        for link in modal_links:
                                            href = link.get_attribute("href")
                                            if href and href.startswith("http"):
                                                if any(keyword in href.lower() for keyword in ["taleo", "greenhouse", "apply", "job", "careers", "ats", "workday", "tbe"]):
                                                    application_url = href
                                                    logging.info(f"Found application URL in modal link: {application_url}")
                                                    # Close modal if possible
                                                    try:
                                                        close_btn = modal.find_element(By.CSS_SELECTOR, "button[aria-label*='close'], button[aria-label*='Close'], .artdeco-modal__dismiss")
                                                        close_btn.click()
                                                        time.sleep(0.5)
                                                    except:
                                                        pass
                                                    break
                                        if application_url:
                                            break
                                except:
                                    continue
                        except:
                            pass
                        
                        # Also check all external links on the page
                        if not application_url:
                            external_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='http']:not([href*='linkedin.com'])")
                            for link in external_links[:20]:  # Check first 20 external links
                                href = link.get_attribute("href")
                                if href and href.startswith("http"):
                                    href_lower = href.lower()
                                    # Exclude common non-application URLs
                                    exclude_keywords = ["benefits", "facebook-life", "work-life", "careers/life", "about", "culture", "privacy", "terms", "cookie"]
                                    if any(exclude in href_lower for exclude in exclude_keywords):
                                        continue
                                    
                                    # Check if it looks like an application URL
                                    application_keywords = [
                                        "taleo", "greenhouse", "apply", "job", "careers", "ats", "workday", 
                                        "tbe", "viewrequisition", "requisition", "application", "candidate", 
                                        "recruiting", "hire", "position", "opening", "vacancy", "phf.tbe"
                                    ]
                                    if any(keyword in href_lower for keyword in application_keywords):
                                        application_url = href
                                        logging.info(f"Found application URL in link element: {application_url}")
                                        break
                    except Exception as e:
                        logging.debug(f"Error searching for external links: {e}")
            
            if application_url and application_url.startswith("http"):
                # Final validation - exclude common non-application URLs
                url_lower = application_url.lower()
                exclude_patterns = [
                    "benefits", "facebook-life", "work-life", "careers/life", "about", 
                    "culture", "privacy", "terms", "cookie", "careers/benefits"
                ]
                if any(pattern in url_lower for pattern in exclude_patterns):
                    logging.warning(f"Extracted URL appears to be a non-application page: {application_url}")
                    return "Not Available"
                
                # Don't clean up query parameters - they might be important (like source tracking)
                logging.info(f"Successfully extracted application URL: {application_url}")
                return application_url
            else:
                logging.warning("Could not extract application URL after clicking Apply button")
                capture_url_debug_snapshot(driver, "apply_click_no_url")
                # Try one more approach - check if button has onclick handler that contains URL
                try:
                    onclick = apply_button.get_attribute("onclick")
                    if onclick:
                        # Extract URL from onclick handler
                        url_patterns = [
                            r'https?://[^\s\'"\)]+',
                            r'window\.open\([\'"](https?://[^\'"]+)[\'"]',
                            r'location\.href\s*=\s*[\'"](https?://[^\'"]+)[\'"]'
                        ]
                        for pattern in url_patterns:
                            match = re.search(pattern, onclick)
                            if match:
                                potential_url = match.group(1) if len(match.groups()) > 0 else match.group(0)
                                if "linkedin.com" not in potential_url:
                                    logging.info(f"Found application URL in onclick handler: {potential_url}")
                                    return potential_url
                except Exception as e:
                    logging.debug(f"Error checking onclick handler: {e}")
                
                return "Not Available"
                
        except Exception as click_error:
            logging.warning(f"Error clicking Apply button: {click_error}")
            # Make sure we're back on the original window
            try:
                if original_window and original_window in driver.window_handles:
                    driver.switch_to.window(original_window)
            except:
                pass
            return "Not Available"
        
    except Exception as e:
        logging.warning(f"Error extracting application URL: {e}")
        # Ensure we're back on the original window
        try:
            if original_window and original_window in driver.window_handles:
                driver.switch_to.window(original_window)
        except:
            pass
        return "Not Available"

def get_job_details(driver, url):
    """Get details for a single job posting."""
    max_retries = 2  # Reduced retries since we're using batch processing
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logging.info(f"Processing URL: {url}")
            
            # Initial page load with delay
            driver.get(url)
            time.sleep(random.uniform(3, 5))
            
            wait = WebDriverWait(driver, 15)
            
            # Initialize variables
            job_title = company_name = job_description = date_posted = location = salary = remote_status = days_since_posted = application_url = None
            
            # Extract job details with minimal delays
            try:
                show_more_button = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, '.feed-shared-inline-show-more-text__see-more-less-toggle')))
                driver.execute_script("arguments[0].click();", show_more_button)
            except Exception as e:
                logging.warning(f"Show more button not found: {e}")
            
            # Extract all fields with appropriate waits
            job_title = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1'))).text.strip()
            
            try:
                job_description_element = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.job-details-about-the-job-module__description div.feed-shared-inline-show-more-text')))
                job_description = job_description_element.text.replace("-", " ").strip()
                job_description = re.sub(r'\s+', ' ', job_description)
            except:
                job_description = "-"
                
            try:
                company_name = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.job-details-jobs-unified-top-card__company-name a'))).text.strip()
            except:
                company_name = "-"
                
            try:
                # Target the tertiary description container where date info is located
                tertiary_container = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.job-details-jobs-unified-top-card__tertiary-description-container')))
                
                # Find spans that contain date/time information
                date_text = None
                spans = tertiary_container.find_elements(By.CSS_SELECTOR, 'span.tvm__text.tvm__text--low-emphasis')
                
                # Time pattern that matches "X hours/days/weeks/months ago" with or without "Posted/Reposted"
                time_ago_pattern = re.compile(r'(\d+)\s*(hour|day|week|month)s?\s*ago', re.IGNORECASE)
                
                for span in spans:
                    span_text = span.text.strip()
                    logging.debug(f"Checking span text for date: '{span_text}'")
                    
                    # Check if this span contains a time-ago pattern
                    if time_ago_pattern.search(span_text):
                        date_text = span_text
                        logging.info(f"Found time-ago pattern in span: '{date_text}'")
                        break
                    # Also check for "Posted" or "Reposted" prefix
                    elif 'reposted' in span_text.lower() or 'posted' in span_text.lower():
                        date_text = span_text
                        logging.info(f"Found posted/reposted in span: '{date_text}'")
                        break
                
                # If not found in spans, try searching the entire container text
                if not date_text:
                    container_text = tertiary_container.text
                    logging.debug(f"Container text: '{container_text}'")
                    
                    # Look for time-ago pattern anywhere in container
                    time_match = time_ago_pattern.search(container_text)
                    if time_match:
                        # Get the full match with surrounding context
                        match_start = max(0, time_match.start() - 10)
                        match_end = min(len(container_text), time_match.end())
                        date_text = container_text[match_start:match_end].strip()
                        # Clean up - remove leading punctuation
                        date_text = re.sub(r'^[·\s]+', '', date_text)
                        logging.info(f"Found time-ago pattern in container: '{date_text}'")
                
                if date_text:
                    logging.info(f"Found date text: {date_text}")
                    date_posted = parse_date_posted(date_text)
                    # Calculate days since posted
                    days_since_posted = calculate_days_since_posted(date_posted)
                    logging.info(f"Parsed date_posted: {date_posted}, days_since_posted: {days_since_posted}")
                else:
                    logging.warning("Could not find date text in tertiary container")
                    date_posted = None
                    days_since_posted = None
            except Exception as e:
                logging.warning(f"Could not extract date posted: {e}", exc_info=True)
                date_posted = None
                days_since_posted = None
                
            try:
                location = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.job-details-jobs-unified-top-card__primary-description-container span.tvm__text'))).text.strip()
            except:
                location = "-"
                
            try:
                salary = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.job-details-preferences-and-skills__pill span.ui-label.text-body-small"))).text.strip()
            except:
                salary = "-"
                
            try:
                # Look for the job-details-fit-level-preferences container first
                preferences_container = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.job-details-fit-level-preferences")))
                
                # Find buttons within the container that contain location type text
                buttons = preferences_container.find_elements(By.TAG_NAME, "button")
                remote_status = "Onsite"  # Default fallback
                
                for button in buttons:
                    button_text = button.text.strip()
                    # Check if button contains location type keywords
                    if any(keyword in button_text for keyword in ["Remote", "Hybrid", "Onsite"]):
                        # Extract just the location type (may have other text like "Full-time")
                        if "Remote" in button_text:
                            remote_status = "Remote"
                            break
                        elif "Hybrid" in button_text:
                            remote_status = "Hybrid"
                            break
                        elif "Onsite" in button_text:
                            remote_status = "Onsite"
                            break
                
            except Exception as e:
                logging.warning(f"Could not extract remote status: {e}")
                remote_status = "Onsite"
            
            # Extract application URL from Apply button
            try:
                logging.info("Attempting to extract application URL...")
                application_url = extract_application_url(driver, wait)
                logging.info(f"Application URL extraction result: {application_url}")
            except Exception as e:
                logging.warning(f"Could not extract application URL: {e}", exc_info=True)
                application_url = "Not Available"
            
            return job_title, company_name, job_description, date_posted, location, remote_status, salary, url, days_since_posted, application_url
            
        except Exception as e:
            retry_count += 1
            logging.warning(f"Attempt {retry_count} failed for URL {url}: {e}")
            if retry_count < max_retries:
                time.sleep(random.uniform(5, 8))
            else:
                logging.error(f"Failed to retrieve details after {max_retries} attempts")
                return "-", "-", "-", None, "-", "Onsite", "-", url, None, "Not Available"

def parse_date_posted(date_text):
    """Parse the date posted text into a timestamp."""
    try:
        if not date_text:
            return None
            
        today = pd.Timestamp('today')
        date_text_lower = date_text.lower()
        
        # Handle hours (case-insensitive, handle plural)
        if 'hour' in date_text_lower:
            match = re.search(r'(\d+)\s*hour', date_text_lower)
            if match:
                hours = int(match.group(1))
                return today - pd.Timedelta(hours=hours)
        # Handle days (case-insensitive, handle plural)
        elif 'day' in date_text_lower:
            match = re.search(r'(\d+)\s*day', date_text_lower)
            if match:
                days = int(match.group(1))
                return today - pd.Timedelta(days=days)
        # Handle weeks (case-insensitive, handle plural)
        elif 'week' in date_text_lower:
            match = re.search(r'(\d+)\s*week', date_text_lower)
            if match:
                weeks = int(match.group(1))
                return today - pd.Timedelta(weeks=weeks)
        # Handle months (case-insensitive, handle plural)
        elif 'month' in date_text_lower:
            match = re.search(r'(\d+)\s*month', date_text_lower)
            if match:
                months = int(match.group(1))
                return today - pd.DateOffset(months=months)
        
        logging.warning(f"Could not parse date format: {date_text}")
        return None
    except Exception as e:
        logging.warning(f"Could not parse date: {date_text} - {e}", exc_info=True)
        return None

def calculate_days_since_posted(date_posted):
    """Calculate the number of days between the extraction date and the posting date."""
    if date_posted is None:
        return None
    try:
        today = pd.Timestamp('today').normalize()
        posted_date = pd.Timestamp(date_posted).normalize()
        days_diff = (today - posted_date).days
        return days_diff
    except Exception as e:
        logging.warning(f"Could not calculate days since posted: {e}")
        return None

def load_job_links(filename):
    """Load job links from the CSV file."""
    try:
        # Check if input file exists
        if not os.path.exists(filename):
            logging.warning(f"Input file {filename[:25]} does not exist.")
            return pd.DataFrame(), []  # Return empty DataFrame and list
            
        # Load the CSV file
        df = pd.read_csv(filename)
        links = df['job_url'].tolist() if 'job_url' in df.columns else []
        logging.info(f"Successfully loaded {len(links)} job links from {filename[:25]}")
        return df, links
        
    except Exception as e:
        logging.error(f"Error loading job links: {e}")
        return pd.DataFrame(), []  # Return empty DataFrame and list on error

def generate_unique_id():
    """Generate a unique ID using UUID4."""
    return str(uuid.uuid4())

def save_job_details(df, job_title):
    """Save job details with updated directory and formatting."""
    try:
        # Add unique IDs to each job record
        df['job_id'] = [generate_unique_id() for _ in range(len(df))]
        
        # Clean job title for directory name
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Create base folder structure with job_details subdirectory
        folder_store = str(job_details_for(job_title_clean))
        os.makedirs(folder_store, exist_ok=True)
        
        # Generate filename with date
        current_date = datetime.now().strftime('%Y%m%d')
        
        # Generate random 5-digit number
        random_number = str(random.randint(10000, 99999))
        
        # Construct the filename (all lowercase) without company name
        base_filename = f"{job_title_clean}_details_{current_date}_{random_number}"
        
        # Reorder columns to have job_id first
        cols = ['job_id'] + [col for col in df.columns if col != 'job_id']
        df = df[cols]
        
        # Save both CSV and JSON versions
        csv_path = os.path.join(folder_store, f"{base_filename}.csv")
        json_path = os.path.join(folder_store, f"{base_filename}.json")
        
        df.to_csv(csv_path, index=False)
        logging.info(f"Results saved to {csv_path}")
        
        # Convert NaT to None or a string
        df = df.where(pd.notnull(df), None)
        
        # Convert datetime columns to strings
        for col in df.select_dtypes(include=['datetime64[ns]']).columns:
            df[col] = df[col].astype(str)
        
        # Save as JSON with metadata (keeping company in metadata only)
        company_name = df['company'].iloc[0] if not df.empty else 'unknown'
        company_name_clean = company_name.lower().replace(' ', '_').replace(',', '').replace('.', '')
        
        output_data = {
            "metadata": {
                "job_title": job_title_clean,
                "company": company_name_clean,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file_id": random_number
            },
            "jobs": df_to_dict_safe(df)
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {json_path}")
        
        return csv_path
        
    except Exception as e:
        logging.error(f"Error saving job details: {e}")
        raise

def process_job_links(links, output_dir, job_title, test_limit=None):
    """Process job links in batches with appropriate delays."""
    try:
        if test_limit and len(links) > test_limit:
            links = links[:test_limit]
            logging.info(f"TESTING MODE: Limiting to {test_limit} jobs for testing")
        
        # Initialize driver once
        driver = create_driver()
        load_cookies(driver, load_cookie_data())
        
        # Process in small batches
        batch_size = 3
        results = []
        
        for i in range(0, len(links), batch_size):
            batch = links[i:i + batch_size]
            logging.info(f"Processing batch {i//batch_size + 1} of {(len(links) + batch_size - 1)//batch_size}")
            
            # Process each URL in the batch
            for url in batch:
                try:
                    job_details = get_job_details(driver, url)
                    if job_details:
                        results.append(job_details)
                except Exception as e:
                    logging.error(f"Error processing URL {url}: {e}")
                    continue
                
                # Add delay between jobs within batch (5-10 seconds)
                time.sleep(random.uniform(5, 10))
            
            # Add longer delay between batches (20-30 seconds)
            if i + batch_size < len(links):
                delay = random.uniform(20, 30)
                logging.info(f"Taking a break between batches ({delay:.1f} seconds)...")
                time.sleep(delay)
        
        # Create results DataFrame
        df_results = pd.DataFrame(results, columns=[
            'job_title', 'company', 'description', 'date_posted',
            'location', 'remote', 'salary', 'job_url', 'days_since_posted', 'application_url'
        ])
        
        # Save results in job_details directory
        job_title_clean = job_title.lower().replace(' ', '_')
        folder_store = str(job_details_for(job_title_clean))
        os.makedirs(folder_store, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{job_title_clean}_job_details_{timestamp}.csv"
        output_path = os.path.join(folder_store, output_filename)
        
        # Save both CSV and JSON
        df_results.to_csv(output_path, index=False)
        logging.info(f"Results saved to {output_path}")
        
        # Save JSON version
        json_path = output_path.replace('.csv', '.json')
        output_data = {
            "metadata": {
                "job_title": job_title_clean,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_jobs": len(df_results)
            },
            "jobs": df_to_dict_safe(df_results)
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {json_path}")
        
        return df_results
        
    except Exception as e:
        logging.error(f"Error in process_job_links: {e}")
        return pd.DataFrame()
    finally:
        try:
            cleanup_driver(driver)
        except:
            pass

def main(job_title, input_filename, test_limit=None):
    """Main function with cleaned job title."""
    driver = None
    try:
        # Clean job title
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Initialize metrics tracker
        metrics_tracker = JobMetricsTracker()
        
        # Load job links from input file
        logging.info(f"Loading job links from {input_filename}")
        df, links = load_job_links(input_filename)
        if not links:
            logging.warning("No job links found to process.")
            return

        # Initialize driver
        logging.info("Initializing Chrome driver...")
        driver = create_driver()
        
        try:
            # Load cookies
            logging.info("Loading cookies...")
            cookies = load_cookie_data()
            if cookies:
                load_cookies(driver, cookies)
            else:
                logging.warning("No cookies loaded")
            
            # Process job links and collect detailed information
            if test_limit and len(links) > test_limit:
                links = links[:test_limit]
                logging.info(f"TESTING MODE: Limiting to {test_limit} jobs for testing")
            
            logging.info(f"Starting to process {len(links)} job links...")
            detailed_jobs = []
            for link in links:
                job_details = get_job_details(driver, link)
                if job_details:
                    # Convert tuple to dictionary
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
            
            # Create DataFrame from detailed jobs
            if detailed_jobs:
                df_results = pd.DataFrame(detailed_jobs)
                
                # Save to job details directory
                folder_store = str(job_details_for(job_title_clean))
                os.makedirs(folder_store, exist_ok=True)
                
                # Generate filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"{job_title_clean}_job_details_{timestamp}.csv"
                output_path = os.path.join(folder_store, output_filename)
                
                # Save CSV
                df_results.to_csv(output_path, index=False)
                logging.info(f"Results saved to {output_path}")
                
                # Save JSON version
                json_path = output_path.replace('.csv', '.json')
                output_data = {
                    "metadata": {
                        "job_title": job_title_clean,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "total_jobs": len(df_results)
                    },
                    "jobs": df_to_dict_safe(df_results)
                }
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                logging.info(f"Results saved to {json_path}")
                
                # Update metrics
                metrics_tracker.update_jobs_aggregation(
                    job_title=job_title,
                    new_jobs=detailed_jobs
                )
            
        finally:
            if driver:
                logging.info("Closing Chrome driver...")
                cleanup_driver(driver)
                
    except Exception as e:
        logging.error(f"Error in main processing: {str(e)}")
        if driver:
            try:
                cleanup_driver(driver)
            except:
                pass
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_title", required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--test_limit", type=int, default=None,
                        help="Limit number of job links processed (optional).")
    args = parser.parse_args()
    
    main(args.job_title, args.filename, test_limit=args.test_limit)
