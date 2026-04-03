"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface GapItem {
  input: string;
  weight: number;
  type: string;
}

interface MatchedItem {
  input: string;
  weight: number;
  source: string;
  proficiency?: string;
}

interface AlignmentScore {
  id: string;
  job_id: string;
  resume_id: string;
  alignment_score: number;
  alignment_grade: string;
  matched_inputs: { matched: MatchedItem[]; supplementary: MatchedItem[] } | null;
  gaps: GapItem[] | null;
  scored_at: string;
}

interface JobInfo {
  id: string;
  job_title: string;
  company_title: string | null;
  location: string | null;
  job_url: string;
}

function gradeVariant(grade: string): "success" | "warning" | "destructive" | "secondary" {
  if (grade.startsWith("A")) return "success";
  if (grade.startsWith("B")) return "warning";
  if (grade.startsWith("C")) return "destructive";
  return "secondary";
}

function scoreBarColor(score: number): string {
  if (score >= 0.75) return "bg-green-500";
  if (score >= 0.55) return "bg-yellow-500";
  if (score >= 0.35) return "bg-orange-500";
  return "bg-red-500";
}

export default function AlignmentPage() {
  const [scores, setScores] = useState<AlignmentScore[]>([]);
  const [jobs, setJobs] = useState<Record<string, JobInfo>>({});
  const [searchConfigs, setSearchConfigs] = useState<any[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [expandedScore, setExpandedScore] = useState<string | null>(null);
  const supabase = createClient();

  useEffect(() => {
    loadConfigs();
  }, []);

  useEffect(() => {
    loadScores();
  }, [selectedConfig]);

  async function getApi() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    return new ApiClient(session.access_token);
  }

  async function loadConfigs() {
    const api = await getApi();
    if (!api) return;
    const configs = await api.listSearchConfigs().catch(() => []);
    setSearchConfigs(configs as any[]);
  }

  async function loadScores() {
    const api = await getApi();
    if (!api) return;
    setLoading(true);

    const params: { search_config_id?: string } = {};
    if (selectedConfig) params.search_config_id = selectedConfig;

    const result = await api.listAlignmentScores(params).catch(() => []);
    const scoreList = result as AlignmentScore[];
    setScores(scoreList);

    // Batch-load job details (parallel, up to 50)
    const uniqueJobIds = [...new Set(scoreList.map((s) => s.job_id))].slice(0, 50);
    const jobResults = await Promise.all(
      uniqueJobIds.map((id) => api.getJob(id).catch(() => null))
    );

    const jobMap: Record<string, JobInfo> = {};
    for (const job of jobResults) {
      if (job) jobMap[(job as JobInfo).id] = job as JobInfo;
    }
    setJobs(jobMap);
    setLoading(false);
  }

  // Summary stats
  const avgScore = scores.length > 0
    ? scores.reduce((sum, s) => sum + s.alignment_score, 0) / scores.length
    : 0;
  const gradeDistribution = scores.reduce<Record<string, number>>((acc, s) => {
    const letter = s.alignment_grade[0]; // A, B, C, D
    acc[letter] = (acc[letter] || 0) + 1;
    return acc;
  }, {});

  if (loading) {
    return <p className="text-muted-foreground">Loading alignment scores...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Alignment Scores</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {scores.length} jobs scored
          </p>
        </div>
        <Link href="/dashboard/alignment/setup">
          <Button variant="outline" size="sm">Setup</Button>
        </Link>
      </div>

      {/* Filter */}
      <div className="flex gap-4">
        <select
          className="rounded-md border bg-background px-3 py-2 text-sm"
          value={selectedConfig}
          onChange={(e) => setSelectedConfig(e.target.value)}
        >
          <option value="">All searches</option>
          {searchConfigs.map((c: any) => (
            <option key={c.id} value={c.id}>{c.job_title}</option>
          ))}
        </select>
      </div>

      {scores.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No alignment scores yet. Run the alignment pipeline to score your jobs.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-2xl font-bold">{(avgScore * 100).toFixed(1)}%</p>
                <p className="text-sm text-muted-foreground">Average Score</p>
              </CardContent>
            </Card>
            {["A", "B", "C", "D"].map((letter) => (
              <Card key={letter}>
                <CardContent className="pt-6">
                  <p className="text-2xl font-bold">{gradeDistribution[letter] || 0}</p>
                  <p className="text-sm text-muted-foreground">{letter} Grade Jobs</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Score list */}
          <div className="space-y-2">
            {scores.map((score) => {
              const job = jobs[score.job_id];
              const isExpanded = expandedScore === score.id;
              const gaps = Array.isArray(score.gaps) ? score.gaps : [];
              const matched = score.matched_inputs?.matched || [];
              const supplementary = score.matched_inputs?.supplementary || [];

              return (
                <Card
                  key={score.id}
                  className={`cursor-pointer transition-shadow ${isExpanded ? "ring-2 ring-primary" : "hover:shadow-md"}`}
                >
                  <CardContent className="py-4">
                    {/* Summary row */}
                    <div
                      className="flex items-center justify-between"
                      onClick={() => setExpandedScore(isExpanded ? null : score.id)}
                    >
                      <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex items-center gap-2">
                          <p className="font-medium truncate">{job?.job_title || "Unknown Job"}</p>
                          <Badge variant={gradeVariant(score.alignment_grade)} className="shrink-0">
                            {score.alignment_grade}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {job?.company_title || ""}{job?.location ? ` \u00B7 ${job.location}` : ""}
                        </p>
                        {/* Score bar */}
                        <div className="flex items-center gap-3">
                          <div className="h-2 flex-1 rounded-full bg-secondary max-w-xs">
                            <div
                              className={`h-2 rounded-full transition-all ${scoreBarColor(score.alignment_score)}`}
                              style={{ width: `${Math.max(score.alignment_score * 100, 2)}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium w-14 text-right">
                            {(score.alignment_score * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                      <svg
                        className={`h-4 w-4 text-muted-foreground transition-transform ml-4 shrink-0 ${isExpanded ? "rotate-180" : ""}`}
                        fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                      >
                        <path d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="mt-4 border-t pt-4 space-y-4">
                        {/* Matched skills */}
                        {matched.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium mb-2">
                              Matched Skills ({matched.length})
                            </h4>
                            <div className="flex flex-wrap gap-1">
                              {matched.map((m, i) => (
                                <Badge key={i} variant="success" className="text-xs">
                                  {m.input}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Supplementary matches */}
                        {supplementary.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium mb-2">
                              Supplementary Matches ({supplementary.length})
                            </h4>
                            <div className="flex flex-wrap gap-1">
                              {supplementary.map((s, i) => (
                                <Badge key={i} variant="secondary" className="text-xs">
                                  {s.input} ({s.proficiency || "intermediate"})
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Gaps */}
                        {gaps.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium mb-2">
                              Gaps ({gaps.length})
                            </h4>
                            <div className="flex flex-wrap gap-1">
                              {gaps.map((g, i) => (
                                <Badge key={i} variant="destructive" className="text-xs">
                                  {g.input}
                                  {g.weight >= 0.7 && " *"}
                                </Badge>
                              ))}
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                              * = high-weight requirement
                            </p>
                          </div>
                        )}

                        {/* Actions */}
                        {job && (
                          <div className="flex gap-3">
                            <a href={job.job_url} target="_blank" rel="noopener noreferrer"
                              className="text-sm text-primary hover:underline">
                              View on LinkedIn
                            </a>
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
