// ── Base Form Filler ────────────────────────────────────────────────────────
// Port of src/auto_application/form_fillers/base.py
// Provides DOM manipulation primitives shared by all board-specific fillers.

import {
  FILL_DELAY_MIN,
  FILL_DELAY_MAX,
  CLICK_DELAY_MIN,
  CLICK_DELAY_MAX,
  ELEMENT_WAIT_TIMEOUT,
  MAX_WORK_EXPERIENCE,
  MAX_EDUCATION,
} from "@shared/constants";
import type {
  UserConfig,
  ResumeComponents,
  FillResult,
  FillStep,
  WorkExperience,
  Education,
} from "@shared/types";
import { uploadFileFromBase64 } from "./file-upload";

// ── Helpers ─────────────────────────────────────────────────────────────────

function randomDelay(min: number, max: number): Promise<void> {
  const ms = Math.floor(Math.random() * (max - min)) + min;
  return new Promise((r) => setTimeout(r, ms));
}

export const fillDelay = () => randomDelay(FILL_DELAY_MIN, FILL_DELAY_MAX);
export const clickDelay = () => randomDelay(CLICK_DELAY_MIN, CLICK_DELAY_MAX);

/**
 * Native value setter — bypasses React/Angular synthetic event wrappers.
 * Sets the value directly on the underlying HTMLInputElement prototype,
 * then dispatches real DOM events so frameworks detect the change.
 */
const nativeInputSetter = Object.getOwnPropertyDescriptor(
  HTMLInputElement.prototype,
  "value",
)?.set;

const nativeTextareaSetter = Object.getOwnPropertyDescriptor(
  HTMLTextAreaElement.prototype,
  "value",
)?.set;

export function setNativeValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const setter = el instanceof HTMLTextAreaElement ? nativeTextareaSetter : nativeInputSetter;
  if (setter) {
    setter.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.dispatchEvent(new Event("blur", { bubbles: true }));
}

// ── Element Finders ─────────────────────────────────────────────────────────

/** Try a list of CSS selectors, return the first visible match. */
export function queryFirst(selectors: readonly string[]): HTMLElement | null {
  for (const sel of selectors) {
    const el = document.querySelector<HTMLElement>(sel);
    if (el && el.offsetParent !== null) return el;
  }
  return null;
}

/** Try a list of XPath expressions, return the first visible match. */
export function queryFirstXPath(xpaths: readonly string[]): HTMLElement | null {
  for (const xpath of xpaths) {
    const result = document.evaluate(
      xpath,
      document,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null,
    );
    const el = result.singleNodeValue as HTMLElement | null;
    if (el && el.offsetParent !== null) return el;
  }
  return null;
}

/** Combined CSS + XPath lookup with fallback. */
export function findElement(
  cssSelectors: readonly string[],
  xpathSelectors: readonly string[] = [],
): HTMLElement | null {
  return queryFirst(cssSelectors) ?? queryFirstXPath(xpathSelectors);
}

