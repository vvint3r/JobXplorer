import type { BoardFeatures } from "./types";

// ── URL Patterns ─────────────────────────────────────────────────────────────

const JOB_BOARD_PATTERNS: Record<string, RegExp[]> = {
  greenhouse: [/greenhouse\.io/i, /boards\.greenhouse\.io/i, /job-boards\.greenhouse\.io/i],
  workday: [/workday\.com/i, /myworkdayjobs\.com/i],
  lever: [/lever\.co/i, /jobs\.lever\.co/i],
  smartrecruiters: [/smartrecruiters\.com/i],
  icims: [/icims\.com/i],
  taleo: [/taleo\.net/i, /taleo\.com/i],
  jobvite: [/jobvite\.com/i],
  bamboohr: [/bamboohr\.com/i],
  linkedin: [/linkedin\.com\/jobs/i],
  indeed: [/indeed\.com/i],
  glassdoor: [/glassdoor\.com/i],
};

// ── Feature Matrix ───────────────────────────────────────────────────────────

const BOARD_FEATURES: Record<string, BoardFeatures> = {
  greenhouse: {
    auto_fill_supported: true,
    file_upload_supported: true,
    custom_questions: true,
    requires_manual_review: false,
  },
  workday: {
    auto_fill_supported: true,
    file_upload_supported: true,
    custom_questions: true,
    requires_manual_review: true,
  },
  lever: {
    auto_fill_supported: true,
    file_upload_supported: true,
    custom_questions: true,
    requires_manual_review: false,
  },
  smartrecruiters: {
    auto_fill_supported: true,
    file_upload_supported: true,
    custom_questions: true,
    requires_manual_review: false,
  },
  linkedin: {
    auto_fill_supported: true,
    file_upload_supported: true,
    custom_questions: false,
    requires_manual_review: false,
  },
  generic: {
    auto_fill_supported: true,
    file_upload_supported: true,
    custom_questions: true,
    requires_manual_review: true,
  },
};

// ── Public API ───────────────────────────────────────────────────────────────

/** Detect job board type from a URL string. Returns 'generic' if no match. */
export function detectJobBoard(url: string): string {
  for (const [board, patterns] of Object.entries(JOB_BOARD_PATTERNS)) {
    if (patterns.some((re) => re.test(url))) {
      return board;
    }
  }
  return "generic";
}

/** Get board type and feature matrix for a URL. */
export function getJobBoardInfo(url: string): { type: string; features: BoardFeatures } {
  const type = detectJobBoard(url);
  const features = BOARD_FEATURES[type] ?? BOARD_FEATURES.generic;
  return { type, features };
}

/** Check if a URL belongs to a known ATS (non-generic). */
export function isKnownJobBoard(url: string): boolean {
  return detectJobBoard(url) !== "generic";
}
