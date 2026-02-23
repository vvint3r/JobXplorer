"""
Generic form filler for unknown job board platforms.
Uses heuristics to identify and fill common form fields.
"""
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseFormFiller

class GenericFormFiller(BaseFormFiller):
    """Generic form filler that works with any job board using heuristics."""
    
    def detect_application_page(self):
        """Detect if we're on an application page using common indicators."""
        try:
            # Look for common application form indicators
            indicators = [
                "input[type='file']",  # File upload
                "input[type='email']",  # Email field
                "form",  # Any form
                "input[name*='name']",  # Name fields
                "input[name*='email']"  # Email fields
            ]
            
            found_indicators = 0
            for indicator in indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements:
                        found_indicators += 1
                except:
                    continue
            
            # If we find at least 2 indicators, likely an application page
            return found_indicators >= 2
        except:
            return False
    
    def fill_application(self, job_url, job_data=None):
        """
        Fill out a generic job application using heuristics.
        
        Args:
            job_url: URL of the job posting
            job_data: Optional dictionary with job information
            
        Returns:
            dict: Result with 'success' (bool), 'message' (str), and 'submitted' (bool)
        """
        self.logger.info(f"Starting generic application fill for: {job_url}")
        
        try:
            # Navigate to the application page
            self.driver.get(job_url)
            self.random_delay(2, 4)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Try to find and click "Apply" button
            self._click_apply_button()
            
            self.random_delay(2, 3)
            
            # Fill fields using heuristics
            personal_info = self.config.get('personal_info', {})
            app_info = self.config.get('application_info', {})
            
            # Fill all text inputs that look like personal info
            self._fill_all_text_fields(personal_info, app_info)
            
            # Fill dropdowns
            self._fill_all_dropdowns(app_info)
            
            # Fill work experience section (uses resume components from base class)
            work_exp_filled = self.fill_work_experience_section(max_entries=3)
            self.logger.info(f"Filled {work_exp_filled} work experience entries")
            
            # Fill education section (uses resume components from base class)
            edu_filled = self.fill_education_section(max_entries=2)
            self.logger.info(f"Filled {edu_filled} education entries")
            
            # Upload files
            resume_path = app_info.get('resume_path')
            if resume_path:
                self._upload_any_file(resume_path)
            
            # Check for submit button
            submitted = False
            submit_button = self._find_submit_button()
            
            if submit_button:
                self.logger.info("Application form filled. Submit button found.")
                return {
                    'success': True,
                    'message': 'Application form filled using generic heuristics. Please review before submitting.',
                    'submitted': submitted
                }
            else:
                return {
                    'success': False,
                    'message': 'Could not find submit button. Form may need manual completion.',
                    'submitted': False
                }
                
        except Exception as e:
            self.logger.error(f"Error filling generic application: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'submitted': False
            }
    
    def _click_apply_button(self):
        """Try to find and click an Apply button."""
        apply_selectors = [
            (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]"),
            (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]"),
            (By.CSS_SELECTOR, "a[href*='apply']"),
            (By.CSS_SELECTOR, "button[class*='apply']")
        ]
        
        for by, selector in apply_selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed():
                        self.click_button((by, selector))
                        return
            except:
                continue
    
    def _fill_all_text_fields(self, personal_info, app_info):
        """Fill all text input fields using field name/ID heuristics."""
        try:
            # Get all text inputs
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='tel']")
            
            field_mappings = {
                'first': personal_info.get('first_name', ''),
                'last': personal_info.get('last_name', ''),
                'email': personal_info.get('email', ''),
                'phone': personal_info.get('phone', ''),
                'zip': personal_info.get('zip_code', ''),
                'postal': personal_info.get('zip_code', ''),
                'linkedin': personal_info.get('linkedin_profile', '')
            }
            
            for input_field in inputs:
                try:
                    field_id = (input_field.get_attribute('id') or '').lower()
                    field_name = (input_field.get_attribute('name') or '').lower()
                    field_placeholder = (input_field.get_attribute('placeholder') or '').lower()
                    
                    # Skip if already filled
                    if input_field.get_attribute('value'):
                        continue
                    
                    # Try to match field
                    for key, value in field_mappings.items():
                        if value and (key in field_id or key in field_name or key in field_placeholder):
                            # Use the element directly instead of trying to find it again
                            try:
                                input_field.clear()
                                self.random_delay(0.2, 0.5)
                                input_field.send_keys(value)
                                self.random_delay(0.3, 0.7)
                            except:
                                pass
                            break
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"Error filling text fields: {e}")
    
    def _fill_all_dropdowns(self, app_info):
        """Fill all dropdown fields using heuristics."""
        try:
            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            
            for select in selects:
                try:
                    select_id = (select.get_attribute('id') or '').lower()
                    select_name = (select.get_attribute('name') or '').lower()
                    
                    # Match dropdowns to values
                    if 'hear' in select_id or 'hear' in select_name:
                        value = app_info.get('how_did_you_hear', 'LinkedIn')
                        self.select_dropdown([(By.CSS_SELECTOR, f"select[id='{select.get_attribute('id')}']")], value, match_type='contains')
                    elif 'authorized' in select_id or 'authorized' in select_name:
                        value = app_info.get('legally_authorized_to_work', 'Yes')
                        self.select_dropdown([(By.CSS_SELECTOR, f"select[id='{select.get_attribute('id')}']")], value, match_type='contains')
                    elif 'visa' in select_id or 'sponsor' in select_id or 'visa' in select_name or 'sponsor' in select_name:
                        value = app_info.get('require_visa_sponsorship', 'No')
                        self.select_dropdown([(By.CSS_SELECTOR, f"select[id='{select.get_attribute('id')}']")], value, match_type='contains')
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"Error filling dropdowns: {e}")
    
    def _upload_any_file(self, file_path):
        """Try to upload a file to any file input found."""
        try:
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            
            for file_input in file_inputs:
                try:
                    # Check if it's for resume/CV
                    input_id = (file_input.get_attribute('id') or '').lower()
                    input_name = (file_input.get_attribute('name') or '').lower()
                    
                    if 'resume' in input_id or 'cv' in input_id or 'resume' in input_name or 'cv' in input_name:
                        self.upload_file([(By.CSS_SELECTOR, f"input[id='{file_input.get_attribute('id')}']")], file_path)
                        return True
                except:
                    continue
            
            # If no specific resume field, try first file input
            if file_inputs:
                try:
                    self.upload_file([(By.CSS_SELECTOR, "input[type='file']")], file_path)
                    return True
                except:
                    pass
            
            return False
        except Exception as e:
            self.logger.warning(f"Error uploading file: {e}")
            return False
    
    def _find_submit_button(self):
        """Find submit button using common patterns."""
        submit_selectors = [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]"),
            (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]")
        ]
        
        return self.find_element_safe(submit_selectors, timeout=5)

