// ── Dashboard ───────────────────────────────────────────────────────────────
// Overview panel: greeting, stats, quick actions.

import React, { useState, useEffect } from "react";
import type { AuthStatus } from "@shared/types";

interface DashboardProps {
  auth: AuthStatus;
}

interface Stats {
  totalJobs: number;
  applied: number;
  pending: number;
  withResume: number;
}

export function Dashboard({ auth }: DashboardProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchStats() {
      try {
        // Fetch jobs to compute stats
        const jobs = await chrome.runtime.sendMessage({
          type: "API_GET_JOBS",
          params: { limit: 500 },
        });

        if (cancelled) return;

        if (Array.isArray(jobs)) {
          setStats({
            totalJobs: jobs.length,
            applied: jobs.filter((j: Record<string, unknown>) => j.application_status === "applied").length,
            pending: jobs.filter((j: Record<string, unknown>) => !j.application_status || j.application_status === "new").length,
            withResume: jobs.filter((j: Record<string, unknown>) => j.has_optimized_resume).length,
          });
        }
      } catch {
        // Stats unavailable — show defaults
        if (!cancelled) setStats({ totalJobs: 0, applied: 0, pending: 0, withResume: 0 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchStats();
    return () => { cancelled = true; };
  }, []);

  const greeting = auth.fullName
    ? `Welcome, ${auth.fullName.split(" ")[0]}`
    : `Welcome`;

  return (
    <div>
      <div className="jx-greeting">{greeting}</div>

      {loading ? (
        <div className="jx-loading" style={{ minHeight: 100 }}>
          Loading stats...
        </div>
      ) : stats ? (
        <>
          <div className="jx-stats">
            <div className="jx-stat-card">
              <div className="jx-stat-value">{stats.totalJobs}</div>
              <div className="jx-stat-label">Total Jobs</div>
            </div>
            <div className="jx-stat-card highlight">
              <div className="jx-stat-value">{stats.applied}</div>
              <div className="jx-stat-label">Applied</div>
            </div>
            <div className="jx-stat-card">
              <div className="jx-stat-value">{stats.pending}</div>
              <div className="jx-stat-label">Pending</div>
            </div>
            <div className="jx-stat-card">
              <div className="jx-stat-value">{stats.withResume}</div>
              <div className="jx-stat-label">Resume Ready</div>
            </div>
          </div>

          <div className="jx-quick-actions">
            <div className="jx-quick-actions-title">Quick Actions</div>
            <button
              className="jx-action-btn"
              onClick={() => {
                chrome.runtime.sendMessage({ type: "CACHE_INVALIDATE" });
                window.location.reload();
              }}
            >
              Refresh Data
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
