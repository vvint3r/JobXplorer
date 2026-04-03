// ── Workday Form Filler ─────────────────────────────────────────────────────
// Port of src/auto_application/form_fillers/workday.py
// Workday uses a multi-step wizard with data-automation-id attributes.
// The extension CANNOT handle sign-in — it pauses and asks the user.

import {
  WORKDAY_SELECTORS as SEL,
  WORKDAY_STEP_KEYWORDS,
  WORKDAY_STEP_FIELDS,
  WORKDAY_XPATH as XPATH,
} from "@shared/selectors/workday";
import { MAX_FORM_STEPS } from "@shared/constants";
import type { FillResult, FillStep } from "@shared/types";
import {
  type FillerContext,
  fillTextField,
  selectDropdown,
  selectCustomDropdown,
  clickElement,
  setCheckbox,
  fillWorkExperienceSection,
  fillEducationSection,
  uploadResume,
  createFillResult,
  addStep,
  fillDelay,
  clickDelay,
  waitForElement,
  queryFirst,
} from "./base";
import {
  WORK_EXPERIENCE_SELECTORS,
  WORK_EXPERIENCE_XPATH,
  EDUCATION_SELECTORS,
  EDUCATION_XPATH,
} from "@shared/selectors/generic";

type WorkdayStep =
  | "signIn"
  | "personalInfo"
  | "experience"
  | "education"
  | "resume"
  | "questions"
  | "voluntary"
  | "review"
  | "complete"
  | "unknown";

// ── Step Detection ──────────────────────────────────────────────────────────

function detectCurrentStep(): WorkdayStep {
  const pageText = document.body.innerText.toLowerCase();

  // Check sign-in page
  if (
    (pageText.includes("sign in") || pageText.includes("create account")) &&
    (document.querySelector("input[type='password']") ||
      document.querySelector("button[data-automation-id='signInButton']"))
  ) {
    return "signIn";
  }

  // Check by page text keywords (ordered by priority)
  for (const [step, keywords] of Object.entries(WORKDAY_STEP_KEYWORDS)) {
    if (keywords.some((kw: string) => pageText.includes(kw))) {
      // Special cases to avoid false positives
      if (step === "review" && !pageText.includes("review your application") && !pageText.includes("submit application")) {
        continue;
      }
      return step as WorkdayStep;
    }
  }

  // Fall back to checking which form fields are present
  for (const [step, selectors] of Object.entries(WORKDAY_STEP_FIELDS)) {
    for (const sel of selectors) {
      if (document.querySelector(sel)) {
        return step as WorkdayStep;
      }
    }
  }

  return "unknown";
}

// ── Step Handlers ───────────────────────────────────────────────────────────

async function fillPersonalInfo(ctx: FillerContext): Promise<[number, number]> {
  const pi = ctx.config.personal_info;
  let filled = 0;
  const total = 8;

  // Workday uses data-automation-id for most fields
  const wdField = async (automationId: string, value: string | undefined) => {
    if (!value) return false;
    const selectors = [
      `input[data-automation-id='${automationId}']`,
      `input[data-automation-id*='${automationId}']`,
      `textarea[data-automation-id='${automationId}']`,
    ];
    return fillTextField(selectors, value);
  };

  if (await wdField("firstName", pi.first_name)) filled++;
  if (await wdField("legalNameSection_firstName", pi.first_name)) filled++;
  if (await wdField("lastName", pi.last_name)) filled++;
  if (await wdField("legalNameSection_lastName", pi.last_name)) filled++;
  if (await wdField("email", pi.email)) filled++;
  if (await wdField("phone", pi.phone)) filled++;
  if (await wdField("phoneNumber", pi.phone)) filled++;
  if (await wdField("addressSection_addressLine1", pi.location)) filled++;
  if (await wdField("addressSection_city", pi.city)) filled++;
  if (await wdField("addressSection_postalCode", pi.zip_code)) filled++;

  // Country dropdown (custom Workday dropdown)
  await selectCustomDropdown(
    SEL.countryDropdown,
    "United States",
  );

  return [filled, total];
}

async function fillExperience(ctx: FillerContext): Promise<[number, number]> {
  const count = await fillWorkExperienceSection(
    ctx,
    WORK_EXPERIENCE_SELECTORS,
    WORK_EXPERIENCE_XPATH,
    ["button[class*='add-experience']"],
    [
      "//button[contains(text(), 'Add Another')]",
      "//button[contains(text(), 'Add Work Experience')]",
    ],
  );
  return [count, ctx.resumeComponents?.work_experience?.length ?? 0];
}

async function fillEducation(ctx: FillerContext): Promise<[number, number]> {
  const count = await fillEducationSection(
    ctx,
    EDUCATION_SELECTORS,
    EDUCATION_XPATH,
    ["button[class*='add-education']"],
    [
      "//button[contains(text(), 'Add Another')]",
      "//button[contains(text(), 'Add Education')]",
    ],
  );
  return [count, ctx.resumeComponents?.education?.length ?? 0];
}

async function fillResume(ctx: FillerContext): Promise<boolean> {
  return uploadResume(SEL.fileUpload, ctx.resumePdfBase64);
}

