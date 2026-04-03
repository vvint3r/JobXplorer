"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface PipelineRun {
  id: string;
  pipeline_type: string;
  status: string;
  current_stage: string | null;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

function statusVariant(status: string): "success" | "warning" | "destructive" | "secondary" {
  switch (status) {
    case "completed": return "success";
    case "running": return "warning";
    case "failed": return "destructive";
    default: return "secondary";
  }
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return "-";
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const seconds = Math.round((e - s) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

const STAGE_LABELS: Record<string, string> = {
  job_search: "Searching LinkedIn",
  job_details: "Fetching job details",
  merge: "Deduplicating jobs",
  insights: "Analyzing JDs",
  alignment: "Scoring alignment",
  optimize: "Optimizing resumes",
};

export default function PipelinesPage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [realtimeActive, setRealtimeActive] = useState(false);
  const supabase = createClient();
  const runsRef = useRef(runs);
  runsRef.current = runs;

  useEffect(() => {
    loadRuns();

    // Subscribe to Supabase Realtime for pipeline_runs changes
    const channel = supabase
      .channel("pipeline-runs")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "pipeline_runs" },
        (payload) => {
          setRealtimeActive(true);
          const updated = payload.new as PipelineRun;
          if (!updated?.id) return;

          setRuns((prev) => {
            const idx = prev.findIndex((r) => r.id === updated.id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = { ...next[idx], ...updated };
              return next;
            }
            // New run — prepend
            if (payload.eventType === "INSERT") {
              return [updated, ...prev];
            }
            return prev;
          });
        }
      )
      .subscribe();

    // Fallback: poll every 30s if Realtime isn't working, or every 5s
    // before first Realtime event comes in. After first event, reduce frequency.
    const interval = setInterval(() => {
      const hasActive = runsRef.current.some(
        (r) => r.status === "running" || r.status === "pending"
      );
      if (hasActive) loadRuns();
    }, realtimeActive ? 30000 : 5000);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(interval);
    };
  }, [realtimeActive]);

  async function getApi() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    return new ApiClient(session.access_token);
  }

  async function loadRuns() {
    const api = await getApi();
    if (!api) return;
    const result = await api.listPipelineRuns().catch(() => []);
    setRuns(result as PipelineRun[]);
    setLoading(false);
  }

  async function handleCancel(runId: string) {
    const api = await getApi();
    if (!api) return;
    await api.cancelPipelineRun(runId);
    loadRuns();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Pipeline Runs</h1>
        {realtimeActive && (
          <Badge variant="success" className="text-xs">Live</Badge>
        )}
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading pipeline runs...</p>
      ) : runs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No pipeline runs yet. Go to Searches and trigger a pipeline.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => (
            <Card key={run.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                    <span className="font-medium capitalize">{run.pipeline_type} Pipeline</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    <span>{formatDuration(run.started_at, run.completed_at)}</span>
                    <span>{new Date(run.created_at).toLocaleString()}</span>
                    {(run.status === "running" || run.status === "pending") && (
                      <Button variant="destructive" size="sm" onClick={() => handleCancel(run.id)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                {(run.status === "running" || run.status === "pending") && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>{run.current_stage ? STAGE_LABELS[run.current_stage] || run.current_stage : "Waiting..."}</span>
                      <span>{Math.round(run.progress * 100)}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-secondary">
                      <div
                        className="h-2 rounded-full bg-primary transition-all duration-500"
                        style={{ width: `${Math.max(run.progress * 100, 2)}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Completed progress bar (static) */}
                {run.status === "completed" && (
                  <div className="h-2 w-full rounded-full bg-secondary">
                    <div className="h-2 w-full rounded-full bg-green-500" />
                  </div>
                )}

                {/* Error message */}
                {run.error_message && (
                  <div className="mt-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {run.error_message}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
