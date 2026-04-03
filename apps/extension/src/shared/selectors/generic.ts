// ── Generic ATS Selector Maps ────────────────────────────────────────────────
// Ported from src/auto_application/form_fillers/generic.py
// Heuristic field-name matching for unknown ATS platforms.

/** Mapping of field name substrings to user config keys. */
export const GENERIC_FIELD_MAPPINGS: Record<string, string> = {
  first: "first_name",
  last: "last_name",
  email: "email",
  phone: "phone",
  zip: "zip_code",
  postal: "zip_code",
  linkedin: "linkedin_profile",
};

/** Dropdown field patterns → config key. */
export const GENERIC_DROPDOWN_MAPPINGS: Record<string, string> = {
  hear: "how_did_you_hear",
  authorized: "legally_authorized_to_work",
  visa: "require_visa_sponsorship",
  sponsor: "require_visa_sponsorship",
};

/** Default values for dropdown fields when user config is missing. */
export const GENERIC_DROPDOWN_DEFAULTS: Record<string, string> = {
  how_did_you_hear: "LinkedIn",
  legally_authorized_to_work: "Yes",
  require_visa_sponsorship: "No",
};

/** Apply button selectors — used by all generic form detection. */
export const APPLY_BUTTON_SELECTORS = [
  // Data-automation-id (Workday)
  "button[data-automation-id='jobPostingApplyButton']",
  "a[data-automation-id='jobPostingApplyButton']",
  // Class patterns
  "button.jobs-apply-button",
  "a.jobs-apply-button",
  "button[class*='apply-button']",
  "a[class*='apply-button']",
  "button[class*='applyBtn']",
  "a[class*='applyBtn']",
  // Href patterns
  "a[href*='/apply']",
  "a[href*='apply.']",
  // ID patterns
  "button[id*='apply']",
  "a[id*='apply']",
  // ARIA label
  "button[aria-label*='Apply']",
  "a[aria-label*='Apply']",
  // Input submit
  "input[type='submit'][value*='Apply']",
];

/** XPath apply button selectors (case-insensitive text matching). */
export const APPLY_BUTTON_XPATH = [
  "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply now')]",
  "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply now')]",
  "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply for')]",
  "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply for')]",
  "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start application')]",
  "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start application')]",
  "//button[normalize-space(text())='Apply']",
  "//a[normalize-space(text())='Apply']",
  "//button[contains(text(), 'Apply')]",
  "//a[contains(text(), 'Apply')]",
  "//button[.//span[contains(text(), 'Apply')]]",
  "//a[.//span[contains(text(), 'Apply')]]",
];

/** Indicators that the current page is an application form. */
export const FORM_INDICATORS = [
  "input[type='file']",
  "input[name*='first_name']",
  "input[name*='firstName']",
  "input[name*='email'][type='email']",
  "form[action*='apply']",
  "form[action*='submit']",
  "div[data-automation-id='formField']",
  "button[type='submit']",
];

/** Resume file input selectors (priority order). */
export const RESUME_UPLOAD_SELECTORS = [
  "input[type='file'][name*='resume']",
  "input[type='file'][name*='cv']",
  "input[type='file'][id*='resume']",
  "input[type='file'][id*='cv']",
  "input[type='file']",
];

/** Submit button selectors. */
export const SUBMIT_BUTTON_SELECTORS = [
  "button[type='submit']",
  "input[type='submit']",
];

export const SUBMIT_BUTTON_XPATH = [
  "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
  "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
];

// ── Work Experience Selectors ────────────────────────────────────────────────

