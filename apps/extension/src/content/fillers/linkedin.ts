// ── LinkedIn Easy Apply Filler ────────────────────────────────────────────────
// Fills the LinkedIn Easy Apply sidebar modal on linkedin.com/jobs pages.
// Steps: contact info → resume → screening questions → review → submit

import { SEL, XPATH, STEP_KEYWORDS } from "@shared/selectors/linkedin";
import type { FillResult } from "@shared/types";
import {
  type FillerContext,
  fillTextField,
  selectDropdown,
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

const MAX_STEPS = 10;

export async function fillLinkedIn(ctx: FillerContext): Promise<FillResult> {
  const result = createFillResult();

  // ── Step 0: Open the Easy Apply modal if not already open ────────────────
  const modal = queryFirst([...SEL.modal]);
  if (!modal) {
    ctx.onStep({ name: "Opening Easy Apply", status: "filling" });
    const opened = await clickElement([...SEL.easyApplyButton], []);
    if (!opened) {
      addStep(result, "Open Modal", "error", 0, 0, "Easy Apply button not found");
      return result;
    }
    // Wait for modal to appear
    const appeared = await waitForElement([...SEL.modal], 5000);
    if (!appeared) {
      addStep(result, "Open Modal", "error", 0, 0, "Modal did not open");
      return result;
    }
    addStep(result, "Open Modal", "done", 1, 1);
    await fillDelay();
  }

  // ── Step loop: iterate through wizard steps ──────────────────────────────
  for (let step = 0; step < MAX_STEPS; step++) {
    const stepType = _detectStep();
    ctx.onStep({ name: stepType, status: "filling" });

    let filled = 0;

    if (stepType === "Contact Info") {
      const pi = ctx.config.personal_info;
      if (pi.phone && await fillTextField([...SEL.phone], pi.phone)) filled++;
      // Phone country code dropdown (if present)
      if (pi.phone_country_code) {
        await selectDropdown([...SEL.phoneCountryCode], pi.phone_country_code);
      }
      addStep(result, "Contact Info", filled > 0 ? "done" : "skipped", filled, 1);

    } else if (stepType === "Resume") {
      // Prefer existing uploaded resume if listed; otherwise upload new
      const existingResume = queryFirst([...SEL.resumeOption]);
      if (existingResume) {
        // Click the first resume option to select it
        existingResume.click();
        addStep(result, "Resume", "done", 1, 1);
        filled++;
      } else {
        const uploaded = uploadResume([...SEL.resumeUpload], ctx.resumePdfBase64);
        addStep(result, "Resume Upload", uploaded ? "done" : "skipped", uploaded ? 1 : 0, 1);
        if (uploaded) filled++;
      }

    } else if (stepType === "Screening Questions") {
      filled = await _fillScreeningQuestions(ctx);
      addStep(result, "Screening Questions", filled > 0 ? "done" : "skipped", filled, 0);

    } else if (stepType === "Review") {
      addStep(result, "Review", "done", 0, 0);
      // Leave final submission to the user
      break;
    }

    await fillDelay();

    // Check if submit is now visible after filling — leave for user to confirm
    const submitBtn = queryFirst([...SEL.submitButton]);
    if (submitBtn) {
      addStep(result, "Ready to Submit", "done", 0, 0);
      break;
    }

    // Click Next / Continue
    const advanced = await clickElement([...SEL.nextButton], [...XPATH.nextButton]);
    if (!advanced) {
      // If we can't advance, we may be on the final step already
      addStep(result, `Step ${step + 1}`, "error", filled, 0, "Could not advance — check form manually");
      break;
    }

    await new Promise((r) => setTimeout(r, 1000));
  }

  return result;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _detectStep(): string {
  const headerEl = queryFirst([...SEL.modalHeader]);
  const text = (headerEl?.textContent ?? "").toLowerCase().trim();

  if (STEP_KEYWORDS.contact.some((kw) => text.includes(kw))) return "Contact Info";
  if (STEP_KEYWORDS.resume.some((kw) => text.includes(kw))) return "Resume";
  if (STEP_KEYWORDS.questions.some((kw) => text.includes(kw))) return "Screening Questions";
  if (STEP_KEYWORDS.review.some((kw) => text.includes(kw))) return "Review";

  // Fallback: look for visible input fields to infer step type
  const hasFileInput = !!document.querySelector(".jobs-easy-apply-content input[type='file']");
  if (hasFileInput) return "Resume";

  return `Step (${text.slice(0, 30) || "unknown"})`;
}

async function _fillScreeningQuestions(ctx: FillerContext): Promise<number> {
  let filled = 0;
  const answers = ctx.config.custom_answers ?? {};

  // Text inputs
  const inputs = document.querySelectorAll<HTMLInputElement>(
    ".jobs-easy-apply-form-element input[type='text'], .jobs-easy-apply-form-element input[type='number']",
  );
  for (const input of inputs) {
    if (input.offsetParent === null || input.value) continue;
    const label = _getAriaLabel(input);
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
  const textareas = document.querySelectorAll<HTMLTextAreaElement>(
    ".jobs-easy-apply-form-element textarea",
  );
  for (const ta of textareas) {
    if (ta.offsetParent === null || ta.value) continue;
    const label = _getAriaLabel(ta);
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
  const selects = document.querySelectorAll<HTMLSelectElement>(
    ".jobs-easy-apply-form-element select",
  );
  for (const sel of selects) {
    if (sel.offsetParent === null) continue;
    const label = _getAriaLabel(sel).toLowerCase();
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

function _getAriaLabel(el: HTMLElement): string {
  const ariaLabel = el.getAttribute("aria-label");
  if (ariaLabel) return ariaLabel;
  const labelledBy = el.getAttribute("aria-labelledby");
  if (labelledBy) {
    const labelEl = document.getElementById(labelledBy);
    if (labelEl) return labelEl.textContent?.trim() ?? "";
  }
  const id = el.id;
  if (id) {
    const label = document.querySelector<HTMLLabelElement>(`label[for="${id}"]`);
    if (label) return label.textContent?.trim() ?? "";
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
  if (lower.includes("years") || lower.includes("experience")) return "3";
  return null;
}
