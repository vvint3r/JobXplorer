// ── SmartRecruiters ATS Form Filler ──────────────────────────────────────────
// Multi-step wizard at jobs.smartrecruiters.com/company/job/apply
// Steps detected by h1 text; navigated via data-testid buttons.

import { SEL, XPATH, STEP_KEYWORDS } from "@shared/selectors/smartrecruiters";
import type { FillResult } from "@shared/types";
import {
  type FillerContext,
  fillTextField,
  uploadResume,
  clickElement,
  waitForElement,
  createFillResult,
  addStep,
  fillDelay,
  clickDelay,
  queryFirst,
  setNativeValue,
} from "./base";

const MAX_STEPS = 8;

export async function fillSmartRecruiters(ctx: FillerContext): Promise<FillResult> {
  const result = createFillResult();

  // Wait for wizard to be ready
  const modalEl = await waitForElement([...SEL.stepTitle], 5000);
  if (!modalEl) {
    addStep(result, "Page Load", "error", 0, 0, "SmartRecruiters form not found");
    return result;
  }

  for (let step = 0; step < MAX_STEPS; step++) {
    const stepName = _detectStep();
    ctx.onStep({ name: stepName, status: "filling" });

    let filled = 0;

    if (stepName === "Personal Info") {
      const pi = ctx.config.personal_info;
      if (pi.first_name && await fillTextField([...SEL.firstName], pi.first_name)) filled++;
      if (pi.last_name && await fillTextField([...SEL.lastName], pi.last_name)) filled++;
      if (pi.email && await fillTextField([...SEL.email], pi.email)) filled++;
      if (pi.phone && await fillTextField([...SEL.phone], pi.phone)) filled++;
      addStep(result, "Personal Info", filled > 0 ? "done" : "skipped", filled, 4);

    } else if (stepName === "Resume") {
      const uploaded = uploadResume([...SEL.resumeUpload], ctx.resumePdfBase64);
      addStep(result, "Resume Upload", uploaded ? "done" : "skipped", uploaded ? 1 : 0, 1);

    } else if (stepName === "Screening Questions") {
      const qFilled = await _fillScreeningQuestions(ctx);
      addStep(result, "Screening Questions", qFilled > 0 ? "done" : "skipped", qFilled, 0);

    } else if (stepName === "Review") {
      addStep(result, "Review", "done", 0, 0);
      // Don't auto-submit — leave for user
      break;
    }

    await fillDelay();

    // Check if submit button is now visible (last step)
    const submitBtn = queryFirst([...SEL.submitButton]);
    if (submitBtn) {
      addStep(result, "Ready to Submit", "done", 0, 0);
      break;
    }

    // Advance to next step
    const advanced = await clickElement([...SEL.nextButton], [...XPATH.nextButton]);
    if (!advanced) {
      addStep(result, `Step ${step + 1} Navigation`, "error", 0, 0, "Could not find Next button");
      break;
    }

    // Wait for next step to load
    await new Promise((r) => setTimeout(r, 1200));
  }

  return result;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _detectStep(): string {
  const titleEl = queryFirst([...SEL.stepTitle]);
  const text = (titleEl?.textContent ?? "").toLowerCase().trim();

  if (STEP_KEYWORDS.personalInfo.some((kw) => text.includes(kw))) return "Personal Info";
  if (STEP_KEYWORDS.resume.some((kw) => text.includes(kw))) return "Resume";
  if (STEP_KEYWORDS.questions.some((kw) => text.includes(kw))) return "Screening Questions";
  if (STEP_KEYWORDS.review.some((kw) => text.includes(kw))) return "Review";
  return `Step (${text.slice(0, 30) || "unknown"})`;
}

async function _fillScreeningQuestions(ctx: FillerContext): Promise<number> {
  let filled = 0;
  const answers = ctx.config.custom_answers ?? {};

  // Text inputs
  const inputs = document.querySelectorAll<HTMLInputElement>(SEL.customInputs[0]);
  for (const input of inputs) {
    if (input.offsetParent === null || input.value) continue;
    const label = _getLabel(input);
    const answer = _matchAnswer(answers, label, ctx);
    if (answer) {
      input.focus();
      await fillDelay();
      setNativeValue(input, answer);
      await fillDelay();
      filled++;
    }
  }

  // Textareas
  const textareas = document.querySelectorAll<HTMLTextAreaElement>(SEL.customTextareas[0]);
  for (const ta of textareas) {
    if (ta.offsetParent === null || ta.value) continue;
    const label = _getLabel(ta);
    const answer = _matchAnswer(answers, label, ctx);
    if (answer) {
      ta.focus();
      await fillDelay();
      setNativeValue(ta as unknown as HTMLInputElement, answer);
      await fillDelay();
      filled++;
    }
  }

  // Selects
  const selects = document.querySelectorAll<HTMLSelectElement>(SEL.customSelects[0]);
  for (const sel of selects) {
    if (sel.offsetParent === null) continue;
    const label = _getLabel(sel).toLowerCase();
    let value: string | undefined;
    if (label.includes("authoriz")) value = String(ctx.config.work_authorization?.legally_authorized_to_work ?? "Yes");
    if (label.includes("sponsor") || label.includes("visa")) value = String(ctx.config.work_authorization?.require_visa_sponsorship ?? "No");
    if (value) {
      const opt = Array.from(sel.options).find((o) => o.text.toLowerCase().includes(value!.toLowerCase()));
      if (opt) {
        sel.value = opt.value;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        filled++;
      }
    }
  }

  return filled;
}

function _getLabel(el: HTMLElement): string {
  const id = el.id;
  if (id) {
    const label = document.querySelector<HTMLLabelElement>(`label[for="${id}"]`);
    if (label) return label.textContent?.trim() ?? "";
  }
  const ariaLabel = el.getAttribute("aria-label") ?? el.getAttribute("aria-labelledby");
  if (ariaLabel) return ariaLabel;
  let parent = el.parentElement;
  while (parent) {
    const label = parent.querySelector("label");
    if (label && label !== el) return label.textContent?.trim() ?? "";
    parent = parent.parentElement;
  }
  return "";
}

function _matchAnswer(
  answers: Record<string, unknown>,
  label: string,
  ctx: FillerContext,
): string | null {
  const lower = label.toLowerCase();
  for (const [key, val] of Object.entries(answers)) {
    if (lower.includes(key.toLowerCase()) || key.toLowerCase().includes(lower)) {
      return String(val);
    }
  }
  if (lower.includes("authoriz")) return String(ctx.config.work_authorization?.legally_authorized_to_work ?? "Yes");
  if (lower.includes("sponsor") || lower.includes("visa")) return String(ctx.config.work_authorization?.require_visa_sponsorship ?? "No");
  return null;
}
