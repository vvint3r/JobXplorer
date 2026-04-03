// ── Job Queue ───────────────────────────────────────────────────────────────
// Compact list of top unapplied jobs sorted by alignment score.
// Each row has an "Open" button to navigate to the application URL.

import React, { useState, useEffect } from "react";
import type { JobMatch } from "@shared/types";

export function JobQueue() {
  const [jobs, setJobs] = useState<JobMatch[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchJobs() {
      try {
        const result = await chrome.runtime.sendMessage({
          type: "API_GET_JOBS",
          params: { limit: 30 },
        });

        if (cancelled) return;

        if (Array.isArray(result)) {
          // Sort by alignment score descending, then filter useful ones
          const sorted = result
            .filter((j: JobMatch) => j.application_url || j.job_url)
            .sort((a: JobMatch, b: JobMatch) => {
              const scoreA = a.alignment_score ?? 0;
              const scoreB = b.alignment_score ?? 0;
              return scoreB - scoreA;
            });
          setJobs(sorted);
        }
      } catch {
        // Silently fail
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchJobs();
    return () => { cancelled = true; };
  }, []);

  const handleOpen = (job: JobMatch) => {
    const url = job.application_url ?? job.job_url;
    if (url) {
      chrome.tabs.create({ url });
    }
  };

  if (loading) {
    return <div className="jx-loading" style={{ minHeight: 200 }}>Loading jobs...</div>;
  }

  if (jobs.length === 0) {
    return (
      <div className="jx-empty-state">
        <div className="jx-empty-state-icon">[ ]</div>
        <div>No jobs found in your account.</div>
        <div style={{ marginTop: 4, fontSize: 11 }}>
          Run the job search pipeline to populate your queue.
        </div>
      </div>
    );
  }

  return (
    <ul className="jx-job-list">
      {jobs.map((job) => (
        <li key={job.id} className="jx-job-item">
          <div className="jx-job-item-info">
            <div className="jx-job-item-title" title={job.job_title}>
              {job.job_title}
            </div>
            <div className="jx-job-item-company">{job.company_title}</div>
            <div className="jx-job-item-badges">
              {job.alignment_score != null && (
                <span className="jx-badge jx-badge-score">
                  {job.alignment_grade ?? `${Math.round(job.alignment_score)}%`}
                </span>
              )}
              {job.has_optimized_resume && (
                <span className="jx-badge jx-badge-resume">Resume</span>
              )}
              {job.application_status && (
                <span className="jx-badge jx-badge-status">
                  {job.application_status}
                </span>
              )}
            </div>
          </div>
          <div className="jx-job-item-actions">
            <button className="jx-apply-btn" onClick={() => handleOpen(job)}>
              Open
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
