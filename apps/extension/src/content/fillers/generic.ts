// ── Generic Form Filler ─────────────────────────────────────────────────────
// Port of src/auto_application/form_fillers/generic.py
// Heuristic-based filler for unknown ATS platforms.
// Scans all visible inputs/selects and matches by name/id/placeholder.

import {
  GENERIC_FIELD_MAPPINGS,
  GENERIC_DROPDOWN_MAPPINGS,
  GENERIC_DROPDOWN_DEFAULTS,
  RESUME_UPLOAD_SELECTORS,
  WORK_EXPERIENCE_SELECTORS,
  WORK_EXPERIENCE_XPATH,
  EDUCATION_SELECTORS,
  EDUCATION_XPATH,
} from "@shared/selectors/generic";
import type { FillResult } from "@shared/types";
import {
  type FillerContext,
  setNativeValue,
  selectDropdown,
  fillWorkExperienceSection,
  fillEducationSection,
  uploadResume,
  createFillResult,
  addStep,
  fillDelay,
} from "./base";

export async function fillGeneric(ctx: FillerContext): Promise<FillResult> {
  const result = createFillResult();
  const pi = ctx.config.personal_info;
  const ai = ctx.config.application_info;

  // ── Step 1: Heuristic text field fill ─────────────────────────────────
  ctx.onStep({ name: "Personal Info", status: "filling" });

  let piFilled = 0;
  let piTotal = 0;

  const inputs = document.querySelectorAll<HTMLInputElement>(
    "input[type='text'], input[type='email'], input[type='tel'], input:not([type])",
  );

  for (const input of inputs) {
    // Skip hidden or already-filled fields
    if (input.offsetParent === null || input.value) continue;

    const fieldId = (input.id ?? "").toLowerCase();
    const fieldName = (input.name ?? "").toLowerCase();
    const fieldPlaceholder = (input.placeholder ?? "").toLowerCase();
    const combined = `${fieldId} ${fieldName} ${fieldPlaceholder}`;

    piTotal++;

    // Match against known field patterns
    for (const [pattern, configKey] of Object.entries(GENERIC_FIELD_MAPPINGS)) {
      if (combined.includes(pattern)) {
        const value = pi[configKey] ?? ai[configKey];
        if (value) {
          input.focus();
          await fillDelay();
          setNativeValue(input, value);
          await fillDelay();
          piFilled++;
        }
        break;
      }
    }
  }

  addStep(result, "Personal Info", "done", piFilled, piTotal);

  // ── Step 2: Heuristic dropdown fill ───────────────────────────────────
  ctx.onStep({ name: "Dropdowns", status: "filling" });

  let ddFilled = 0;
  let ddTotal = 0;

  const selects = document.querySelectorAll<HTMLSelectElement>("select");

  for (const select of selects) {
    if (select.offsetParent === null) continue;

    const selectId = (select.id ?? "").toLowerCase();
    const selectName = (select.name ?? "").toLowerCase();
    const combined = `${selectId} ${selectName}`;

    ddTotal++;

    for (const [pattern, configKey] of Object.entries(GENERIC_DROPDOWN_MAPPINGS)) {
      if (combined.includes(pattern)) {
        const value =
          (ai[configKey] as string) ??
          (ctx.config.work_authorization[configKey] as string) ??
          GENERIC_DROPDOWN_DEFAULTS[configKey];

        if (value) {
          // Use the select's actual id/name for a precise selector
          const idSel = select.id ? `select#${CSS.escape(select.id)}` : null;
          const nameSel = select.name ? `select[name='${select.name}']` : null;
          const selectors = [idSel, nameSel].filter(Boolean) as string[];

          if (await selectDropdown(selectors, value)) {
            ddFilled++;
          }
        }
        break;
      }
    }
  }

  addStep(result, "Dropdowns", ddFilled > 0 ? "done" : "skipped", ddFilled, ddTotal);

  // ── Step 3: Work Experience ───────────────────────────────────────────
  ctx.onStep({ name: "Work Experience", status: "filling" });

  const workFilled = await fillWorkExperienceSection(
    ctx,
    WORK_EXPERIENCE_SELECTORS,
    WORK_EXPERIENCE_XPATH,
    [],
    [
      "//button[contains(text(), 'Add Another')]",
      "//button[contains(text(), 'Add Work Experience')]",
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
    [],
    [
      "//button[contains(text(), 'Add Another')]",
      "//button[contains(text(), 'Add Education')]",
    ],
  );

  addStep(
    result,
    "Education",
    eduFilled > 0 ? "done" : "skipped",
    eduFilled,
    ctx.resumeComponents?.education?.length ?? 0,
  );

  // ── Step 5: Resume Upload ─────────────────────────────────────────────
  ctx.onStep({ name: "Resume Upload", status: "filling" });

  const uploaded = uploadResume(RESUME_UPLOAD_SELECTORS, ctx.resumePdfBase64);
  addStep(result, "Resume Upload", uploaded ? "done" : "skipped", uploaded ? 1 : 0, 1);

  await fillDelay();
  return result;
}
