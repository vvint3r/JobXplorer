// ── Configuration Constants ──────────────────────────────────────────────────

/** Base URL for the JobXplore API. Override in extension settings for self-hosted. */
export const DEFAULT_API_URL = "http://localhost:8000";

/** Supabase project URL — set at build time or via settings. */
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? "";

/** Supabase anon key — set at build time or via settings. */
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

// ── Fill Behaviour ───────────────────────────────────────────────────────────

/** Random delay range (ms) between field fills — mimics human typing. */
export const FILL_DELAY_MIN = 150;
export const FILL_DELAY_MAX = 500;

/** Delay after clicking a button (ms) to let page settle. */
export const CLICK_DELAY_MIN = 300;
export const CLICK_DELAY_MAX = 800;

/** How long to wait for a DOM element to appear (ms) before giving up. */
export const ELEMENT_WAIT_TIMEOUT = 10_000;

/** Max steps in a multi-step form before aborting (prevents infinite loops). */
export const MAX_FORM_STEPS = 12;

/** Max work experience entries to fill. */
export const MAX_WORK_EXPERIENCE = 3;

/** Max education entries to fill. */
export const MAX_EDUCATION = 2;

// ── Cache ────────────────────────────────────────────────────────────────────

/** How long to cache user profile data in the background worker (ms). */
export const PROFILE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// ── Storage Keys ─────────────────────────────────────────────────────────────

export const STORAGE_KEYS = {
  JWT: "jx_jwt",
  REFRESH_TOKEN: "jx_refresh_token",
  EXPIRES_AT: "jx_expires_at",
  API_URL: "jx_api_url",
  SETTINGS: "jx_settings",
} as const;

// ── Extension Settings Defaults ──────────────────────────────────────────────

export interface ExtensionSettings {
  autoDetect: boolean;
  randomDelays: boolean;
  autoSubmit: boolean;
  fillVoluntaryDisclosures: boolean;
}

export const DEFAULT_SETTINGS: ExtensionSettings = {
  autoDetect: true,
  randomDelays: true,
  autoSubmit: false,
  fillVoluntaryDisclosures: false,
};
