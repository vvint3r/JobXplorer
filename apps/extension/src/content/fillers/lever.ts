// ── Lever ATS Form Filler ────────────────────────────────────────────────────
// Lever uses a single-page form at jobs.lever.co/company/uuid/apply
// Fields are standard HTML inputs with name attributes.

import { SEL, XPATH } from "@shared/selectors/lever";
import type { FillResult } from "@shared/types";
import {
  type FillerContext,
  fillTextField,
  setNativeValue,
  uploadResume,
  createFillResult,
  addStep,
  fillDelay,
  clickElement,
  queryFirst,
} from "./base";

export async function fillLever(ctx: FillerContext): Promise<FillResult> {
  const result = createFillResult();
  const pi = ctx.config.personal_info;
  const ai = ctx.config.application_info;

  // ── Step 1: Personal Info ────────────────────────────────────────────────
  ctx.onStep({ name: "Personal Info", status: "filling" });

  let piFilled = 0;

  // Lever uses a single full-name field — concatenate first + last
  const fullName = [pi.first_name, pi.last_name].filter(Boolean).join(" ");
  if (fullName && await fillTextField([...SEL.fullName], fullName)) piFilled++;
  if (pi.email && await fillTextField([...SEL.email], pi.email)) piFilled++;
  if (pi.phone && await fillTextField([...SEL.phone], pi.phone)) piFilled++;

  // Current company — use most recent work experience if available
  const currentCompany =
    ctx.resumeComponents?.work_experience?.[0]?.company ?? "";
  if (currentCompany && await fillTextField([...SEL.currentCompany], currentCompany)) piFilled++;

  // LinkedIn URL
  if (pi.linkedin_profile && await fillTextField([...SEL.linkedin], pi.linkedin_profile)) piFilled++;

  addStep(result, "Personal Info", piFilled > 0 ? "done" : "skipped", piFilled, 5);

  // ── Step 2: Resume Upload ────────────────────────────────────────────────
  ctx.onStep({ name: "Resume Upload", status: "filling" });

  const uploaded = uploadResume([...SEL.resumeUpload], ctx.resumePdfBase64);
  addStep(result, "Resume Upload", uploaded ? "done" : "skipped", uploaded ? 1 : 0, 1);

  await fillDelay();

  // ── Step 3: Custom Questions ─────────────────────────────────────────────
  ctx.onStep({ name: "Custom Questions", status: "filling" });

  let cqFilled = 0;
  let cqTotal = 0;

  // Text inputs with cards prefix
  const customInputs = document.querySelectorAll<HTMLInputElement>(
    SEL.customTextInputs[0],
  );
  for (const input of customInputs) {
    if (input.offsetParent === null || input.value) continue;
    cqTotal++;
    // Try to find a matching answer from custom_answers config
    const label = _getLabelText(input);
    const answer = _findCustomAnswer(ctx, label);
    if (answer) {
      input.focus();
      await fillDelay();
      setNativeValue(input, answer);
      await fillDelay();
      cqFilled++;
    }
  }

  // Textareas with cards prefix
  const customTextareas = document.querySelectorAll<HTMLTextAreaElement>(
    SEL.customTextareas[0],
  );
  for (const ta of customTextareas) {
    if (ta.offsetParent === null || ta.value) continue;
    cqTotal++;
    const label = _getLabelText(ta);
    const answer = _findCustomAnswer(ctx, label);
    if (answer) {
      ta.focus();
      await fillDelay();
      setNativeValue(ta as unknown as HTMLInputElement, answer);
      await fillDelay();
      cqFilled++;
    }
  }

  addStep(
    result,
    "Custom Questions",
    cqTotal === 0 ? "skipped" : cqFilled > 0 ? "done" : "skipped",
    cqFilled,
    cqTotal,
  );

  // ── Step 4: Work Authorization dropdowns ─────────────────────────────────
  ctx.onStep({ name: "Work Authorization", status: "filling" });

  // Lever sometimes has work auth selects — handled via heuristic scan
  let waFilled = 0;
  const selects = document.querySelectorAll<HTMLSelectElement>(
    SEL.customSelects[0],
  );
  for (const sel of selects) {
    if (sel.offsetParent === null) continue;
    const label = _getLabelText(sel).toLowerCase();
    if (label.includes("authoriz") || label.includes("sponsor") || label.includes("visa")) {
      const value = label.includes("sponsor") || label.includes("visa")
        ? (ctx.config.work_authorization?.require_visa_sponsorship ?? "No")
        : (ctx.config.work_authorization?.legally_authorized_to_work ?? "Yes");
      const opt = Array.from(sel.options).find(
        (o) => o.text.toLowerCase().includes(value.toString().toLowerCase()),
      );
      if (opt) {
        sel.value = opt.value;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        waFilled++;
      }
    }
  }
  addStep(result, "Work Authorization", waFilled > 0 ? "done" : "skipped", waFilled, 0);

  await fillDelay();
  return result;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _getLabelText(el: HTMLElement): string {
  // Look for associated <label> or aria-label
  const id = el.id;
  if (id) {
    const label = document.querySelector<HTMLLabelElement>(`label[for="${id}"]`);
    if (label) return label.textContent?.trim() ?? "";
  }
  const ariaLabel = el.getAttribute("aria-label");
  if (ariaLabel) return ariaLabel;

  // Walk up to find a wrapping label or legend
  let parent = el.parentElement;
  while (parent && parent !== document.body) {
    if (parent.tagName === "LABEL" || parent.tagName === "FIELDSET") {
      return parent.textContent?.trim() ?? "";
    }
    parent = parent.parentElement;
  }
  return "";
}

function _findCustomAnswer(ctx: FillerContext, label: string): string | null {
  if (!label) return null;
  const lower = label.toLowerCase();
  const answers = ctx.config.custom_answers ?? {};
  // Exact or substring match against stored custom answers
  for (const [key, val] of Object.entries(answers)) {
    if (lower.includes(key.toLowerCase()) || key.toLowerCase().includes(lower)) {
      return String(val);
    }
  }
  // Work auth fallbacks
  if (lower.includes("authoriz")) return String(ctx.config.work_authorization?.legally_authorized_to_work ?? "Yes");
  if (lower.includes("sponsor") || lower.includes("visa")) return String(ctx.config.work_authorization?.require_visa_sponsorship ?? "No");
  return null;
}
