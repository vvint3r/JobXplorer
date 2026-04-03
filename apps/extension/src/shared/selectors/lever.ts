// ── Lever ATS Selector Maps ───────────────────────────────────────────────────
// Lever uses a single-page application form at jobs.lever.co/company/uuid/apply
// Fields use standard name attributes.

// Personal info — Lever uses a single full-name field (not split first/last)
export const SEL = {
  fullName: ["input[name='name']"] as const,
  email: ["input[name='email']"] as const,
  phone: ["input[name='phone']"] as const,
  currentCompany: ["input[name='org']"] as const,
  linkedin: ["input[name='urls[LinkedIn]']", "input[name='urls[LinkedIn URL]']"] as const,
  website: ["input[name='urls[Portfolio]']", "input[name='urls[Website]']"] as const,

  // Resume upload
  resumeUpload: [
    "input[type='file'][name='resume']",
    "input[type='file'][class*='resume']",
    "input[type='file']",
  ] as const,

  // Custom question fields (Lever prefixes them with "cards")
  customTextInputs: ["input[name^='cards']"] as const,
  customTextareas: ["textarea[name^='cards']"] as const,
  customSelects: ["select[name^='cards']"] as const,

  // Submit
  submitButton: [
    "button[type='submit']",
    "button[class*='submit']",
    "input[type='submit']",
  ] as const,
} as const;

export const XPATH = {
  submitButton: [
    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit application')]",
    "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply')]",
  ] as const,
} as const;
