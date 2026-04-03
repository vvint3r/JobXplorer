// ── Workday ATS Selector Maps ────────────────────────────────────────────────
// Ported from src/auto_application/form_fillers/workday.py

export const WORKDAY_SELECTORS = {
  // ── Apply Button ─────────────────────────────────────────────────────────
  applyButton: [
    "button[data-automation-id='jobPostingApplyButton']",
    "a[data-automation-id='jobPostingApplyButton']",
    "button.css-1hr0gbs",
  ],

  // ── Sign-In Detection ────────────────────────────────────────────────────
  signInEmail: [
    "input[data-automation-id='email']",
    "input[type='email']",
    "input[name='email']",
    "input[id*='email']",
    "input[placeholder*='Email']",
  ],
  signInPassword: [
    "input[data-automation-id='password']",
    "input[type='password']",
    "input[name='password']",
    "input[id*='password']",
  ],
  signInButton: [
    "button[data-automation-id='signInButton']",
  ],
  createAccountButton: [
    "button[data-automation-id='createAccountButton']",
  ],

  // ── Personal Info (Step 2) ───────────────────────────────────────────────
  firstName: [
    "input[data-automation-id='firstName']",
    "input[data-automation-id*='firstName']",
    "input[data-automation-id='legalNameSection_firstName']",
  ],
  lastName: [
    "input[data-automation-id='lastName']",
    "input[data-automation-id*='lastName']",
    "input[data-automation-id='legalNameSection_lastName']",
  ],
  email: [
    "input[data-automation-id='email']",
    "input[data-automation-id*='email']",
  ],
  phone: [
    "input[data-automation-id='phone']",
    "input[data-automation-id*='phone']",
    "input[data-automation-id='phoneNumber']",
  ],
  addressLine1: [
    "input[data-automation-id='addressSection_addressLine1']",
  ],
  city: [
    "input[data-automation-id='addressSection_city']",
  ],
  postalCode: [
    "input[data-automation-id='addressSection_postalCode']",
  ],

  // ── Dropdowns (custom Workday components) ────────────────────────────────
  countryDropdown: [
    "button[data-automation-id='addressSection_countryRegion']",
    "[data-automation-id='countryDropdown']",
  ],
  stateDropdown: [
    "button[data-automation-id='addressSection_region']",
    "[data-automation-id='stateDropdown']",
  ],

  // ── Experience Fields ────────────────────────────────────────────────────
  jobTitle: [
    "input[data-automation-id*='jobTitle']",
  ],
  company: [
    "input[data-automation-id*='company']",
    "input[data-automation-id*='employer']",
  ],

  // ── Education Fields ─────────────────────────────────────────────────────
  school: [
    "input[data-automation-id*='school']",
    "input[data-automation-id*='university']",
  ],
  degree: [
    "input[data-automation-id*='degree']",
  ],

  // ── File Upload ──────────────────────────────────────────────────────────
  fileUpload: [
    "input[data-automation-id='file-upload-input-ref']",
    "input[type='file']",
    "input[data-automation-id='resumeUpload']",
  ],

  // ── Voluntary Disclosures ────────────────────────────────────────────────
  genderDropdown: [
    "button[data-automation-id*='gender']",
  ],
  veteranDropdown: [
    "button[data-automation-id*='veteran']",
  ],
  disabilityDropdown: [
    "button[data-automation-id*='disability']",
  ],
  ethnicityDropdown: [
    "button[data-automation-id*='ethnicity']",
    "button[data-automation-id*='race']",
  ],

  // ── How Did You Hear ─────────────────────────────────────────────────────
  sourceDropdown: [
    "button[data-automation-id*='source']",
  ],

  // ── Navigation ───────────────────────────────────────────────────────────
  nextButton: [
    "button[data-automation-id='bottom-navigation-next-button']",
    "button[data-automation-id='nextButton']",
  ],
  submitButton: [
    "button[data-automation-id='bottom-navigation-submit-button']",
    "button[data-automation-id='submitButton']",
  ],

  // ── Detection Indicators ─────────────────────────────────────────────────
  formIndicators: [
    "div[data-automation-id='formField']",
    "button[data-automation-id='bottom-navigation-next-button']",
    "input[data-automation-id]",
    "div[data-automation-id='jobPostingHeader']",
  ],

  // ── Dropdown Option Selection ────────────────────────────────────────────
  dropdownOption: (value: string) => [
    `div[data-automation-id*='option']:not([aria-hidden='true'])`,
    `li:not([aria-hidden='true'])`,
    `div[role='option']`,
  ],
} as const;

// ── Step Detection Keywords ──────────────────────────────────────────────────

export const WORKDAY_STEP_KEYWORDS = {
  signIn: ["sign in", "create account", "/login", "/signin", "createaccount"],
  personalInfo: ["my information", "personal information", "contact information", "your information"],
  experience: ["my experience", "work experience", "employment history", "job history", "previous employment"],
  education: ["my education"],
  resumeUpload: ["upload resume", "attach resume"],
  questions: ["application questions", "screening questions", "work authorization", "require sponsorship", "how did you hear"],
  voluntaryDisclosure: ["voluntary disclosure", "self-identification", "voluntary self", "equal opportunity", "eeo"],
  review: ["review", "summary", "submit application", "review your application"],
  complete: ["thank you", "application submitted"],
} as const;

// ── Step Detection by Fields ─────────────────────────────────────────────────

export const WORKDAY_STEP_FIELDS = {
  personalInfo: [
    "input[data-automation-id*='firstName']",
    "input[data-automation-id*='lastName']",
    "input[data-automation-id*='email']",
    "input[data-automation-id*='phone']",
  ],
  experience: [
    "input[data-automation-id*='jobTitle']",
    "input[data-automation-id*='company']",
    "input[data-automation-id*='employer']",
  ],
  education: [
    "input[data-automation-id*='school']",
    "input[data-automation-id*='degree']",
    "input[data-automation-id*='university']",
  ],
} as const;

// XPath selectors for Workday
export const WORKDAY_XPATH = {
  nextButton: [
    "//button[contains(text(), 'Next')]",
    "//button[contains(text(), 'Continue')]",
    "//button[contains(text(), 'Save')]",
    "//button[contains(text(), 'Save & Continue')]",
  ],
  submitButton: [
    "//button[contains(text(), 'Submit')]",
    "//button[contains(text(), 'Submit Application')]",
  ],
  applyButton: [
    "//button[contains(text(), 'Apply')]",
    "//a[contains(text(), 'Apply')]",
  ],
  countryDropdown: [
    "//label[contains(text(), 'Country')]/following::button[1]",
  ],
  stateDropdown: [
    "//label[contains(text(), 'State')]/following::button[1]",
  ],
  genderDropdown: [
    "//label[contains(text(), 'Gender')]/following::button[1]",
  ],
  veteranDropdown: [
    "//label[contains(text(), 'Veteran')]/following::button[1]",
  ],
  disabilityDropdown: [
    "//label[contains(text(), 'Disability')]/following::button[1]",
  ],
  ethnicityDropdown: [
    "//label[contains(text(), 'Race')]/following::button[1]",
    "//label[contains(text(), 'Ethnicity')]/following::button[1]",
  ],
  sourceDropdown: [
    "//label[contains(text(), 'How did you hear')]/following::button[1]",
    "//label[contains(text(), 'how did you')]/following::button[1]",
  ],
} as const;