/** Wait for an element matching any selector to appear in the DOM. */
export function waitForElement(
  selectors: readonly string[],
  timeout = ELEMENT_WAIT_TIMEOUT,
): Promise<HTMLElement | null> {
  return new Promise((resolve) => {
    // Check immediately
    const existing = queryFirst(selectors);
    if (existing) {
      resolve(existing);
      return;
    }

    const timer = setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, timeout);

    const observer = new MutationObserver(() => {
      const el = queryFirst(selectors);
      if (el) {
        clearTimeout(timer);
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
  });
}

// ── Field Fillers ───────────────────────────────────────────────────────────

/** Fill a text input or textarea. Returns true if filled. */
export async function fillTextField(
  selectors: readonly string[],
  value: string | undefined,
  xpathSelectors: readonly string[] = [],
): Promise<boolean> {
  if (!value) return false;
  const el = findElement(selectors, xpathSelectors) as
    | HTMLInputElement
    | HTMLTextAreaElement
    | null;
  if (!el) return false;

  el.focus();
  await fillDelay();

  // Clear existing value
  setNativeValue(el, "");
  await fillDelay();

  // Set new value
  setNativeValue(el, value);
  await fillDelay();

  return true;
}

/** Select an option from a <select> dropdown. Returns true if selected. */
export async function selectDropdown(
  selectors: readonly string[],
  value: string | undefined,
  matchType: "exact" | "contains" = "contains",
): Promise<boolean> {
  if (!value) return false;
  const el = queryFirst(selectors) as HTMLSelectElement | null;
  if (!el || el.tagName !== "SELECT") return false;

  const options = Array.from(el.options);
  const match = options.find((opt) => {
    const text = opt.text.trim();
    return matchType === "exact" ? text === value : text.includes(value);
  });

  if (match) {
    el.value = match.value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await fillDelay();
    return true;
  }

  return false;
}

/**
 * Click a custom dropdown (button-opens-listbox pattern used by Workday etc.)
 * and select an option by text content.
 */
export async function selectCustomDropdown(
  buttonSelectors: readonly string[],
  value: string | undefined,
): Promise<boolean> {
  if (!value) return false;
  const button = queryFirst(buttonSelectors);
  if (!button) return false;

  button.click();
  await clickDelay();

  // Look for the option in the opened list
  const optionXPaths = [
    `//div[contains(@role, 'option') and contains(text(), '${value}')]`,
    `//li[contains(text(), '${value}')]`,
    `//div[contains(@class, 'option') and contains(text(), '${value}')]`,
    `//div[contains(@data-automation-id, 'option') and contains(text(), '${value}')]`,
  ];

  const option = queryFirstXPath(optionXPaths);
  if (option) {
    option.click();
    await fillDelay();
    return true;
  }

  // Try typing into search input if one appeared
  const searchInput = document.querySelector<HTMLInputElement>(
    "input[type='search'], input[data-automation-id*='search']",
  );
  if (searchInput) {
    setNativeValue(searchInput, value);
    await clickDelay();
    // Press Enter
    searchInput.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await fillDelay();
    return true;
  }

  // Close dropdown if we couldn't select
  document.body.dispatchEvent(
    new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
  );
  return false;
}

/** Click a button/link element. */
export async function clickElement(
  selectors: readonly string[],
  xpathSelectors: readonly string[] = [],
): Promise<boolean> {
  const el = findElement(selectors, xpathSelectors);
  if (!el) return false;

  el.scrollIntoView({ behavior: "smooth", block: "center" });
  await clickDelay();
  el.click();
  await clickDelay();
  return true;
}

/** Check or uncheck a checkbox. */
export async function setCheckbox(
  selectors: readonly string[],
  checked: boolean,
): Promise<boolean> {
  const el = queryFirst(selectors) as HTMLInputElement | null;
  if (!el) return false;

  if (el.checked !== checked) {
    el.click();
    await fillDelay();
  }
  return true;
}

// ── Month/Year Helpers ──────────────────────────────────────────────────────

const MONTH_NAMES: Record<string, string> = {
  "01": "January", "02": "February", "03": "March", "04": "April",
  "05": "May", "06": "June", "07": "July", "08": "August",
  "09": "September", "10": "October", "11": "November", "12": "December",
};

export async function selectMonth(
  selectors: readonly string[],
  monthNum: string | undefined,
): Promise<boolean> {
  if (!monthNum) return false;
  const monthName = MONTH_NAMES[monthNum] ?? "";
  // Try name first, then number
  return (
    (await selectDropdown(selectors, monthName)) ||
    (await selectDropdown(selectors, monthNum))
  );
}

export async function fillYear(
  selectors: readonly string[],
  year: string | undefined,
): Promise<boolean> {
  if (!year) return false;
  // Try as dropdown first, then as text
  return (
    (await selectDropdown(selectors, year, "exact")) ||
    (await fillTextField(selectors, year))
  );
}

// ── Composite Sections ──────────────────────────────────────────────────────

export interface FillerContext {
  config: UserConfig;
  resumeComponents: ResumeComponents | null;
  resumePdfBase64: string | null;
  onStep: (step: FillStep) => void;
}

/**
 * Fill work experience entries using resume components data.
 * Returns number of entries filled.
 */
export async function fillWorkExperienceSection(
  ctx: FillerContext,
  fieldSelectors: Record<string, readonly string[]>,
  xpathSelectors: Record<string, readonly string[]>,
  addButtonSelectors: readonly string[],
  addButtonXPaths: readonly string[],
): Promise<number> {
  if (!ctx.resumeComponents?.work_experience?.length) return 0;

  const entries = ctx.resumeComponents.work_experience.slice(0, MAX_WORK_EXPERIENCE);
  let filled = 0;

  for (let i = 0; i < entries.length; i++) {
    const exp = entries[i];
    if (await fillSingleWorkExperience(exp, fieldSelectors, xpathSelectors)) {
      filled++;
    }
    // Click "Add Another" if more entries follow
    if (i < entries.length - 1) {
      await clickElement(addButtonSelectors, addButtonXPaths);
      await clickDelay();
    }
  }
  return filled;
}

async function fillSingleWorkExperience(
  exp: WorkExperience,
  sel: Record<string, readonly string[]>,
  xpath: Record<string, readonly string[]>,
): Promise<boolean> {
  let ok = true;

  if (!(await fillTextField(sel.jobTitle ?? [], exp.job_title, xpath.jobTitle ?? []))) ok = false;
  if (!(await fillTextField(sel.company ?? [], exp.company, xpath.company ?? []))) ok = false;

  if (exp.currently_work_here) {
    await setCheckbox(sel.currentlyWorkHere ?? [], true);
  }

  await selectMonth(sel.fromMonth ?? [], exp.from?.month);
  await fillYear(sel.fromYear ?? [], exp.from?.year);

  if (!exp.currently_work_here) {
    await selectMonth(sel.toMonth ?? [], exp.to?.month);
    await fillYear(sel.toYear ?? [], exp.to?.year);
  }

  await fillTextField(sel.description ?? [], exp.role_description, xpath.description ?? []);

  return ok;
}

/**
 * Fill education entries using resume components data.
 * Returns number of entries filled.
 */
export async function fillEducationSection(
  ctx: FillerContext,
  fieldSelectors: Record<string, readonly string[]>,
  xpathSelectors: Record<string, readonly string[]>,
  addButtonSelectors: readonly string[],
  addButtonXPaths: readonly string[],
): Promise<number> {
  if (!ctx.resumeComponents?.education?.length) return 0;

  const entries = ctx.resumeComponents.education.slice(0, MAX_EDUCATION);
  let filled = 0;

  for (let i = 0; i < entries.length; i++) {
    const edu = entries[i];
    if (await fillSingleEducation(edu, fieldSelectors, xpathSelectors)) {
      filled++;
    }
    if (i < entries.length - 1) {
      await clickElement(addButtonSelectors, addButtonXPaths);
      await clickDelay();
    }
  }
  return filled;
}

async function fillSingleEducation(
  edu: Education,
  sel: Record<string, readonly string[]>,
  xpath: Record<string, readonly string[]>,
): Promise<boolean> {
  let ok = true;

  if (!(await fillTextField(sel.school ?? [], edu.school_or_university, xpath.school ?? []))) ok = false;

  // Try degree dropdown first, fall back to text
  const degreeSet =
    (await selectDropdown(sel.degreeDropdown ?? [], edu.degree, "contains")) ||
    (await fillTextField(sel.degreeText ?? [], `${edu.degree} in ${edu.field_of_study}`, xpath.degreeText ?? []));
  if (!degreeSet) ok = false;

  await fillTextField(sel.fieldOfStudy ?? [], edu.field_of_study, xpath.fieldOfStudy ?? []);
  await fillYear(sel.fromYear ?? [], edu.from?.year);
  await fillYear(sel.toYear ?? [], edu.to?.year);
  await fillTextField(sel.gpa ?? [], edu.gpa);

  return ok;
}

/** Upload resume PDF via DataTransfer API. */
export function uploadResume(
  selectors: readonly string[],
  base64Data: string | null,
  filename = "resume.pdf",
): boolean {
  if (!base64Data) return false;

  for (const sel of selectors) {
    const input = document.querySelector<HTMLInputElement>(sel);
    if (input && input.type === "file") {
      return uploadFileFromBase64(input, base64Data, filename);
    }
  }
  return false;
}

// ── Result Builder ──────────────────────────────────────────────────────────

export function createFillResult(): FillResult {
  return { fieldsTotal: 0, fieldsFilled: 0, errors: [], steps: [] };
}

export function addStep(
  result: FillResult,
  name: string,
  status: FillStep["status"],
  fieldsFilled = 0,
  fieldsTotal = 0,
  error?: string,
): FillStep {
  const step: FillStep = { name, status, fieldsFilled, fieldsTotal, error };
  result.steps.push(step);
  result.fieldsTotal += fieldsTotal;
  result.fieldsFilled += fieldsFilled;
  if (error) result.errors.push(error);
  return step;
}