export const WORK_EXPERIENCE_SELECTORS = {
  jobTitle: [
    "input[name*='job_title']",
    "input[name*='title']",
    "input[id*='jobTitle']",
    "input[id*='job-title']",
    "input[placeholder*='Job Title']",
    "input[placeholder*='Title']",
  ],
  company: [
    "input[name*='company']",
    "input[name*='employer']",
    "input[id*='company']",
    "input[id*='employer']",
    "input[placeholder*='Company']",
    "input[placeholder*='Employer']",
  ],
  currentlyWorkHere: [
    "input[type='checkbox'][name*='current']",
    "input[type='checkbox'][id*='current']",
  ],
  fromMonth: [
    "select[name*='start_month']",
    "select[name*='from_month']",
    "select[id*='startMonth']",
  ],
  fromYear: [
    "select[name*='start_year']",
    "select[name*='from_year']",
    "select[id*='startYear']",
    "input[name*='start_year']",
  ],
  toMonth: [
    "select[name*='end_month']",
    "select[name*='to_month']",
    "select[id*='endMonth']",
  ],
  toYear: [
    "select[name*='end_year']",
    "select[name*='to_year']",
    "select[id*='endYear']",
    "input[name*='end_year']",
  ],
  description: [
    "textarea[name*='description']",
    "textarea[name*='responsibilities']",
    "textarea[id*='description']",
    "textarea[placeholder*='description']",
  ],
};

export const WORK_EXPERIENCE_XPATH = {
  jobTitle: [
    "//label[contains(text(), 'Job Title')]/following-sibling::input",
    "//label[contains(text(), 'Title')]/following::input[1]",
  ],
  company: [
    "//label[contains(text(), 'Company')]/following-sibling::input",
    "//label[contains(text(), 'Employer')]/following::input[1]",
  ],
  currentlyWorkHere: [
    "//input[@type='checkbox'][following-sibling::*[contains(text(), 'currently')]]",
    "//label[contains(text(), 'currently')]/input[@type='checkbox']",
  ],
  fromMonth: [
    "//label[contains(text(), 'From')]/following::select[1]",
  ],
  fromYear: [
    "//label[contains(text(), 'From')]/following::select[2]",
    "//label[contains(text(), 'From')]/following::input[contains(@name, 'year')]",
  ],
  toMonth: [
    "//label[contains(text(), 'To')]/following::select[1]",
  ],
  toYear: [
    "//label[contains(text(), 'To')]/following::select[2]",
  ],
  description: [
    "//label[contains(text(), 'Description')]/following::textarea[1]",
    "//label[contains(text(), 'Responsibilities')]/following::textarea[1]",
  ],
};

// ── Education Selectors ──────────────────────────────────────────────────────

export const EDUCATION_SELECTORS = {
  school: [
    "input[name*='school']",
    "input[name*='university']",
    "input[name*='institution']",
    "input[id*='school']",
    "input[id*='university']",
    "input[placeholder*='School']",
    "input[placeholder*='University']",
  ],
  degreeDropdown: [
    "select[name*='degree']",
    "select[id*='degree']",
  ],
  degreeText: [
    "input[name*='degree']",
    "input[id*='degree']",
    "input[placeholder*='Degree']",
  ],
  fieldOfStudy: [
    "input[name*='field']",
    "input[name*='major']",
    "input[id*='field']",
    "input[id*='major']",
    "input[placeholder*='Field']",
    "input[placeholder*='Major']",
  ],
  fromYear: [
    "select[name*='start_year']",
    "select[name*='from_year']",
    "input[name*='start_year']",
  ],
  toYear: [
    "select[name*='end_year']",
    "select[name*='to_year']",
    "select[name*='graduation']",
    "input[name*='end_year']",
    "input[name*='graduation']",
  ],
  gpa: [
    "input[name*='gpa']",
    "input[id*='gpa']",
    "input[placeholder*='GPA']",
  ],
};

export const EDUCATION_XPATH = {
  school: [
    "//label[contains(text(), 'School')]/following-sibling::input",
    "//label[contains(text(), 'University')]/following::input[1]",
  ],
  fieldOfStudy: [
    "//label[contains(text(), 'Field')]/following::input[1]",
    "//label[contains(text(), 'Major')]/following::input[1]",
  ],
  degreeText: [
    "//label[contains(text(), 'Degree')]/following::input[1]",
  ],
  fromYear: [
    "//label[contains(text(), 'From')]/following::select[1]",
  ],
  toYear: [
    "//label[contains(text(), 'To')]/following::select[1]",
    "//label[contains(text(), 'Graduation')]/following::select[1]",
  ],
};
