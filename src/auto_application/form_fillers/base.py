"""
Base class for form fillers.
"""
import time
import random
import logging
from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..resume_components_loader import ResumeComponentsLoader, load_resume_components


class BaseFormFiller(ABC):
    """Base class for all form fillers."""
    
    def __init__(self, driver, config):
        """
        Initialize the form filler.
        
        Args:
            driver: Selenium WebDriver instance
            config: User configuration dictionary
        """
        self.driver = driver
        self.config = config
        self.wait = WebDriverWait(driver, 15)
        self.logger = logging.getLogger(__name__)
        
        # Load resume components if available
        self.resume_components = None
        try:
            self.resume_components = load_resume_components(config)
            if self.resume_components.work_experience_count > 0:
                self.logger.info(f"Loaded resume with {self.resume_components.work_experience_count} work experiences")
        except Exception as e:
            self.logger.warning(f"Could not load resume components: {e}")
    
    def random_delay(self, min_seconds=0.5, max_seconds=2.0):
        """Add random delay to mimic human behavior."""
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    def find_element_safe(self, selectors, timeout=10):
        """
        Try multiple selectors to find an element.
        
        Args:
            selectors: List of tuples (By, selector) or single tuple
            timeout: Maximum time to wait
            
        Returns:
            WebElement or None
        """
        if not isinstance(selectors, list):
            selectors = [selectors]
        
        for by, selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                return element
            except TimeoutException:
                continue
        
        return None
    
    def fill_text_field(self, selectors, value, clear_first=True):
        """
        Fill a text input field.
        
        Args:
            selectors: CSS selector or list of selectors
            value: Value to fill
            clear_first: Whether to clear the field first
            
        Returns:
            bool: True if successful
        """
        if not value:
            return False
        
        element = self.find_element_safe(selectors if isinstance(selectors, list) else [selectors])
        if not element:
            self.logger.warning(f"Could not find text field with selectors: {selectors}")
            return False
        
        try:
            if clear_first:
                element.clear()
            self.random_delay(0.2, 0.5)
            element.send_keys(value)
            self.random_delay(0.3, 0.7)
            return True
        except Exception as e:
            self.logger.error(f"Error filling text field: {e}")
            return False
    
    def select_dropdown(self, selectors, value, match_type='exact'):
        """
        Select an option from a dropdown.
        
        Args:
            selectors: CSS selector or list of selectors
            value: Value to select
            match_type: 'exact', 'contains', or 'starts_with'
            
        Returns:
            bool: True if successful
        """
        if not value:
            return False
        
        element = self.find_element_safe(selectors if isinstance(selectors, list) else [selectors])
        if not element:
            self.logger.warning(f"Could not find dropdown with selectors: {selectors}")
            return False
        
        try:
            # Try using Select class first (for standard HTML selects)
            try:
                select = Select(element)
                options = select.options
                for option in options:
                    option_text = option.text.strip()
                    if match_type == 'exact' and option_text == value:
                        select.select_by_visible_text(value)
                        self.random_delay(0.3, 0.7)
                        return True
                    elif match_type == 'contains' and value in option_text:
                        select.select_by_visible_text(option_text)
                        self.random_delay(0.3, 0.7)
                        return True
                    elif match_type == 'starts_with' and option_text.startswith(value):
                        select.select_by_visible_text(option_text)
                        self.random_delay(0.3, 0.7)
                        return True
            except:
                # If Select doesn't work, try clicking and selecting
                element.click()
                self.random_delay(0.5, 1.0)
                
                # Look for option elements
                option_selectors = [
                    (By.XPATH, f"//option[contains(text(), '{value}')]"),
                    (By.XPATH, f"//li[contains(text(), '{value}')]"),
                    (By.XPATH, f"//div[contains(text(), '{value}')]")
                ]
                
                option = self.find_element_safe(option_selectors, timeout=5)
                if option:
                    option.click()
                    self.random_delay(0.3, 0.7)
                    return True
            
            self.logger.warning(f"Could not find option '{value}' in dropdown")
            return False
        except Exception as e:
            self.logger.error(f"Error selecting dropdown: {e}")
            return False
    
    def upload_file(self, selectors, file_path):
        """
        Upload a file to a file input.
        
        Args:
            selectors: CSS selector or list of selectors
            file_path: Path to the file to upload
            
        Returns:
            bool: True if successful
        """
        import os
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
        
        element = self.find_element_safe(selectors if isinstance(selectors, list) else [selectors])
        if not element:
            self.logger.warning(f"Could not find file input with selectors: {selectors}")
            return False
        
        try:
            # File inputs typically have type="file"
            if element.tag_name != 'input' or element.get_attribute('type') != 'file':
                # Try to find a hidden file input and trigger click on visible element
                self.logger.warning("Element is not a file input, attempting workaround")
            
            element.send_keys(file_path)
            self.random_delay(1.0, 2.0)  # File uploads take time
            return True
        except Exception as e:
            self.logger.error(f"Error uploading file: {e}")
            return False
    
    def click_button(self, selectors, wait_after=True):
        """
        Click a button or clickable element.
        
        Args:
            selectors: CSS selector or list of selectors
            wait_after: Whether to wait after clicking
            
        Returns:
            bool: True if successful
        """
        element = self.find_element_safe(selectors if isinstance(selectors, list) else [selectors])
        if not element:
            self.logger.warning(f"Could not find button with selectors: {selectors}")
            return False
        
        try:
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            self.random_delay(0.3, 0.7)
            
            # Try JavaScript click first (more reliable)
            self.driver.execute_script("arguments[0].click();", element)
            if wait_after:
                self.random_delay(1.0, 2.0)
            return True
        except Exception as e:
            self.logger.error(f"Error clicking button: {e}")
            return False
    
    def check_checkbox(self, selectors, checked=True):
        """
        Check or uncheck a checkbox.
        
        Args:
            selectors: CSS selector or list of selectors
            checked: True to check, False to uncheck
            
        Returns:
            bool: True if successful
        """
        element = self.find_element_safe(selectors if isinstance(selectors, list) else [selectors])
        if not element:
            self.logger.warning(f"Could not find checkbox with selectors: {selectors}")
            return False
        
        try:
            current_state = element.is_selected()
            if current_state != checked:
                element.click()
                self.random_delay(0.3, 0.7)
            return True
        except Exception as e:
            self.logger.error(f"Error checking checkbox: {e}")
            return False
    
    # ==================== APPLY BUTTON METHODS ====================
    
    def find_and_click_apply_button(self, wait_after: bool = True) -> bool:
        """
        Find and click the "Apply" button on a job posting page.
        
        Handles various button text patterns like:
        - "Apply"
        - "Apply Now"
        - "Apply for this job"
        - "Apply for this position"
        - "Start Application"
        - "Submit Application"
        - "Apply on company website"
        
        Args:
            wait_after: Whether to wait after clicking
            
        Returns:
            bool: True if Apply button was found and clicked
        """
        self.logger.info("Looking for Apply button...")
        
        # Comprehensive list of Apply button selectors, ordered by specificity
        apply_button_selectors = [
            # Data-automation-id (Workday specific)
            (By.CSS_SELECTOR, "button[data-automation-id='jobPostingApplyButton']"),
            (By.CSS_SELECTOR, "a[data-automation-id='jobPostingApplyButton']"),
            
            # Common class patterns
            (By.CSS_SELECTOR, "button.jobs-apply-button"),
            (By.CSS_SELECTOR, "a.jobs-apply-button"),
            (By.CSS_SELECTOR, "button[class*='apply-button']"),
            (By.CSS_SELECTOR, "a[class*='apply-button']"),
            (By.CSS_SELECTOR, "button[class*='applyBtn']"),
            (By.CSS_SELECTOR, "a[class*='applyBtn']"),
            
            # Href patterns (links to application)
            (By.CSS_SELECTOR, "a[href*='/apply']"),
            (By.CSS_SELECTOR, "a[href*='apply.']"),
            
            # ID patterns
            (By.CSS_SELECTOR, "button[id*='apply']"),
            (By.CSS_SELECTOR, "a[id*='apply']"),
            
            # ARIA label patterns
            (By.CSS_SELECTOR, "button[aria-label*='Apply']"),
            (By.CSS_SELECTOR, "a[aria-label*='Apply']"),
            
            # Text-based XPath selectors (case-insensitive)
            (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply now')]"),
            (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply now')]"),
            (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply for')]"),
            (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply for')]"),
            (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start application')]"),
            (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start application')]"),
            
            # Generic "Apply" text (last resort - may match too broadly)
            (By.XPATH, "//button[normalize-space(text())='Apply']"),
            (By.XPATH, "//a[normalize-space(text())='Apply']"),
            (By.XPATH, "//button[contains(text(), 'Apply')]"),
            (By.XPATH, "//a[contains(text(), 'Apply')]"),
            
            # Input submit buttons
            (By.CSS_SELECTOR, "input[type='submit'][value*='Apply']"),
            
            # Span inside button/anchor (common pattern)
            (By.XPATH, "//button[.//span[contains(text(), 'Apply')]]"),
            (By.XPATH, "//a[.//span[contains(text(), 'Apply')]]"),
        ]
        
        for by, selector in apply_button_selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    # Check if element is visible and enabled
                    if element.is_displayed():
                        button_text = element.text.strip() or element.get_attribute('aria-label') or ''
                        self.logger.info(f"Found Apply button: '{button_text}' using selector: {selector}")
                        
                        # Skip "Easy Apply" buttons (LinkedIn internal)
                        if 'easy apply' in button_text.lower():
                            self.logger.info("Skipping 'Easy Apply' button (LinkedIn internal)")
                            continue
                        
                        # Scroll into view and click
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            self.random_delay(0.5, 1.0)
                            
                            # Try JavaScript click first
                            self.driver.execute_script("arguments[0].click();", element)
                            self.logger.info("Clicked Apply button successfully")
                            
                            if wait_after:
                                self.random_delay(2.0, 4.0)
                            
                            return True
                        except Exception as click_error:
                            self.logger.warning(f"Failed to click with JS, trying regular click: {click_error}")
                            try:
                                element.click()
                                if wait_after:
                                    self.random_delay(2.0, 4.0)
                                return True
                            except Exception as e:
                                self.logger.warning(f"Regular click also failed: {e}")
                                continue
            except Exception as e:
                continue
        
        self.logger.warning("Could not find Apply button on page")
        return False
    
    def is_on_application_form(self) -> bool:
        """
        Check if we're currently on an application form page (not just a job posting).
        
        Returns:
            bool: True if on an application form
        """
        form_indicators = [
            # File upload (resume)
            (By.CSS_SELECTOR, "input[type='file']"),
            # Common form field patterns
            (By.CSS_SELECTOR, "input[name*='first_name']"),
            (By.CSS_SELECTOR, "input[name*='firstName']"),
            (By.CSS_SELECTOR, "input[name*='email'][type='email']"),
            # Form element itself
            (By.CSS_SELECTOR, "form[action*='apply']"),
            (By.CSS_SELECTOR, "form[action*='submit']"),
            # Workday specific
            (By.CSS_SELECTOR, "div[data-automation-id='formField']"),
            # Submit button
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Submit')]"),
        ]
        
        indicators_found = 0
        for by, selector in form_indicators:
            try:
                elements = self.driver.find_elements(by, selector)
                if elements:
                    indicators_found += 1
                    if indicators_found >= 2:  # At least 2 indicators suggest we're on a form
                        return True
            except:
                continue
        
        return False
    
    def navigate_to_application_form(self, job_url: str) -> bool:
        """
        Navigate to the application form from a job posting URL.
        
        This handles the common case where the job URL shows a job description
        and we need to click "Apply" to get to the actual application form.
        
        Args:
            job_url: The URL of the job posting
            
        Returns:
            bool: True if successfully navigated to application form
        """
        self.logger.info(f"Navigating to: {job_url}")
        self.driver.get(job_url)
        self.random_delay(3, 5)  # Allow page to fully load
        
        # Check if we're already on the application form
        if self.is_on_application_form():
            self.logger.info("Already on application form")
            return True
        
        # Try to find and click Apply button
        if self.find_and_click_apply_button():
            self.random_delay(2, 4)  # Wait for application form to load
            
            # Verify we're now on the application form
            if self.is_on_application_form():
                self.logger.info("Successfully navigated to application form")
                return True
            else:
                self.logger.warning("Clicked Apply but may not be on application form yet")
                # Some sites require additional steps (sign in, etc.)
                return True  # Still return True as we clicked Apply
        
        self.logger.warning("Could not navigate to application form")
        return False
    
    @abstractmethod
    def fill_application(self, job_url, job_data=None):
        """
        Fill out the job application form.
        
        Args:
            job_url: URL of the job posting
            job_data: Optional dictionary with job information
            
        Returns:
            dict: Result with 'success' (bool) and 'message' (str)
        """
        pass
    
    @abstractmethod
    def detect_application_page(self):
        """
        Detect if we're on an application page.
        
        Returns:
            bool: True if on application page
        """
        pass
    
    # ==================== WORK EXPERIENCE METHODS ====================
    
    def fill_work_experience_section(self, max_entries: int = 3):
        """
        Fill work experience section with data from resume components.
        
        Args:
            max_entries: Maximum number of work experience entries to fill
            
        Returns:
            int: Number of entries successfully filled
        """
        if not self.resume_components:
            self.logger.warning("No resume components loaded - cannot fill work experience")
            return 0
        
        filled = 0
        entries_to_fill = min(max_entries, self.resume_components.work_experience_count)
        
        for i in range(entries_to_fill):
            try:
                if self._fill_single_work_experience(i):
                    filled += 1
                    self.logger.info(f"Filled work experience entry {i + 1}")
                    
                    # Check if we need to click "Add Another" button for next entry
                    if i < entries_to_fill - 1:
                        self._click_add_another_experience()
                        self.random_delay(1.0, 2.0)
            except Exception as e:
                self.logger.error(f"Error filling work experience entry {i}: {e}")
        
        return filled
    
    def _fill_single_work_experience(self, index: int) -> bool:
        """
        Fill a single work experience entry.
        
        Args:
            index: Index of the work experience in resume components
            
        Returns:
            bool: True if successful
        """
        if not self.resume_components:
            return False
        
        data = self.resume_components.get_work_exp_form_data(index)
        if not data:
            return False
        
        success = True
        
        # Job Title
        job_title_selectors = [
            (By.CSS_SELECTOR, f"input[name*='job_title'][data-index='{index}']"),
            (By.CSS_SELECTOR, "input[name*='job_title']"),
            (By.CSS_SELECTOR, "input[name*='title']"),
            (By.CSS_SELECTOR, "input[id*='jobTitle']"),
            (By.CSS_SELECTOR, "input[id*='job-title']"),
            (By.CSS_SELECTOR, "input[placeholder*='Job Title']"),
            (By.CSS_SELECTOR, "input[placeholder*='Title']"),
            (By.XPATH, "//label[contains(text(), 'Job Title')]/following-sibling::input"),
            (By.XPATH, "//label[contains(text(), 'Title')]/following::input[1]")
        ]
        if not self.fill_text_field(job_title_selectors, data['job_title']):
            self.logger.warning(f"Could not fill job title for entry {index}")
            success = False
        
        # Company
        company_selectors = [
            (By.CSS_SELECTOR, f"input[name*='company'][data-index='{index}']"),
            (By.CSS_SELECTOR, "input[name*='company']"),
            (By.CSS_SELECTOR, "input[name*='employer']"),
            (By.CSS_SELECTOR, "input[id*='company']"),
            (By.CSS_SELECTOR, "input[id*='employer']"),
            (By.CSS_SELECTOR, "input[placeholder*='Company']"),
            (By.CSS_SELECTOR, "input[placeholder*='Employer']"),
            (By.XPATH, "//label[contains(text(), 'Company')]/following-sibling::input"),
            (By.XPATH, "//label[contains(text(), 'Employer')]/following::input[1]")
        ]
        if not self.fill_text_field(company_selectors, data['company']):
            self.logger.warning(f"Could not fill company for entry {index}")
            success = False
        
        # Currently work here checkbox
        if data['currently_work_here']:
            current_job_selectors = [
                (By.CSS_SELECTOR, "input[type='checkbox'][name*='current']"),
                (By.CSS_SELECTOR, "input[type='checkbox'][id*='current']"),
                (By.XPATH, "//input[@type='checkbox'][following-sibling::*[contains(text(), 'currently')]]"),
                (By.XPATH, "//label[contains(text(), 'currently')]/input[@type='checkbox']")
            ]
            self.check_checkbox(current_job_selectors, checked=True)
        
        # From date - Month
        from_month_selectors = [
            (By.CSS_SELECTOR, "select[name*='start_month']"),
            (By.CSS_SELECTOR, "select[name*='from_month']"),
            (By.CSS_SELECTOR, "select[id*='startMonth']"),
            (By.XPATH, "//label[contains(text(), 'From')]/following::select[1]")
        ]
        self._select_month(from_month_selectors, data['from_month'])
        
        # From date - Year
        from_year_selectors = [
            (By.CSS_SELECTOR, "select[name*='start_year']"),
            (By.CSS_SELECTOR, "select[name*='from_year']"),
            (By.CSS_SELECTOR, "select[id*='startYear']"),
            (By.CSS_SELECTOR, "input[name*='start_year']"),
            (By.XPATH, "//label[contains(text(), 'From')]/following::select[2]"),
            (By.XPATH, "//label[contains(text(), 'From')]/following::input[contains(@name, 'year')]")
        ]
        self._fill_year(from_year_selectors, data['from_year'])
        
        # To date (if not currently working)
        if not data['currently_work_here']:
            to_month_selectors = [
                (By.CSS_SELECTOR, "select[name*='end_month']"),
                (By.CSS_SELECTOR, "select[name*='to_month']"),
                (By.CSS_SELECTOR, "select[id*='endMonth']"),
                (By.XPATH, "//label[contains(text(), 'To')]/following::select[1]")
            ]
            self._select_month(to_month_selectors, data['to_month'])
            
            to_year_selectors = [
                (By.CSS_SELECTOR, "select[name*='end_year']"),
                (By.CSS_SELECTOR, "select[name*='to_year']"),
                (By.CSS_SELECTOR, "select[id*='endYear']"),
                (By.CSS_SELECTOR, "input[name*='end_year']"),
                (By.XPATH, "//label[contains(text(), 'To')]/following::select[2]")
            ]
            self._fill_year(to_year_selectors, data['to_year'])
        
        # Role Description
        description_selectors = [
            (By.CSS_SELECTOR, "textarea[name*='description']"),
            (By.CSS_SELECTOR, "textarea[name*='responsibilities']"),
            (By.CSS_SELECTOR, "textarea[id*='description']"),
            (By.CSS_SELECTOR, "textarea[placeholder*='description']"),
            (By.XPATH, "//label[contains(text(), 'Description')]/following::textarea[1]"),
            (By.XPATH, "//label[contains(text(), 'Responsibilities')]/following::textarea[1]")
        ]
        self.fill_text_field(description_selectors, data['role_description'])
        
        return success
    
    def _click_add_another_experience(self):
        """Click the 'Add Another' button for work experience."""
        add_selectors = [
            (By.XPATH, "//button[contains(text(), 'Add Another')]"),
            (By.XPATH, "//button[contains(text(), 'Add Work Experience')]"),
            (By.XPATH, "//a[contains(text(), 'Add Another')]"),
            (By.CSS_SELECTOR, "button[class*='add-experience']"),
            (By.CSS_SELECTOR, "a[class*='add-experience']")
        ]
        return self.click_button(add_selectors, wait_after=True)
    
    # ==================== EDUCATION METHODS ====================
    
    def fill_education_section(self, max_entries: int = 2):
        """
        Fill education section with data from resume components.
        
        Args:
            max_entries: Maximum number of education entries to fill
            
        Returns:
            int: Number of entries successfully filled
        """
        if not self.resume_components:
            self.logger.warning("No resume components loaded - cannot fill education")
            return 0
        
        filled = 0
        entries_to_fill = min(max_entries, self.resume_components.education_count)
        
        for i in range(entries_to_fill):
            try:
                if self._fill_single_education(i):
                    filled += 1
                    self.logger.info(f"Filled education entry {i + 1}")
                    
                    # Check if we need to click "Add Another" button for next entry
                    if i < entries_to_fill - 1:
                        self._click_add_another_education()
                        self.random_delay(1.0, 2.0)
            except Exception as e:
                self.logger.error(f"Error filling education entry {i}: {e}")
        
        return filled
    
    def _fill_single_education(self, index: int) -> bool:
        """
        Fill a single education entry.
        
        Args:
            index: Index of the education in resume components
            
        Returns:
            bool: True if successful
        """
        if not self.resume_components:
            return False
        
        data = self.resume_components.get_edu_form_data(index)
        if not data:
            return False
        
        success = True
        
        # School/University
        school_selectors = [
            (By.CSS_SELECTOR, f"input[name*='school'][data-index='{index}']"),
            (By.CSS_SELECTOR, "input[name*='school']"),
            (By.CSS_SELECTOR, "input[name*='university']"),
            (By.CSS_SELECTOR, "input[name*='institution']"),
            (By.CSS_SELECTOR, "input[id*='school']"),
            (By.CSS_SELECTOR, "input[id*='university']"),
            (By.CSS_SELECTOR, "input[placeholder*='School']"),
            (By.CSS_SELECTOR, "input[placeholder*='University']"),
            (By.XPATH, "//label[contains(text(), 'School')]/following-sibling::input"),
            (By.XPATH, "//label[contains(text(), 'University')]/following::input[1]")
        ]
        if not self.fill_text_field(school_selectors, data['school']):
            self.logger.warning(f"Could not fill school for entry {index}")
            success = False
        
        # Degree - try dropdown first, then text field
        degree_dropdown_selectors = [
            (By.CSS_SELECTOR, "select[name*='degree']"),
            (By.CSS_SELECTOR, "select[id*='degree']")
        ]
        degree_text_selectors = [
            (By.CSS_SELECTOR, "input[name*='degree']"),
            (By.CSS_SELECTOR, "input[id*='degree']"),
            (By.CSS_SELECTOR, "input[placeholder*='Degree']"),
            (By.XPATH, "//label[contains(text(), 'Degree')]/following::input[1]")
        ]
        
        # Try to find degree dropdown or text field
        if not self.select_dropdown(degree_dropdown_selectors, data['degree'], match_type='contains'):
            self.fill_text_field(degree_text_selectors, data['degree_with_field'])
        
        # Field of Study (Major)
        field_selectors = [
            (By.CSS_SELECTOR, "input[name*='field']"),
            (By.CSS_SELECTOR, "input[name*='major']"),
            (By.CSS_SELECTOR, "input[id*='field']"),
            (By.CSS_SELECTOR, "input[id*='major']"),
            (By.CSS_SELECTOR, "input[placeholder*='Field']"),
            (By.CSS_SELECTOR, "input[placeholder*='Major']"),
            (By.XPATH, "//label[contains(text(), 'Field')]/following::input[1]"),
            (By.XPATH, "//label[contains(text(), 'Major')]/following::input[1]")
        ]
        self.fill_text_field(field_selectors, data['field_of_study'])
        
        # From Year
        from_year_selectors = [
            (By.CSS_SELECTOR, "select[name*='start_year']"),
            (By.CSS_SELECTOR, "select[name*='from_year']"),
            (By.CSS_SELECTOR, "input[name*='start_year']"),
            (By.XPATH, "//label[contains(text(), 'From')]/following::select[1]")
        ]
        self._fill_year(from_year_selectors, data['from_year'])
        
        # To Year (Graduation Year)
        to_year_selectors = [
            (By.CSS_SELECTOR, "select[name*='end_year']"),
            (By.CSS_SELECTOR, "select[name*='to_year']"),
            (By.CSS_SELECTOR, "select[name*='graduation']"),
            (By.CSS_SELECTOR, "input[name*='end_year']"),
            (By.CSS_SELECTOR, "input[name*='graduation']"),
            (By.XPATH, "//label[contains(text(), 'To')]/following::select[1]"),
            (By.XPATH, "//label[contains(text(), 'Graduation')]/following::select[1]")
        ]
        self._fill_year(to_year_selectors, data['to_year'])
        
        # GPA (if available and field exists)
        if data.get('gpa'):
            gpa_selectors = [
                (By.CSS_SELECTOR, "input[name*='gpa']"),
                (By.CSS_SELECTOR, "input[id*='gpa']"),
                (By.CSS_SELECTOR, "input[placeholder*='GPA']")
            ]
            self.fill_text_field(gpa_selectors, data['gpa'])
        
        return success
    
    def _click_add_another_education(self):
        """Click the 'Add Another' button for education."""
        add_selectors = [
            (By.XPATH, "//button[contains(text(), 'Add Another')]"),
            (By.XPATH, "//button[contains(text(), 'Add Education')]"),
            (By.XPATH, "//a[contains(text(), 'Add Another')]"),
            (By.CSS_SELECTOR, "button[class*='add-education']"),
            (By.CSS_SELECTOR, "a[class*='add-education']")
        ]
        return self.click_button(add_selectors, wait_after=True)
    
    # ==================== DATE HELPER METHODS ====================
    
    def _select_month(self, selectors, month_num: str):
        """
        Select a month from a dropdown.
        
        Args:
            selectors: List of selector tuples
            month_num: Month number as string ('01' to '12')
        """
        if not month_num:
            return False
        
        # Month name mapping for text-based dropdowns
        month_names = {
            '01': 'January', '02': 'February', '03': 'March', '04': 'April',
            '05': 'May', '06': 'June', '07': 'July', '08': 'August',
            '09': 'September', '10': 'October', '11': 'November', '12': 'December'
        }
        
        month_name = month_names.get(month_num, '')
        
        # Try selecting by month name first, then by number
        if not self.select_dropdown(selectors, month_name, match_type='contains'):
            return self.select_dropdown(selectors, month_num, match_type='contains')
        return True
    
    def _fill_year(self, selectors, year: str):
        """
        Fill a year field (dropdown or text input).
        
        Args:
            selectors: List of selector tuples
            year: Year as string (e.g., '2023')
        """
        if not year:
            return False
        
        # Try as dropdown first
        if self.select_dropdown(selectors, year, match_type='exact'):
            return True
        
        # Fall back to text field
        return self.fill_text_field(selectors, year)


