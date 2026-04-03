// ── SmartRecruiters ATS Selector Maps ────────────────────────────────────────
// SmartRecruiters uses a multi-step wizard with data-testid and name attributes.
// URL pattern: jobs.smartrecruiters.com/company/job or /apply

export const SEL = {
  // Personal info — step 1
  firstName: ["input[name='firstName']", "input[data-testid='firstName']"] as const,
  lastName: ["input[name='lastName']", "input[data-testid='lastName']"] as const,
  email: ["input[name='email']", "input[type='email']"] as const,
  phone: ["input[name='phoneNumber']", "input[name='phone']", "input[data-testid='phoneNumber']"] as const,

  // Resume upload
  resumeUpload: [
    "input[type='file'][name='resume']",
    "input[type='file'][data-testid='resume-upload']",
    "input[type='file'][accept*='pdf']",
    "input[type='file']",
  ] as const,

  // Navigation
  nextButton: [
    "button[data-testid='navigation-next']",
    "button[data-testid='next-button']",
    "button[class*='navigation-next']",
  ] as const,

  submitButton: [
    "button[data-testid='submit-btn']",
    "button[data-testid='submit']",
    "button[type='submit']",
  ] as const,

  // Custom questions (generic input/textarea/select on Q steps)
  customInputs: ["div[data-testid='question'] input[type='text']"] as const,
  customTextareas: ["div[data-testid='question'] textarea"] as const,
  customSelects: ["div[data-testid='question'] select"] as const,

  // Step indicator (to detect current step)
  stepTitle: [
    "h1[data-testid='page-title']",
    "h2[class*='title']",
    ".step-title",
    "h1",
  ] as const,
} as const;

export const XPATH = {
  nextButton: [
    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'next')]",
    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue')]",
  ] as const,
  submitButton: [
    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit')]",
    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send application')]",
  ] as const,
} as const;

/** Step types detected by title text. */
export const STEP_KEYWORDS = {
  personalInfo: ["personal", "contact", "information", "details"],
  resume: ["resume", "cv", "upload", "document"],
  questions: ["question", "screening", "additional"],
  review: ["review", "summary", "confirm"],
} as const;