async function fillQuestions(ctx: FillerContext): Promise<[number, number]> {
  const ai = ctx.config.application_info;
  const wa = ctx.config.work_authorization;
  let filled = 0;
  const total = 3;

  // Yes/No radio questions for work authorization
  const answerRadio = async (questionText: string, answerYes: boolean) => {
    const answerValue = answerYes ? "Yes" : "No";
    const xpath = `//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '${questionText.toLowerCase()}')]/following::input[@type='radio'][@value='${answerValue}']`;
    const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    const radio = result.singleNodeValue as HTMLInputElement | null;
    if (radio) {
      radio.click();
      await fillDelay();
      return true;
    }
    return false;
  };

  if (await answerRadio("authorized", wa.authorized_to_work !== false)) filled++;
  if (await answerRadio("sponsorship", !!wa.requires_sponsorship)) filled++;
  if (await answerRadio("visa", !!wa.requires_sponsorship)) filled++;

  // "How did you hear" dropdown
  await selectCustomDropdown(
    [
      "button[data-automation-id*='source']",
    ],
    ai.how_did_you_hear ?? "LinkedIn",
  );

  // Fill any custom text questions
  const customAnswers = ctx.config.custom_answers ?? {};
  const textareas = document.querySelectorAll<HTMLTextAreaElement>("textarea");
  for (const textarea of textareas) {
    // Try to find associated label via parent formField
    const parent = textarea.closest("[data-automation-id*='formField']");
    const label = parent?.querySelector("label");
    if (!label) continue;
    const labelText = label.textContent?.toLowerCase() ?? "";

    for (const [pattern, answer] of Object.entries(customAnswers)) {
      if (answer && labelText.includes(pattern.toLowerCase())) {
        await fillTextField(["textarea"], answer);
        filled++;
        break;
      }
    }
  }

  return [filled, total];
}

async function fillVoluntary(ctx: FillerContext): Promise<[number, number]> {
  const vd = ctx.config.voluntary_disclosures ?? {};
  let filled = 0;

  if (vd.gender_identity) {
    if (await selectCustomDropdown(SEL.genderDropdown, vd.gender_identity as string)) filled++;
  }
  if (vd.veteran_status) {
    if (await selectCustomDropdown(SEL.veteranDropdown, vd.veteran_status as string)) filled++;
  }
  if (vd.disability) {
    if (await selectCustomDropdown(SEL.disabilityDropdown, vd.disability as string)) filled++;
  }

  return [filled, 3];
}

// ── Navigation ──────────────────────────────────────────────────────────────

async function clickNext(): Promise<boolean> {
  return clickElement(SEL.nextButton, XPATH.nextButton);
}

// ── Main Fill Function ──────────────────────────────────────────────────────

export async function fillWorkday(
  ctx: FillerContext,
  onSignInRequired: () => Promise<void>,
): Promise<FillResult> {
  const result = createFillResult();
  let stepsProcessed = 0;
  let lastStep: WorkdayStep | null = null;

  while (stepsProcessed < MAX_FORM_STEPS) {
    const currentStep = detectCurrentStep();

    // Prevent infinite loop on same step
    if (currentStep === lastStep && currentStep !== "unknown" && currentStep !== "review") {
      // Try to advance
      if (!(await clickNext())) break;
      stepsProcessed++;
      await clickDelay();
      // Wait for page to settle
      await new Promise((r) => setTimeout(r, 1500));
      continue;
    }

    lastStep = currentStep;
    ctx.onStep({ name: currentStep, status: "filling" });

    switch (currentStep) {
      case "signIn": {
        // Extension cannot fill passwords for third-party sites.
        // Signal the overlay to show "Please sign in" and wait.
        addStep(result, "Sign In", "skipped", 0, 0, "Manual sign-in required");
        await onSignInRequired();
        break;
      }

      case "personalInfo": {
        const [f, t] = await fillPersonalInfo(ctx);
        addStep(result, "Personal Info", "done", f, t);
        break;
      }

      case "experience": {
        const [f, t] = await fillExperience(ctx);
        addStep(result, "Work Experience", f > 0 ? "done" : "skipped", f, t);
        break;
      }

      case "education": {
        const [f, t] = await fillEducation(ctx);
        addStep(result, "Education", f > 0 ? "done" : "skipped", f, t);
        break;
      }

      case "resume": {
        const uploaded = await fillResume(ctx);
        addStep(result, "Resume Upload", uploaded ? "done" : "skipped", uploaded ? 1 : 0, 1);
        break;
      }

      case "questions": {
        const [f, t] = await fillQuestions(ctx);
        addStep(result, "Application Questions", "done", f, t);
        break;
      }

      case "voluntary": {
        const [f, t] = await fillVoluntary(ctx);
        addStep(result, "Voluntary Disclosures", f > 0 ? "done" : "skipped", f, t);
        break;
      }

      case "review":
        addStep(result, "Review", "done", 0, 0);
        return result; // Done — user reviews and submits manually

      case "complete":
        addStep(result, "Complete", "done", 0, 0);
        return result;

      default:
        addStep(result, "Unknown Step", "skipped", 0, 0);
        break;
    }

    // Advance to next step
    if (!(await clickNext())) {
      break;
    }

    stepsProcessed++;
    await clickDelay();
    // Wait for page transition
    await new Promise((r) => setTimeout(r, 1500));
  }

  return result;
}
