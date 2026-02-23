"""
Workday job application form filler.

Workday has a distinct multi-step application process with specific field patterns.

7-Step Workday Application Flow:
    Step 1A: Create Account/Sign In
        - Click "Apply" button
        - Enter email/username and password
        - Click "Create" or "Sign In" button
    Step 1B: (After clicking) - may land on sign-in page
        - Enter Email Address
        - Enter Password  
        - Click "Sign In"
    Step 2: My Information
        - Personal info (name, email, phone, address)
    Step 3: My Experience
        - Work experience from resume components
    Step 4: Application Questions (1 of 2)
        - Work authorization, sponsorship, etc.
    Step 5: Application Questions (2 of 2)
        - Additional custom questions
    Step 6: Voluntary Disclosures
        - Gender, veteran status, disability, etc.
    Step 7: Review
        - Review and Submit
"""
import logging
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from .base import BaseFormFiller


class WorkdayFormFiller(BaseFormFiller):
    """Form filler for Workday job applications."""
    
    # Workday credentials (can be overridden by config)
    WORKDAY_EMAIL = os.environ.get('WORKDAY_EMAIL', '')
    WORKDAY_PASSWORD = os.environ.get('WORKDAY_PASSWORD', '')
    
    def detect_application_page(self):
        """Detect if we're on a Workday application page."""
        try:
            indicators = [
                "div[data-automation-id='formField']",
                "button[data-automation-id='bottom-navigation-next-button']",
                "input[data-automation-id]",
                "[class*='workday']",
                "div[data-automation-id='jobPostingHeader']"
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
        Fill out a Workday job application.
        
        Args:
            job_url: URL of the job posting
            job_data: Optional dictionary with job information
            
        Returns:
            dict: Result with 'success' (bool), 'message' (str), and 'submitted' (bool)
        """
        self.logger.info(f"Starting Workday application fill for: {job_url}")
        
        try:
            # Navigate to the application page
            self.driver.get(job_url)
            self.random_delay(3, 5)  # Workday pages take longer to load
            
            # Wait for page to load
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Step 1A: Click "Apply" button (using the universal method from base class)
            if not self.find_and_click_apply_button():
                # Try Workday-specific selectors as fallback
                if not self._click_apply_button():
                    self.logger.info("Already on application form or Apply button not found")
            
            self.random_delay(2, 4)
            
            # Step 1B: Handle Sign In / Create Account page
            if self._is_on_sign_in_page():
                self.logger.info("Detected Sign In / Create Account page")
                if not self._handle_sign_in():
                    return {
                        'success': False,
                        'message': 'Failed to sign in to Workday. Check credentials.',
                        'submitted': False
                    }
                self.random_delay(2, 4)
            
            # Process application steps (Steps 2-7)
            steps_completed = 0
            max_steps = 10  # Safety limit
            last_step = None
            
            while steps_completed < max_steps:
                current_step = self._detect_current_step()
                
                # Avoid infinite loops on the same step
                if current_step == last_step and current_step not in ['unknown', 'review', 'complete']:
                    self.logger.warning(f"Stuck on step: {current_step}, attempting to proceed")
                    if not self._click_next_button():
                        break
                    steps_completed += 1
                    self.random_delay(2, 4)
                    continue
                
                last_step = current_step
                self.logger.info(f"Processing Workday Step: {current_step}")
                
                if current_step == 'sign_in':
                    if not self._handle_sign_in():
                        break
                elif current_step == 'personal_info':
                    self._fill_personal_info_step()
                elif current_step == 'experience':
                    self._fill_experience_step()
                elif current_step == 'education':
                    self._fill_education_step()
                elif current_step == 'resume':
                    self._fill_resume_step()
                elif current_step == 'questions':
                    self._fill_questions_step()
                elif current_step == 'voluntary':
                    self._fill_voluntary_step()
                elif current_step == 'review':
                    self.logger.info("Reached review page (Step 7)")
                    break
                elif current_step == 'complete':
                    self.logger.info("Application complete")
                    break
                else:
                    self.logger.warning(f"Unknown step: {current_step}, attempting to proceed")
                
                # Try to advance to next step
                if not self._click_next_button():
                    self.logger.info("No next button found or at final step")
                    break
                
                self.random_delay(2, 4)
                steps_completed += 1
            
            # Check if we reached the review/submit page
            submit_button = self._find_submit_button()
            
            if submit_button:
                self.logger.info("Workday application form filled successfully. Submit button found.")
                return {
                    'success': True,
                    'message': 'Workday application form filled. Ready for review and submission.',
                    'submitted': False
                }
            else:
                return {
                    'success': True,
                    'message': f'Workday application partially filled ({steps_completed} steps). May need manual completion.',
                    'submitted': False
                }
                
        except Exception as e:
            self.logger.error(f"Error filling Workday application: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'submitted': False
            }
    
    # ==================== STEP 1: SIGN IN / CREATE ACCOUNT ====================
    
    def _is_on_sign_in_page(self) -> bool:
        """Check if we're on a Workday sign-in or create account page."""
        try:
            page_content = self.driver.page_source.lower()
            url = self.driver.current_url.lower()
            
            sign_in_indicators = [
                'sign in' in page_content,
                'create account' in page_content,
                'email address' in page_content and 'password' in page_content,
                '/login' in url,
                '/signin' in url,
                'createaccount' in url.replace('-', '').replace('_', '')
            ]
            
            # Also check for sign-in form elements
            sign_in_fields = [
                (By.CSS_SELECTOR, "input[data-automation-id='email']"),
                (By.CSS_SELECTOR, "input[data-automation-id='password']"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "button[data-automation-id='signInButton']"),
                (By.CSS_SELECTOR, "button[data-automation-id='createAccountButton']")
            ]
            
            for by, selector in sign_in_fields:
                try:
                    element = self.driver.find_element(by, selector)
                    if element.is_displayed():
                        return True
                except:
                    continue
            
            return any(sign_in_indicators)
        except:
            return False
    
    def _handle_sign_in(self) -> bool:
        """
        Handle the Workday sign-in / create account step.
        
        Uses credentials from:
        1. Config file (application_info.workday_email, workday_password)
        2. Environment variables (WORKDAY_EMAIL, WORKDAY_PASSWORD)
        3. Personal info email (fallback)
        
        Returns:
            bool: True if sign-in was successful
        """
        self.logger.info("Handling Workday Sign In / Create Account")
        
        # Get credentials
        app_info = self.config.get('application_info', {})
        personal_info = self.config.get('personal_info', {})
        
        email = (
            app_info.get('workday_email') or
            self.WORKDAY_EMAIL or
            personal_info.get('email', '')
        )
        password = (
            app_info.get('workday_password') or
            self.WORKDAY_PASSWORD or
            ''
        )
        
        if not email:
            self.logger.error("No email found for Workday sign-in")
            return False
        
        # Fill email field
        email_selectors = [
            (By.CSS_SELECTOR, "input[data-automation-id='email']"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[name='email']"),
            (By.CSS_SELECTOR, "input[id*='email']"),
            (By.CSS_SELECTOR, "input[placeholder*='Email']"),
            (By.XPATH, "//label[contains(text(), 'Email')]/following::input[1]")
        ]
        
        if not self.fill_text_field(email_selectors, email):
            self.logger.warning("Could not fill email field")
        
        # Fill password field (if present and we have a password)
        if password:
            password_selectors = [
                (By.CSS_SELECTOR, "input[data-automation-id='password']"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='password']"),
                (By.CSS_SELECTOR, "input[id*='password']"),
                (By.XPATH, "//label[contains(text(), 'Password')]/following::input[1]")
            ]
            self.fill_text_field(password_selectors, password)
        
        self.random_delay(0.5, 1.0)
        
        # Click Sign In or Create Account button
        sign_in_button_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id='signInButton']"),
            (By.CSS_SELECTOR, "button[data-automation-id='createAccountButton']"),
            (By.XPATH, "//button[contains(text(), 'Sign In')]"),
            (By.XPATH, "//button[contains(text(), 'Create')]"),
            (By.XPATH, "//button[contains(text(), 'Continue')]"),
            (By.XPATH, "//button[contains(text(), 'Next')]"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//input[@type='submit']")
        ]
        
        if self.click_button(sign_in_button_selectors, wait_after=True):
            self.logger.info("Clicked Sign In / Create Account button")
            self.random_delay(3, 5)  # Wait for sign-in to complete
            
            # Check if sign-in was successful (no longer on sign-in page)
            if not self._is_on_sign_in_page():
                self.logger.info("Sign-in successful")
                return True
            else:
                self.logger.warning("Still on sign-in page after clicking button")
                # May need to handle additional steps (verification, etc.)
                return True  # Continue anyway
        
        self.logger.warning("Could not find Sign In button")
        return False
    
    def _click_apply_button(self):
        """Click the Apply button on the job posting page (Workday-specific selectors)."""
        apply_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id='jobPostingApplyButton']"),
            (By.CSS_SELECTOR, "a[data-automation-id='jobPostingApplyButton']"),
            (By.XPATH, "//button[contains(text(), 'Apply')]"),
            (By.XPATH, "//a[contains(text(), 'Apply')]"),
            (By.CSS_SELECTOR, "button.css-1hr0gbs"),  # Common Workday apply button class
        ]
        
        for by, selector in apply_selectors:
            try:
                element = self.driver.find_element(by, selector)
                if element.is_displayed():
                    self.click_button((by, selector))
                    return True
            except:
                continue
        
        return False
    
    # ==================== STEP DETECTION ====================
    
    def _detect_current_step(self):
        """
        Detect which step of the Workday application we're on.
        
        Returns step name based on the 7-step flow:
        - sign_in: Step 1 (Sign In / Create Account)
        - personal_info: Step 2 (My Information)
        - experience: Step 3 (My Experience)
        - education: Part of Step 3 or separate
        - resume: Part of initial steps
        - questions: Steps 4-5 (Application Questions)
        - voluntary: Step 6 (Voluntary Disclosures)
        - review: Step 7 (Review)
        - complete: After submission
        """
        try:
            page_content = self.driver.page_source.lower()
            url = self.driver.current_url.lower()
            
            # Check for step indicators in order of specificity
            
            # Sign In page
            if self._is_on_sign_in_page():
                return 'sign_in'
            
            # Review/Summary page (Step 7)
            if 'review' in page_content or 'summary' in page_content:
                # Make sure it's not just "review" in a different context
                if 'submit application' in page_content or 'review your application' in page_content:
                    return 'review'
            
            # Completion page
            if 'thank you' in page_content or 'application submitted' in page_content:
                return 'complete'
            
            # Voluntary Disclosures (Step 6)
            if any(phrase in page_content for phrase in [
                'voluntary disclosure', 'self-identification', 
                'voluntary self', 'equal opportunity', 'eeo'
            ]):
                return 'voluntary'
            
            # Application Questions (Steps 4-5)
            if any(phrase in page_content for phrase in [
                'application questions', 'screening questions',
                'work authorization', 'require sponsorship',
                'how did you hear'
            ]):
                return 'questions'
            
            # My Experience / Work Experience (Step 3)
            if any(phrase in page_content for phrase in [
                'my experience', 'work experience', 'employment history',
                'job history', 'previous employment'
            ]):
                return 'experience'
            
            # Education (may be part of Step 3 or separate)
            if 'education' in page_content and 'my education' in page_content:
                return 'education'
            
            # Resume upload (may be early in the process)
            if 'upload resume' in page_content or 'attach resume' in page_content:
                return 'resume'
            
            # My Information / Personal Info (Step 2)
            if any(phrase in page_content for phrase in [
                'my information', 'personal information',
                'contact information', 'your information'
            ]):
                return 'personal_info'
            
            # Check for form fields as fallback detection
            return self._detect_step_by_fields()
            
        except Exception as e:
            self.logger.warning(f"Error detecting step: {e}")
            return 'unknown'
    
    def _detect_step_by_fields(self):
        """Detect current step by examining form fields present on page."""
        try:
            # Check for specific field patterns
            
            # Personal info fields
            personal_fields = [
                "input[data-automation-id*='firstName']",
                "input[data-automation-id*='lastName']",
                "input[data-automation-id*='email']",
                "input[data-automation-id*='phone']"
            ]
            
            # Experience fields
            experience_fields = [
                "input[data-automation-id*='jobTitle']",
                "input[data-automation-id*='company']",
                "input[data-automation-id*='employer']"
            ]
            
            # Education fields
            education_fields = [
                "input[data-automation-id*='school']",
                "input[data-automation-id*='degree']",
                "input[data-automation-id*='university']"
            ]
            
            # Check personal info fields
            for selector in personal_fields:
                try:
                    if self.driver.find_element(By.CSS_SELECTOR, selector):
                        return 'personal_info'
                except:
                    continue
            
            # Check experience fields
            for selector in experience_fields:
                try:
                    if self.driver.find_element(By.CSS_SELECTOR, selector):
                        return 'experience'
                except:
                    continue
            
            # Check education fields
            for selector in education_fields:
                try:
                    if self.driver.find_element(By.CSS_SELECTOR, selector):
                        return 'education'
                except:
                    continue
            
            return 'unknown'
        except:
            return 'unknown'
    
    # ==================== STEP 2: MY INFORMATION ====================
    
    def _fill_personal_info_step(self):
        """Fill the personal information step (Step 2)."""
        self.logger.info("Filling Step 2: My Information")
        personal_info = self.config.get('personal_info', {})
        
        # Workday-specific field patterns
        # First Name
        self._fill_workday_field('firstName', personal_info.get('first_name', ''))
        self._fill_workday_field('legalNameSection_firstName', personal_info.get('first_name', ''))
        
        # Last Name
        self._fill_workday_field('lastName', personal_info.get('last_name', ''))
        self._fill_workday_field('legalNameSection_lastName', personal_info.get('last_name', ''))
        
        # Email
        self._fill_workday_field('email', personal_info.get('email', ''))
        
        # Phone
        phone = personal_info.get('phone', '')
        self._fill_workday_field('phone', phone)
        self._fill_workday_field('phoneNumber', phone)
        
        # Address Line 1
        self._fill_workday_field('addressSection_addressLine1', personal_info.get('address_line_1', ''))
        
        # City
        self._fill_workday_field('addressSection_city', personal_info.get('city', ''))
        
        # Postal Code / ZIP
        self._fill_workday_field('addressSection_postalCode', personal_info.get('zip_code', ''))
        
        # Country (dropdown)
        country_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id='addressSection_countryRegion']"),
            (By.CSS_SELECTOR, "[data-automation-id='countryDropdown']"),
            (By.XPATH, "//label[contains(text(), 'Country')]/following::button[1]")
        ]
        self._select_workday_dropdown(country_selectors, personal_info.get('country', 'United States'))
        
        # State (dropdown)
        state_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id='addressSection_region']"),
            (By.CSS_SELECTOR, "[data-automation-id='stateDropdown']"),
            (By.XPATH, "//label[contains(text(), 'State')]/following::button[1]")
        ]
        self._select_workday_dropdown(state_selectors, personal_info.get('state', ''))
    
    # ==================== STEP 3: MY EXPERIENCE ====================
    
    def _fill_experience_step(self):
        """Fill the work experience step (Step 3) using resume components."""
        self.logger.info("Filling Step 3: My Experience")
        if self.resume_components:
            filled = self.fill_work_experience_section(max_entries=3)
            self.logger.info(f"Filled {filled} work experience entries via resume components")
        else:
            self.logger.warning("No resume components - skipping work experience")
    
    def _fill_education_step(self):
        """Fill the education step using resume components."""
        self.logger.info("Filling Education section")
        if self.resume_components:
            filled = self.fill_education_section(max_entries=2)
            self.logger.info(f"Filled {filled} education entries via resume components")
        else:
            self.logger.warning("No resume components - skipping education")
    
    def _fill_resume_step(self):
        """Upload resume on the resume step."""
        self.logger.info("Uploading resume")
        app_info = self.config.get('application_info', {})
        resume_path = app_info.get('resume_path', '')
        
        if resume_path:
            # Workday file upload selectors
            file_selectors = [
                (By.CSS_SELECTOR, "input[data-automation-id='file-upload-input-ref']"),
                (By.CSS_SELECTOR, "input[type='file']"),
                (By.CSS_SELECTOR, "input[data-automation-id='resumeUpload']")
            ]
            
            self.upload_file(file_selectors, resume_path)
            self.random_delay(2, 4)  # Wait for upload
    
    # ==================== STEPS 4-5: APPLICATION QUESTIONS ====================
    
    def _fill_questions_step(self):
        """Handle custom application questions (Steps 4-5)."""
        self.logger.info("Filling Application Questions")
        custom_answers = self.config.get('custom_answers', {})
        work_auth = self.config.get('work_authorization', {})
        app_info = self.config.get('application_info', {})
        
        # Work authorization question
        if work_auth.get('authorized_to_work'):
            self._answer_yes_no_question('authorized', True)
            self._answer_yes_no_question('legally authorized', True)
            self._answer_yes_no_question('work in the', True)
        
        # Sponsorship question
        requires_sponsorship = work_auth.get('requires_sponsorship', False)
        self._answer_yes_no_question('sponsorship', requires_sponsorship)
        self._answer_yes_no_question('visa', requires_sponsorship)
        
        # How did you hear about us
        source = app_info.get('how_did_you_hear', 'LinkedIn')
        source_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id*='source']"),
            (By.XPATH, "//label[contains(text(), 'How did you hear')]/following::button[1]"),
            (By.XPATH, "//label[contains(text(), 'how did you')]/following::button[1]")
        ]
        self._select_workday_dropdown(source_selectors, source)
        
        # Handle any text-based questions
        self._fill_custom_text_questions(custom_answers)
    
    def _answer_yes_no_question(self, question_text: str, answer_yes: bool):
        """Answer a Yes/No radio button question."""
        answer_value = 'Yes' if answer_yes else 'No'
        
        # Try various patterns for Yes/No questions
        selectors = [
            # Radio buttons with value
            (By.XPATH, f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{question_text.lower()}')]/following::input[@type='radio'][@value='{answer_value}']"),
            (By.XPATH, f"//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{question_text.lower()}')]/following::input[@type='radio'][@value='{answer_value}']"),
            # Workday-specific data-automation-id
            (By.CSS_SELECTOR, f"input[data-automation-id*='{question_text.replace(' ', '')}'][value='{answer_value}']"),
        ]
        
        for by, selector in selectors:
            try:
                element = self.driver.find_element(by, selector)
                if element.is_displayed():
                    element.click()
                    self.random_delay(0.3, 0.7)
                    return True
            except:
                continue
        
        return False
    
    def _fill_custom_text_questions(self, custom_answers: dict):
        """Fill any custom text question fields."""
        try:
            # Find all textarea and text input fields that might be custom questions
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            
            for textarea in textareas:
                try:
                    # Try to find associated label
                    label_text = ""
                    try:
                        # Find parent form field and its label
                        parent = textarea.find_element(By.XPATH, "./ancestor::div[contains(@data-automation-id, 'formField')]")
                        label = parent.find_element(By.CSS_SELECTOR, "label")
                        label_text = label.text.lower()
                    except:
                        pass
                    
                    # Match against custom answers
                    for question_pattern, answer in custom_answers.items():
                        if question_pattern.lower() in label_text and answer:
                            textarea.clear()
                            textarea.send_keys(answer)
                            self.random_delay(0.3, 0.5)
                            break
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"Error filling custom questions: {e}")
    
    # ==================== STEP 6: VOLUNTARY DISCLOSURES ====================
    
    def _fill_voluntary_step(self):
        """Handle voluntary self-identification questions (Step 6)."""
        self.logger.info("Filling Step 6: Voluntary Disclosures")
        disclosures = self.config.get('voluntary_disclosures', {})
        
        # Gender
        if disclosures.get('gender_identity'):
            gender_selectors = [
                (By.CSS_SELECTOR, "button[data-automation-id*='gender']"),
                (By.XPATH, "//label[contains(text(), 'Gender')]/following::button[1]")
            ]
            self._select_workday_dropdown(gender_selectors, disclosures['gender_identity'])
        
        # Veteran status
        if disclosures.get('veteran_status'):
            veteran_selectors = [
                (By.CSS_SELECTOR, "button[data-automation-id*='veteran']"),
                (By.XPATH, "//label[contains(text(), 'Veteran')]/following::button[1]")
            ]
            self._select_workday_dropdown(veteran_selectors, disclosures['veteran_status'])
        
        # Disability
        if disclosures.get('disability'):
            disability_selectors = [
                (By.CSS_SELECTOR, "button[data-automation-id*='disability']"),
                (By.XPATH, "//label[contains(text(), 'Disability')]/following::button[1]")
            ]
            self._select_workday_dropdown(disability_selectors, disclosures['disability'])
        
        # Race/Ethnicity
        race_ethnicity = disclosures.get('race_ethnicity', [])
        if race_ethnicity:
            race_value = race_ethnicity[0] if isinstance(race_ethnicity, list) else race_ethnicity
            race_selectors = [
                (By.CSS_SELECTOR, "button[data-automation-id*='ethnicity']"),
                (By.CSS_SELECTOR, "button[data-automation-id*='race']"),
                (By.XPATH, "//label[contains(text(), 'Race')]/following::button[1]"),
                (By.XPATH, "//label[contains(text(), 'Ethnicity')]/following::button[1]")
            ]
            self._select_workday_dropdown(race_selectors, race_value)
    
    # ==================== HELPER METHODS ====================
    
    def _fill_workday_field(self, automation_id, value):
        """Fill a Workday text field by data-automation-id."""
        if not value:
            return False
        
        selectors = [
            (By.CSS_SELECTOR, f"input[data-automation-id='{automation_id}']"),
            (By.CSS_SELECTOR, f"input[data-automation-id*='{automation_id}']"),
            (By.CSS_SELECTOR, f"textarea[data-automation-id='{automation_id}']"),
            (By.CSS_SELECTOR, f"textarea[data-automation-id*='{automation_id}']")
        ]
        
        return self.fill_text_field(selectors, value)
    
    def _select_workday_dropdown(self, selectors, value):
        """Select a value from a Workday dropdown (which are often custom components)."""
        if not value:
            return False
        
        for by, selector in selectors:
            try:
                # Click to open dropdown
                button = self.driver.find_element(by, selector)
                if button.is_displayed():
                    button.click()
                    self.random_delay(0.5, 1.0)
                    
                    # Try to find and click the option
                    option_selectors = [
                        (By.XPATH, f"//div[contains(@data-automation-id, 'option') and contains(text(), '{value}')]"),
                        (By.XPATH, f"//li[contains(text(), '{value}')]"),
                        (By.XPATH, f"//div[contains(@class, 'option') and contains(text(), '{value}')]"),
                        (By.XPATH, f"//div[contains(@role, 'option') and contains(text(), '{value}')]")
                    ]
                    
                    for opt_by, opt_selector in option_selectors:
                        try:
                            option = self.driver.find_element(opt_by, opt_selector)
                            if option.is_displayed():
                                option.click()
                                self.random_delay(0.3, 0.7)
                                return True
                        except:
                            continue
                    
                    # If exact match failed, try typing to filter
                    try:
                        search_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='search'], input[data-automation-id*='search']")
                        search_input.clear()
                        search_input.send_keys(value)
                        self.random_delay(0.5, 1.0)
                        search_input.send_keys(Keys.ENTER)
                        return True
                    except:
                        # Press Escape to close dropdown if we couldn't select
                        try:
                            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        except:
                            pass
            except:
                continue
        
        return False
    
    def _click_next_button(self):
        """Click the Next button to proceed to the next step."""
        next_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id='bottom-navigation-next-button']"),
            (By.CSS_SELECTOR, "button[data-automation-id='nextButton']"),
            (By.XPATH, "//button[contains(text(), 'Next')]"),
            (By.XPATH, "//button[contains(text(), 'Continue')]"),
            (By.XPATH, "//button[contains(text(), 'Save')]"),
            (By.XPATH, "//button[contains(text(), 'Save & Continue')]")
        ]
        
        return self.click_button(next_selectors, wait_after=True)
    
    def _find_submit_button(self):
        """Find the final submit button (Step 7)."""
        submit_selectors = [
            (By.CSS_SELECTOR, "button[data-automation-id='bottom-navigation-submit-button']"),
            (By.CSS_SELECTOR, "button[data-automation-id='submitButton']"),
            (By.XPATH, "//button[contains(text(), 'Submit')]"),
            (By.XPATH, "//button[contains(text(), 'Submit Application')]")
        ]
        
        return self.find_element_safe(submit_selectors, timeout=5)
