"""
Greenhouse job application form filler.
"""
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .base import BaseFormFiller

class GreenhouseFormFiller(BaseFormFiller):
    """Form filler for Greenhouse job boards."""
    
    def detect_application_page(self):
        """Detect if we're on a Greenhouse application page."""
        try:
            # Greenhouse application pages typically have these indicators
            indicators = [
                "input[type='file']",  # File upload for resume
                "input[name*='first_name']",
                "input[name*='last_name']",
                "input[name*='email']",
                "form[action*='greenhouse']"
            ]
            
            for indicator in indicators:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, indicator)
                    return True
                except:
                    continue
            
            return False
        except:
            return False
    
    def fill_application(self, job_url, job_data=None):
        """
        Fill out a Greenhouse job application.
        
        Args:
            job_url: URL of the job posting
            job_data: Optional dictionary with job information
            
        Returns:
            dict: Result with 'success' (bool), 'message' (str), and 'submitted' (bool)
        """
        self.logger.info(f"Starting Greenhouse application fill for: {job_url}")
        
        try:
            # Navigate to the application page
            self.driver.get(job_url)
            self.random_delay(2, 4)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check if we need to click "Apply" button first
            apply_buttons = [
                (By.CSS_SELECTOR, "a[href*='apply']"),
                (By.CSS_SELECTOR, "button:contains('Apply')"),
                (By.XPATH, "//a[contains(text(), 'Apply')]"),
                (By.XPATH, "//button[contains(text(), 'Apply')]")
            ]
            
            for by, selector in apply_buttons:
                try:
                    button = self.driver.find_element(by, selector)
                    if button.is_displayed():
                        self.logger.info("Found Apply button, clicking...")
                        self.click_button((by, selector))
                        self.random_delay(2, 4)
                        break
                except:
                    continue
            
            # Wait for application form to appear
            self.random_delay(2, 3)
            
            # Fill required fields
            personal_info = self.config.get('personal_info', {})
            app_info = self.config.get('application_info', {})
            
            # Fill basic information
            self._fill_basic_info(personal_info)
            self._fill_application_details(app_info)
            
            # Fill work experience section (uses resume components)
            work_exp_filled = self.fill_work_experience_section(max_entries=3)
            self.logger.info(f"Filled {work_exp_filled} work experience entries")
            
            # Fill education section (uses resume components)
            edu_filled = self.fill_education_section(max_entries=2)
            self.logger.info(f"Filled {edu_filled} education entries")
            
            # Handle custom questions
            self._handle_custom_questions(job_data)
            
            # Upload resume
            resume_path = app_info.get('resume_path')
            if resume_path:
                self._upload_resume(resume_path)
            
            # Upload cover letter if provided
            cover_letter_path = app_info.get('cover_letter_path')
            if cover_letter_path:
                self._upload_cover_letter(cover_letter_path)
            
            # Handle voluntary disclosures
            self._handle_voluntary_disclosures()
            
            # Check if form is ready to submit
            submitted = False
            submit_button = self._find_submit_button()
            
            if submit_button:
                self.logger.info("Application form filled successfully. Submit button found.")
                # Note: We don't auto-submit by default for safety
                # Uncomment the line below to enable auto-submission
                # submitted = self._submit_application()
                return {
                    'success': True,
                    'message': 'Application form filled successfully. Ready for review.',
                    'submitted': submitted
                }
            else:
                return {
                    'success': False,
                    'message': 'Could not find submit button. Form may be incomplete.',
                    'submitted': False
                }
                
        except Exception as e:
            self.logger.error(f"Error filling Greenhouse application: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'submitted': False
            }
    
    def _fill_basic_info(self, personal_info):
        """Fill basic personal information fields."""
        # First Name
        first_name_selectors = [
            (By.CSS_SELECTOR, "input[name='first_name']"),
            (By.CSS_SELECTOR, "input[id*='first_name']"),
            (By.CSS_SELECTOR, "input[id*='firstName']"),
            (By.CSS_SELECTOR, "input[placeholder*='First Name']")
        ]
        self.fill_text_field(first_name_selectors, personal_info.get('first_name', ''))
        
        # Last Name
        last_name_selectors = [
            (By.CSS_SELECTOR, "input[name='last_name']"),
            (By.CSS_SELECTOR, "input[id*='last_name']"),
            (By.CSS_SELECTOR, "input[id*='lastName']"),
            (By.CSS_SELECTOR, "input[placeholder*='Last Name']")
        ]
        self.fill_text_field(last_name_selectors, personal_info.get('last_name', ''))
        
        # Email
        email_selectors = [
            (By.CSS_SELECTOR, "input[name='email']"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[id*='email']")
        ]
        self.fill_text_field(email_selectors, personal_info.get('email', ''))
        
        # Phone
        phone_selectors = [
            (By.CSS_SELECTOR, "input[name='phone']"),
            (By.CSS_SELECTOR, "input[type='tel']"),
            (By.CSS_SELECTOR, "input[id*='phone']")
        ]
        self.fill_text_field(phone_selectors, personal_info.get('phone', ''))
        
        # Preferred Name (if field exists)
        preferred_name = personal_info.get('preferred_name', '')
        if preferred_name:
            preferred_name_selectors = [
                (By.CSS_SELECTOR, "input[name='preferred_name']"),
                (By.CSS_SELECTOR, "input[id*='preferred_name']")
            ]
            self.fill_text_field(preferred_name_selectors, preferred_name)
        
        # LinkedIn Profile
        linkedin = personal_info.get('linkedin_profile', '')
        if linkedin:
            linkedin_selectors = [
                (By.CSS_SELECTOR, "input[name*='linkedin']"),
                (By.CSS_SELECTOR, "input[id*='linkedin']")
            ]
            self.fill_text_field(linkedin_selectors, linkedin)
        
        # Location/Zip Code
        zip_code = personal_info.get('zip_code', '')
        if zip_code:
            zip_selectors = [
                (By.CSS_SELECTOR, "input[name*='zip']"),
                (By.CSS_SELECTOR, "input[name*='postal']"),
                (By.CSS_SELECTOR, "input[id*='zip']")
            ]
            self.fill_text_field(zip_selectors, zip_code)
    
    def _fill_application_details(self, app_info):
        """Fill application-specific details."""
        # How did you hear about this opportunity?
        how_did_you_hear = app_info.get('how_did_you_hear', 'LinkedIn')
        hear_selectors = [
            (By.CSS_SELECTOR, "select[name*='hear']"),
            (By.CSS_SELECTOR, "select[id*='hear']")
        ]
        self.select_dropdown(hear_selectors, how_did_you_hear, match_type='contains')
        
        # Work authorization
        authorized = app_info.get('legally_authorized_to_work', 'Yes')
        auth_selectors = [
            (By.CSS_SELECTOR, "select[name*='authorized']"),
            (By.CSS_SELECTOR, "select[name*='work']")
        ]
        self.select_dropdown(auth_selectors, authorized, match_type='contains')
        
        # Visa sponsorship
        requires_sponsorship = app_info.get('require_visa_sponsorship', 'No')
        visa_selectors = [
            (By.CSS_SELECTOR, "select[name*='visa']"),
            (By.CSS_SELECTOR, "select[name*='sponsor']")
        ]
        self.select_dropdown(visa_selectors, requires_sponsorship, match_type='contains')
        
        # Metro area
        metro_area = app_info.get('metro_area', '')
        if metro_area:
            metro_selectors = [
                (By.CSS_SELECTOR, "select[name*='metro']"),
                (By.CSS_SELECTOR, "select[name*='location']")
            ]
            self.select_dropdown(metro_selectors, metro_area, match_type='contains')
    
    def _upload_resume(self, resume_path):
        """Upload resume file."""
        resume_selectors = [
            (By.CSS_SELECTOR, "input[type='file'][name*='resume']"),
            (By.CSS_SELECTOR, "input[type='file'][name*='cv']"),
            (By.CSS_SELECTOR, "input[type='file']"),
            (By.CSS_SELECTOR, "input[accept*='pdf']")
        ]
        
        # Try to find and click the file upload area first (some sites have custom uploaders)
        upload_area_selectors = [
            (By.CSS_SELECTOR, "label[for*='resume']"),
            (By.CSS_SELECTOR, "label[for*='cv']"),
            (By.CSS_SELECTOR, "div[class*='upload']"),
            (By.CSS_SELECTOR, "button[class*='upload']")
        ]
        
        for by, selector in upload_area_selectors:
            try:
                element = self.driver.find_element(by, selector)
                if element.is_displayed():
                    element.click()
                    self.random_delay(0.5, 1.0)
                    break
            except:
                continue
        
        return self.upload_file(resume_selectors, resume_path)
    
    def _upload_cover_letter(self, cover_letter_path):
        """Upload cover letter file."""
        cover_letter_selectors = [
            (By.CSS_SELECTOR, "input[type='file'][name*='cover']"),
            (By.CSS_SELECTOR, "input[type='file'][name*='letter']")
        ]
        return self.upload_file(cover_letter_selectors, cover_letter_path)
    
    def _handle_custom_questions(self, job_data):
        """Handle custom questions on the application form."""
        custom_answers = self.config.get('custom_answers', {})
        
        # Look for textarea fields (often used for custom questions)
        try:
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for textarea in textareas:
                # Try to identify the question from nearby labels
                try:
                    label = textarea.find_element(By.XPATH, "./preceding-sibling::label | ./ancestor::label")
                    label_text = label.text.lower()
                    
                    # Match question to answer
                    for question_pattern, answer in custom_answers.items():
                        if question_pattern.lower() in label_text and answer:
                            self.fill_text_field([(By.CSS_SELECTOR, f"textarea")], answer)
                            break
                except:
                    continue
        except:
            pass
        
        # Handle specific question types (e.g., PEO experience question from the example)
        if job_data:
            # Example: Handle PEO industry experience question
            peo_question_selectors = [
                (By.XPATH, "//label[contains(text(), 'PEO industry')]/following-sibling::textarea"),
                (By.XPATH, "//label[contains(text(), 'PEO')]/following-sibling::textarea"),
                (By.XPATH, "//textarea[preceding-sibling::label[contains(text(), 'PEO')]]")
            ]
            
            peo_answer = custom_answers.get('PEO industry experience', '')
            if peo_answer:
                self.fill_text_field(peo_question_selectors, peo_answer)
    
    def _handle_voluntary_disclosures(self):
        """Handle voluntary self-identification questions."""
        disclosures = self.config.get('voluntary_disclosures', {})
        
        if not disclosures:
            return
        
        # Gender identity
        if disclosures.get('gender_identity'):
            gender_selectors = [
                (By.CSS_SELECTOR, "select[name*='gender']"),
                (By.CSS_SELECTOR, "select[id*='gender']")
            ]
            self.select_dropdown(gender_selectors, disclosures['gender_identity'])
        
        # Veteran status
        if disclosures.get('veteran_status'):
            veteran_selectors = [
                (By.CSS_SELECTOR, "select[name*='veteran']"),
                (By.CSS_SELECTOR, "select[id*='veteran']")
            ]
            self.select_dropdown(veteran_selectors, disclosures['veteran_status'])
        
        # Disability
        if disclosures.get('disability'):
            disability_selectors = [
                (By.CSS_SELECTOR, "select[name*='disability']"),
                (By.CSS_SELECTOR, "select[id*='disability']")
            ]
            self.select_dropdown(disability_selectors, disclosures['disability'])
    
    def _find_submit_button(self):
        """Find the submit button on the form."""
        submit_selectors = [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Submit')]"),
            (By.XPATH, "//button[contains(text(), 'Submit Application')]"),
            (By.XPATH, "//button[contains(text(), 'Apply')]")
        ]
        
        return self.find_element_safe(submit_selectors, timeout=5)
    
    def _submit_application(self):
        """Submit the application (use with caution)."""
        submit_button = self._find_submit_button()
        if submit_button:
            self.logger.warning("AUTO-SUBMITTING APPLICATION - This will submit the form!")
            self.click_button([(By.CSS_SELECTOR, "button[type='submit']")], wait_after=True)
            self.random_delay(3, 5)
            return True
        return False


