// ── Content Script Entry Point ──────────────────────────────────────────────
// Runs at document_idle on all pages.
// Detects job boards, looks up the job in the user's DB, and mounts overlay.

import { detectJobBoard, isKnownJobBoard } from "@shared/job-board-detector";
import type { JobMatch } from "@shared/types";
import { isApplicationForm } from "./page-detector";
import { watchUrlChanges } from "./url-watcher";
import { mountOverlay, unmountOverlay } from "./overlay";

async function evaluate(): Promise<void> {
  const url = window.location.href;
  const board = detectJobBoard(url);

  // Quick bail: not a known job board and not a form page
  if (!board && !isKnownJobBoard(url) && !isApplicationForm()) {
    return;
  }

  // Check auth
  const authStatus = await chrome.runtime.sendMessage({ type: "AUTH_GET_STATUS" });
  if (!authStatus?.authenticated) {
    return; // Not logged in — do nothing silently
  }

  // Lookup the job by URL
  const jobMatch: JobMatch | null = await chrome.runtime.sendMessage({
    type: "API_LOOKUP_JOB_BY_URL",
    url,
  });

  // Mount overlay if we found a job or if we're on a recognized board
  if (jobMatch || board) {
    mountOverlay(jobMatch, board ?? "generic");
  }
}

// ── Initialize ──────────────────────────────────────────────────────────────

// Run immediately
evaluate().catch(console.error);

// Re-evaluate on SPA navigation
watchUrlChanges(() => {
  unmountOverlay();
  // Small delay to let the new page render
  setTimeout(() => evaluate().catch(console.error), 1000);
});
