/**
 * Unit tests for job-board-detector.ts
 * Pure URL matching — no DOM, no chrome APIs needed.
 */

import { describe, it, expect } from "vitest";
import {
  detectJobBoard,
  getJobBoardInfo,
  isKnownJobBoard,
} from "@shared/job-board-detector";

// ── detectJobBoard ────────────────────────────────────────────────────────────

describe("detectJobBoard", () => {
  it("detects greenhouse URLs", () => {
    expect(detectJobBoard("https://boards.greenhouse.io/acme/jobs/123")).toBe("greenhouse");
  });

  it("detects greenhouse job-boards subdomain", () => {
    expect(detectJobBoard("https://job-boards.greenhouse.io/company/jobs/456")).toBe("greenhouse");
  });

  it("detects workday URLs", () => {
    expect(detectJobBoard("https://acme.myworkdayjobs.com/en-US/External")).toBe("workday");
  });

  it("detects workday.com URLs", () => {
    expect(detectJobBoard("https://wd3.workday.com/acme/d/inst/relative/0")).toBe("workday");
  });

  it("detects lever URLs", () => {
    expect(detectJobBoard("https://jobs.lever.co/acme/abc-123")).toBe("lever");
  });

  it("detects smartrecruiters URLs", () => {
    expect(detectJobBoard("https://jobs.smartrecruiters.com/Acme/123")).toBe("smartrecruiters");
  });

  it("detects linkedin easy apply URLs", () => {
    expect(detectJobBoard("https://www.linkedin.com/jobs/view/12345")).toBe("linkedin");
  });

  it("detects indeed URLs", () => {
    expect(detectJobBoard("https://www.indeed.com/viewjob?jk=abc123")).toBe("indeed");
  });

  it("detects glassdoor URLs", () => {
    expect(detectJobBoard("https://www.glassdoor.com/job-listing/title-JV_KO0,10.htm")).toBe(
      "glassdoor"
    );
  });

  it("returns generic for unknown URLs", () => {
    expect(detectJobBoard("https://careers.randomcompany.com/apply")).toBe("generic");
  });

  it("returns generic for empty string", () => {
    expect(detectJobBoard("")).toBe("generic");
  });

  it("is case-insensitive", () => {
    expect(detectJobBoard("https://BOARDS.GREENHOUSE.IO/ACME")).toBe("greenhouse");
  });

  it("handles URLs with query params", () => {
    expect(detectJobBoard("https://acme.myworkdayjobs.com/jobs?page=2&sort=date")).toBe("workday");
  });
});

// ── getJobBoardInfo ───────────────────────────────────────────────────────────

describe("getJobBoardInfo", () => {
  it("returns type and features for greenhouse", () => {
    const info = getJobBoardInfo("https://boards.greenhouse.io/acme/jobs/1");
    expect(info.type).toBe("greenhouse");
    expect(info.features.auto_fill_supported).toBe(true);
    expect(info.features.file_upload_supported).toBe(true);
  });

  it("returns generic features for unknown board", () => {
    const info = getJobBoardInfo("https://unknown.company.com/apply");
    expect(info.type).toBe("generic");
    expect(info.features).toBeDefined();
    expect(info.features.auto_fill_supported).toBe(true);
  });

  it("workday requires_manual_review is true", () => {
    const info = getJobBoardInfo("https://acme.myworkdayjobs.com/jobs/1");
    expect(info.features.requires_manual_review).toBe(true);
  });

  it("greenhouse requires_manual_review is false", () => {
    const info = getJobBoardInfo("https://boards.greenhouse.io/acme/jobs/1");
    expect(info.features.requires_manual_review).toBe(false);
  });
});

// ── isKnownJobBoard ───────────────────────────────────────────────────────────

describe("isKnownJobBoard", () => {
  it("returns true for greenhouse", () => {
    expect(isKnownJobBoard("https://boards.greenhouse.io/acme/jobs/1")).toBe(true);
  });

  it("returns true for lever", () => {
    expect(isKnownJobBoard("https://jobs.lever.co/acme/123")).toBe(true);
  });

  it("returns false for unknown URLs", () => {
    expect(isKnownJobBoard("https://mycompany.com/careers/apply")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isKnownJobBoard("")).toBe(false);
  });
});
