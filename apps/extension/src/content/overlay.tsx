// ── JobXplore Overlay ───────────────────────────────────────────────────────
// Floating widget mounted in Shadow DOM on application pages.
// Shows job match info, auto-fill button, progress, and result.

import React, { useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import type { JobMatch, FillResult, FillStep, ApplicationLogPayload } from "@shared/types";
import { dispatchFill, type BoardType } from "./fillers/dispatcher";

import overlayStyles from "./overlay.css?inline";

// ── Shadow DOM Mount ────────────────────────────────────────────────────────

const CONTAINER_ID = "jobxplore-overlay-root";

export function mountOverlay(jobMatch: JobMatch | null, boardType: string): void {
  // Prevent double-mount
  if (document.getElementById(CONTAINER_ID)) return;

  const host = document.createElement("div");
  host.id = CONTAINER_ID;
  document.body.appendChild(host);

  const shadow = host.attachShadow({ mode: "closed" });

  // Inject styles
  const style = document.createElement("style");
  style.textContent = overlayStyles;
  shadow.appendChild(style);

  // Mount React
  const mountPoint = document.createElement("div");
  shadow.appendChild(mountPoint);

  const root = createRoot(mountPoint);
  root.render(<Overlay jobMatch={jobMatch} detectedBoard={boardType} />);
}

export function unmountOverlay(): void {
  const host = document.getElementById(CONTAINER_ID);
  if (host) host.remove();
}

// ── Step Icon ───────────────────────────────────────────────────────────────

function StepIcon({ status }: { status: FillStep["status"] }) {
  switch (status) {
    case "done": return <span className="jx-step-icon">+</span>;
    case "filling": return <span className="jx-step-icon">...</span>;
    case "error": return <span className="jx-step-icon">x</span>;
    case "skipped": return <span className="jx-step-icon">-</span>;
    default: return <span className="jx-step-icon">o</span>;
  }
}

// ── Overlay Component ───────────────────────────────────────────────────────

type OverlayState = "idle" | "filling" | "done" | "error" | "sign-in-required";

interface OverlayProps {
  jobMatch: JobMatch | null;
  detectedBoard: string;
}

function Overlay({ jobMatch, detectedBoard }: OverlayProps) {
  const [minimized, setMinimized] = useState(false);
  const [state, setState] = useState<OverlayState>("idle");
  const [steps, setSteps] = useState<FillStep[]>([]);
  const [result, setResult] = useState<FillResult | null>(null);
  const [fillBoardType, setFillBoardType] = useState<BoardType | null>(null);
  const [signInResolver, setSignInResolver] = useState<(() => void) | null>(null);

  const handleAutoFill = useCallback(async () => {
    setState("filling");
    setSteps([]);
    setResult(null);

    try {
      // Fetch user config from background
      const config = await chrome.runtime.sendMessage({ type: "API_GET_PROFILE" });
      if (config?.error) throw new Error(config.error);

      // Fetch optimized resume components + PDF if available
      let resumeComponents = null;
      let resumePdfBase64 = null;

      if (jobMatch?.optimized_resume_id) {
        [resumeComponents, resumePdfBase64] = await Promise.all([
          chrome.runtime.sendMessage({
            type: "API_GET_OPTIMIZED_RESUME",
            resumeId: jobMatch.optimized_resume_id,
          }),
          chrome.runtime.sendMessage({
            type: "API_DOWNLOAD_RESUME_PDF",
            resumeId: jobMatch.optimized_resume_id,
          }),
        ]);
      }

      const { boardType, result: fillResult } = await dispatchFill({
        config,
        resumeComponents,
        resumePdfBase64,
        onStep: (step) => {
          setSteps((prev) => {
            const existing = prev.findIndex((s) => s.name === step.name);
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = step;
              return updated;
            }
            return [...prev, step];
          });
        },
        onSignInRequired: () =>
          new Promise<void>((resolve) => {
            setState("sign-in-required");
            setSignInResolver(() => resolve);
          }),
      });

      setFillBoardType(boardType);
      setResult(fillResult);
      setState("done");
    } catch (err) {
      setState("error");
      setResult({
        fieldsTotal: 0,
        fieldsFilled: 0,
        errors: [err instanceof Error ? err.message : "Unknown error"],
        steps: [],
      });
    }
  }, [jobMatch]);

  const handleContinueAfterSignIn = useCallback(() => {
    setState("filling");
    signInResolver?.();
    setSignInResolver(null);
  }, [signInResolver]);

  const handleMarkApplied = useCallback(async () => {
    if (!jobMatch || !result) return;

    const payload: ApplicationLogPayload = {
      job_id: jobMatch.id,
      board_type: fillBoardType ?? detectedBoard,
      method: "extension_auto_fill",
      status: result.errors.length > 0 ? "partial" : "filled",
      fields_filled: result.fieldsFilled,
      fields_total: result.fieldsTotal,
      optimized_resume_id: jobMatch.optimized_resume_id ?? undefined,
    };

    await chrome.runtime.sendMessage({ type: "API_LOG_APPLICATION", payload });
    await chrome.runtime.sendMessage({
      type: "API_UPDATE_JOB_STATUS",
      jobId: jobMatch.id,
      status: "applied",
    });
  }, [jobMatch, result, fillBoardType, detectedBoard]);

  // ── Minimized state ─────────────────────────────────────────────────
  if (minimized) {
    return (
      <div className="jx-overlay minimized" onClick={() => setMinimized(false)}>
        <div className="jx-mini-icon">JX</div>
      </div>
    );
  }

  return (
    <div className="jx-overlay">
      {/* Header */}
      <div className="jx-header">
        <div className="jx-header-title">JobXplore</div>
        <div className="jx-header-actions">
          <button onClick={() => setMinimized(true)} title="Minimize">_</button>
          <button onClick={unmountOverlay} title="Close">x</button>
        </div>
      </div>

      <div className="jx-body">
        {/* Job Info */}
        {jobMatch ? (
          <div className="jx-job-info">
            <div className="jx-job-title">{jobMatch.job_title}</div>
            <div className="jx-company">{jobMatch.company_title}</div>
            <div className="jx-badges">
              {jobMatch.alignment_score != null && (
                <span className="jx-badge jx-badge-score">
                  {jobMatch.alignment_grade ?? `${Math.round(jobMatch.alignment_score)}%`}
                </span>
              )}
              {jobMatch.has_optimized_resume && (
                <span className="jx-badge jx-badge-resume">Resume Ready</span>
              )}
              {jobMatch.application_status && (
                <span className="jx-badge jx-badge-status">{jobMatch.application_status}</span>
              )}
            </div>
          </div>
        ) : (
          <div className="jx-message">
            Unknown job - detected {detectedBoard} form
          </div>
        )}

        {/* Auto-Fill Button */}
        {state === "idle" && (
          <button className="jx-btn jx-btn-primary" onClick={handleAutoFill}>
            Auto-Fill Application
          </button>
        )}

        {/* Sign-In Required */}
        {state === "sign-in-required" && (
          <>
            <div className="jx-message">
              Please sign in to the ATS, then click Continue.
            </div>
            <button className="jx-btn jx-btn-primary" onClick={handleContinueAfterSignIn}>
              Continue After Sign-In
            </button>
          </>
        )}

        {/* Progress Steps */}
        {(state === "filling" || state === "done" || state === "error") && steps.length > 0 && (
          <ul className="jx-steps">
            {steps.map((step) => (
              <li key={step.name} className={`jx-step ${step.status}`}>
                <StepIcon status={step.status} />
                <span>{step.name}</span>
                {step.fieldsFilled != null && step.fieldsTotal != null && step.fieldsTotal > 0 && (
                  <span style={{ marginLeft: "auto", fontSize: 11 }}>
                    {step.fieldsFilled}/{step.fieldsTotal}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Filling indicator */}
        {state === "filling" && (
          <div className="jx-message">Filling in progress...</div>
        )}

        {/* Result Summary */}
        {state === "done" && result && (
          <div className="jx-summary">
            <strong>{result.fieldsFilled}</strong> of <strong>{result.fieldsTotal}</strong> fields filled.
            {result.errors.length > 0 && (
              <div style={{ color: "#dc2626", marginTop: 4 }}>
                {result.errors.length} issue(s) - please review.
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {state === "error" && result && (
          <div className="jx-summary" style={{ color: "#dc2626" }}>
            Fill failed: {result.errors.join(", ")}
          </div>
        )}

        {/* Post-fill actions */}
        {state === "done" && (
          <>
            <button className="jx-btn jx-btn-success" onClick={handleMarkApplied}>
              Mark as Applied
            </button>
            <button className="jx-btn jx-btn-secondary" onClick={() => setState("idle")}>
              Re-fill
            </button>
          </>
        )}
      </div>
    </div>
  );
}
