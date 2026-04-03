// ── Greenhouse Form Filler ──────────────────────────────────────────────────
// Port of src/auto_application/form_fillers/greenhouse.py
// Greenhouse applications are single-page forms with all fields visible.

import {
  GREENHOUSE_SELECTORS as SEL,
  GREENHOUSE_XPATH as XPATH,
} from "@shared/selectors/greenhouse";
import type { FillResult } from "@shared/types";
import {
  type FillerContext,
  fillTextField,
  selectDropdown,
  fillWorkExperienceSection,
  fillEducationSection,
  uploadResume,
  clickElement,
  createFillResult,
  addStep,
  fillDelay,
} from "./base";
import {
  WORK_EXPERIENCE_SELECTORS,
  WORK_EXPERIENCE_XPATH,
  EDUCATION_SELECTORS,
  EDUCATION_XPATH,
} from "@shared/selectors/generic";

export async function fillGreenhouse(ctx: FillerContext): Promise<FillResult> {
  const result = createFillResult();
  const pi = ctx.config.personal_info;
  const ai = ctx.config.application_info;

  // ── Step 1: Personal Info ─────────────────────────────────────────────
  ctx.onStep({ name: "Personal Info", status: "filling" });

  let piFilled = 0;
  const piTotal = 7;

  if (await fillTextField(SEL.firstName, pi.first_name)) piFilled++;
  if (await fillTextField(SEL.lastName, pi.last_name)) piFilled++;
  if (await fillTextField(SEL.email, pi.email)) piFilled++;
  if (await fillTextField(SEL.phone, pi.phone)) piFilled++;
  if (await fillTextField(SEL.preferredName, pi.preferred_name)) piFilled++;
  if (await fillTextField(SEL.linkedin, pi.linkedin_profile)) piFilled++;
  if (await fillTextField(SEL.zipCode, pi.zip_code)) piFilled++;

  addStep(result, "Personal Info", "done", piFilled, piTotal);

  // ── Step 2: Application Details ───────────────────────────────────────
  ctx.onStep({ name: "Application Details", status: "filling" });

  let adFilled = 0;
  const adTotal = 3;

  if (await selectDropdown(SEL.howDidYouHear, ai.how_did_you_hear ?? "LinkedIn")) adFilled++;
  if (await selectDropdown(SEL.workAuthorization, ai.legally_authorized_to_work ?? "Yes")) adFilled++;
  if (await selectDropdown(SEL.visaSponsorship, ai.require_visa_sponsorship ?? "No")) adFilled++;

  addStep(result, "Application Details", "done", adFilled, adTotal);

  // ── Step 3: Work Experience ───────────────────────────────────────────
  ctx.onStep({ name: "Work Experience", status: "filling" });

  const workFilled = await fillWorkExperienceSection(
    ctx,
    WORK_EXPERIENCE_SELECTORS,
    WORK_EXPERIENCE_XPATH,
    [
      "button:has(+ *:contains('Add Another'))",
      "a[class*='add-experience']",
    ],
    [
      "//button[contains(text(), 'Add Another')]",
      "//button[contains(text(), 'Add Work Experience')]",
      "//a[contains(text(), 'Add Another')]",
    ],
  );

  addStep(
    result,
    "Work Experience",
    workFilled > 0 ? "done" : "skipped",
    workFilled,
    ctx.resumeComponents?.work_experience?.length ?? 0,
  );

  // ── Step 4: Education ─────────────────────────────────────────────────
  ctx.onStep({ name: "Education", status: "filling" });

  const eduFilled = await fillEducationSection(
    ctx,
    EDUCATION_SELECTORS,
    EDUCATION_XPATH,
    ["a[class*='add-education']"],
    [
      "//button[contains(text(), 'Add Another')]",
      "//button[contains(text(), 'Add Education')]",
      "//a[contains(text(), 'Add Another')]",
    ],
  );

  addStep(
    result,
    "Education",
    eduFilled > 0 ? "done" : "skipped",
    eduFilled,
    ctx.resumeComponents?.education?.length ?? 0,
  );

  // ── Step 5: Custom Questions ──────────────────────────────────────────
  ctx.onStep({ name: "Custom Questions", status: "filling" });

  let cqFilled = 0;
  const customAnswers = ctx.config.custom_answers ?? {};

  // Find all textareas and try to match to custom answers via nearby labels
  const textareas = document.querySelectorAll<HTMLTextAreaElement>("textarea");
  for (const textarea of textareas) {
    const label = textarea.closest("div")?.querySelector("label");
    if (!label) continue;
    const labelText = label.textContent?.toLowerCase() ?? "";

    for (const [pattern, answer] of Object.entries(customAnswers)) {
      if (answer && labelText.includes(pattern.toLowerCase())) {
        if (await fillTextField([`textarea`], answer)) {
          cqFilled++;
        }
        break;
      }
    }
  }

  addStep(result, "Custom Questions", cqFilled > 0 ? "done" : "skipped", cqFilled, textareas.length);

  // ── Step 6: Resume Upload ─────────────────────────────────────────────
  ctx.onStep({ name: "Resume Upload", status: "filling" });

  const uploaded = uploadResume(SEL.resumeUpload, ctx.resumePdfBase64);
  addStep(result, "Resume Upload", uploaded ? "done" : "skipped", uploaded ? 1 : 0, 1);

  // ── Step 7: Voluntary Disclosures ─────────────────────────────────────
  ctx.onStep({ name: "Voluntary Disclosures", status: "filling" });

  const vd = ctx.config.voluntary_disclosures ?? {};
  let vdFilled = 0;

  if (vd.gender_identity && (await selectDropdown(SEL.genderIdentity, vd.gender_identity as string))) vdFilled++;
  if (vd.veteran_status && (await selectDropdown(SEL.veteranStatus, vd.veteran_status as string))) vdFilled++;
  if (vd.disability && (await selectDropdown(SEL.disability, vd.disability as string))) vdFilled++;

  addStep(result, "Voluntary Disclosures", vdFilled > 0 ? "done" : "skipped", vdFilled, 3);

  await fillDelay();
  return result;
}
