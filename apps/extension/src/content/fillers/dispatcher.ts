// ── Filler Dispatcher ───────────────────────────────────────────────────────
// Detects the job board from the current URL and dispatches to the
// appropriate board-specific filler.

import { detectJobBoard } from "@shared/job-board-detector";
import type { FillResult, FillStep, UserConfig, ResumeComponents } from "@shared/types";
import type { FillerContext } from "./base";
import { createFillResult, addStep } from "./base";
import { fillGreenhouse } from "./greenhouse";
import { fillWorkday } from "./workday";
import { fillLever } from "./lever";
import { fillSmartRecruiters } from "./smartrecruiters";
import { fillLinkedIn } from "./linkedin";
import { fillGeneric } from "./generic";

export type BoardType = "greenhouse" | "workday" | "lever" | "smartrecruiters" | "linkedin" | "generic";

export interface DispatcherOptions {
  config: UserConfig;
  resumeComponents: ResumeComponents | null;
  resumePdfBase64: string | null;
  onStep: (step: FillStep) => void;
  onSignInRequired: () => Promise<void>;
}

/**
 * Detect the board type and run the appropriate filler.
 * Returns the fill result and the detected board type.
 */
export async function dispatchFill(
  opts: DispatcherOptions,
): Promise<{ boardType: BoardType; result: FillResult }> {
  const url = window.location.href;
  const detected = detectJobBoard(url);

  const ctx: FillerContext = {
    config: opts.config,
    resumeComponents: opts.resumeComponents,
    resumePdfBase64: opts.resumePdfBase64,
    onStep: opts.onStep,
  };

  let boardType: BoardType;
  let result: FillResult;

  switch (detected) {
    case "greenhouse":
      boardType = "greenhouse";
      result = await fillGreenhouse(ctx);
      break;

    case "workday":
      boardType = "workday";
      result = await fillWorkday(ctx, opts.onSignInRequired);
      break;

    case "lever":
      boardType = "lever";
      result = await fillLever(ctx);
      break;

    case "smartrecruiters":
      boardType = "smartrecruiters";
      result = await fillSmartRecruiters(ctx);
      break;

    case "linkedin":
      boardType = "linkedin";
      result = await fillLinkedIn(ctx);
      break;

    default:
      boardType = "generic";
      result = await fillGeneric(ctx);
      break;
  }

  return { boardType, result };
}
