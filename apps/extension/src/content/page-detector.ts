// ── Page Detector ───────────────────────────────────────────────────────────
// Checks if the current page looks like a job application form.

import { FORM_INDICATORS } from "@shared/selectors/generic";

/**
 * Returns true if the current page has at least 2 form indicators,
 * suggesting it's an application form rather than just a job listing.
 */
export function isApplicationForm(): boolean {
  let found = 0;
  for (const selector of FORM_INDICATORS) {
    if (document.querySelector(selector)) {
      found++;
      if (found >= 2) return true;
    }
  }
  return false;
}
