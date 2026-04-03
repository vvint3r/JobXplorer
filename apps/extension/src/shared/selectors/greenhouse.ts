// ── Greenhouse ATS Selector Maps ─────────────────────────────────────────────
// Ported from src/auto_application/form_fillers/greenhouse.py

export const GREENHOUSE_SELECTORS = {
  // ── Personal Info ────────────────────────────────────────────────────────
  firstName: [
    "input[name='first_name']",
    "input[id*='first_name']",
    "input[id*='firstName']",
    "input[placeholder*='First Name']",
  ],
  lastName: [
    "input[name='last_name']",
    "input[id*='last_name']",
    "input[id*='lastName']",
    "input[placeholder*='Last Name']",
  ],
  email: [
    "input[name='email']",
    "input[type='email']",
    "input[id*='email']",
  ],
  phone: [
    "input[name='phone']",
    "input[type='tel']",
    "input[id*='phone']",
  ],
  preferredName: [
    "input[name='preferred_name']",
    "input[id*='preferred_name']",
  ],
  linkedin: [
    "input[name*='linkedin']",
    "input[id*='linkedin']",
  ],
  zipCode: [
    "input[name*='zip']",
    "input[name*='postal']",
    "input[id*='zip']",
  ],

  // ── Application Details (Dropdowns) ──────────────────────────────────────
  howDidYouHear: [
    "select[name*='hear']",
    "select[id*='hear']",
  ],
  workAuthorization: [
    "select[name*='authorized']",
    "select[name*='work']",
  ],
  visaSponsorship: [
    "select[name*='visa']",
    "select[name*='sponsor']",
  ],
  metroArea: [
    "select[name*='metro']",
    "select[name*='location']",
  ],

  // ── File Upload ──────────────────────────────────────────────────────────
  resumeUpload: [
    "input[type='file'][name*='resume']",
    "input[type='file'][name*='cv']",
    "input[type='file']",
    "input[accept*='pdf']",
  ],
  coverLetterUpload: [
    "input[type='file'][name*='cover']",
    "input[type='file'][name*='letter']",
  ],

  // ── Voluntary Disclosures ────────────────────────────────────────────────
  genderIdentity: [
    "select[name*='gender']",
    "select[id*='gender']",
  ],
  veteranStatus: [
    "select[name*='veteran']",
    "select[id*='veteran']",
  ],
  disability: [
    "select[name*='disability']",
    "select[id*='disability']",
  ],

  // ── Submit ───────────────────────────────────────────────────────────────
  submitButton: [
    "button[type='submit']",
    "input[type='submit']",
  ],

  // ── Detection Indicators ─────────────────────────────────────────────────
  formIndicators: [
    "input[type='file']",
    "input[name*='first_name']",
    "input[name*='last_name']",
    "input[name*='email']",
    "form[action*='greenhouse']",
  ],
} as const;

// XPath selectors for Greenhouse (used when CSS selectors fail)
export const GREENHOUSE_XPATH = {
  submitButton: [
    "//button[contains(text(), 'Submit')]",
    "//button[contains(text(), 'Submit Application')]",
    "//button[contains(text(), 'Apply')]",
  ],
  applyButton: [
    "//a[contains(text(), 'Apply')]",
    "//button[contains(text(), 'Apply')]",
  ],
  customQuestionTextarea: (questionText: string) => [
    `//label[contains(text(), '${questionText}')]/following-sibling::textarea`,
    `//label[contains(text(), '${questionText}')]/following::textarea[1]`,
    `//textarea[preceding-sibling::label[contains(text(), '${questionText}')]]`,
  ],
} as const;
