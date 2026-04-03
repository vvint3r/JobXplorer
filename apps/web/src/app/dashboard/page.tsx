"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function DashboardPage() {
  const [stats, setStats] = useState({ jobs: 0, searches: 0, pipelines: 0 });
  const [recentRuns, setRecentRuns] = useState<any[]>([]);
  const supabase = createClient();

  useEffect(() => {
    async function load() {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const api = new ApiClient(session.access_token);

      const [jobCount, searches, runs] = await Promise.all([
        api.getJobCount().catch(() => ({ count: 0 })),
        api.listSearchConfigs().catch(() => []),
        api.listPipelineRuns().catch(() => []),
      ]);

      setStats({
        jobs: (jobCount as any).count || 0,
        searches: (searches as any[]).length,
        pipelines: (runs as any[]).length,
      });
      setRecentRuns((runs as any[]).slice(0, 5));
    }

    load();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Jobs</CardDescription>
            <CardTitle className="text-4xl">{stats.jobs}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Search Configs</CardDescription>
            <CardTitle className="text-4xl">{stats.searches}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Pipeline Runs</CardDescription>
            <CardTitle className="text-4xl">{stats.pipelines}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Pipeline Runs</CardTitle>
        </CardHeader>
        <CardContent>
          {recentRuns.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No pipeline runs yet. Create a search config and start your first run.
            </p>
          ) : (
            <div className="space-y-3">
              {recentRuns.map((run: any) => (
                <div key={run.id} className="flex items-center justify-between border-b pb-3 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{run.pipeline_type} pipeline</p>
                    <p className="text-xs text-muted-foreground">
                      {run.current_stage || "pending"} &middot; {Math.round(run.progress * 100)}%
                    </p>
                  </div>
                  <Badge
                    variant={
                      run.status === "completed" ? "success" :
                      run.status === "failed" ? "destructive" :
                      run.status === "running" ? "warning" : "secondary"
                    }
                  >
                    {run.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
