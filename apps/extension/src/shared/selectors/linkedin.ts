// ── LinkedIn Easy Apply Selector Maps ────────────────────────────────────────
// LinkedIn Easy Apply opens a sidebar modal on linkedin.com/jobs/view/* pages.
// Fields use aria-label attributes and specific class patterns.

export const SEL = {
  // Easy Apply button on the job page (to trigger modal open)
  easyApplyButton: [
    "button.jobs-apply-button",
    "button[aria-label*='Easy Apply']",
    ".jobs-apply-button",
  ] as const,

  // Modal container
  modal: [
    ".jobs-easy-apply-content",
    "[data-test-modal-id='easy-apply-modal']",
    ".artdeco-modal__content",
  ] as const,

  // Personal info fields inside the modal (aria-label based)
  firstName: [
    "input[aria-label*='First name']",
    "input[aria-label*='first name']",
    "input[id*='firstName']",
  ] as const,
  lastName: [
    "input[aria-label*='Last name']",
    "input[aria-label*='last name']",
    "input[id*='lastName']",
  ] as const,
  email: [
    "input[aria-label*='Email']",
    "input[aria-label*='email']",
    "input[type='email']",
  ] as const,
  phone: [
    "input[aria-label*='Phone']",
    "input[aria-label*='phone']",
    "input[aria-label*='Mobile']",
  ] as const,
  phoneCountryCode: [
    "select[aria-label*='Phone country code']",
    "select[aria-label*='country code']",
  ] as const,

  // Resume / document upload
  resumeUpload: [
    "input[type='file'][name='file']",
    "input[type='file'][accept*='pdf']",
    "input[type='file']",
  ] as const,
  // Pre-uploaded resume selector (choose from previously uploaded)
  resumeOption: [
    ".jobs-resume-picker__resume",
    "[data-test-resume-picker-item]",
  ] as const,

  // Screening question inputs (generic within the modal)
  questionInputs: [
    ".jobs-easy-apply-form-element input[type='text']",
    ".jobs-easy-apply-form-element input[type='number']",
    "fieldset.fb-text-selectable__container input",
  ] as const,
  questionTextareas: [".jobs-easy-apply-form-element textarea"] as const,
  questionSelects: [".jobs-easy-apply-form-element select"] as const,
  questionRadios: [".jobs-easy-apply-form-element input[type='radio']"] as const,

  // Navigation buttons inside the modal
  nextButton: [
    "button[aria-label='Continue to next step']",
    "button[aria-label='Review your application']",
    ".jobs-easy-apply-footer button[aria-label*='next']",
    "footer button.artdeco-button--primary",
  ] as const,
  submitButton: [
    "button[aria-label='Submit application']",
    "button[aria-label*='Submit']",
    ".jobs-easy-apply-footer button[aria-label*='Submit']",
  ] as const,
  dismissButton: [
    "button[aria-label='Dismiss']",
    "button.artdeco-modal__dismiss",
  ] as const,

  // Step detection
  modalHeader: [
    "h3.t-18",
    "h3.jobs-easy-apply-header",
    ".jobs-easy-apply-header__title",
  ] as const,
} as const;

export const XPATH = {
  nextButton: [
    "//button[contains(@aria-label,'Continue')]",
    "//button[contains(@aria-label,'Review')]",
    "//footer//button[contains(@class,'primary')]",
  ] as const,
  submitButton: [
    "//button[contains(@aria-label,'Submit application')]",
  ] as const,
} as const;

export const STEP_KEYWORDS = {
  contact: ["contact info", "personal", "phone number"],
  resume: ["resume", "upload", "document"],
  questions: ["question", "screening", "additional information", "work authorization"],
  review: ["review", "additional"],
} as const;
