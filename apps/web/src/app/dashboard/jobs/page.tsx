"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface JobSummary {
  id: string;
  job_title: string;
  company_title: string | null;
  job_url: string;
  application_url: string | null;
  salary_range: string | null;
  location: string | null;
  remote_status: string | null;
  days_since_posted: number | null;
  date_extracted: string | null;
  application_status: string | null;
  created_at: string;
}

interface JobDetail extends JobSummary {
  description: string | null;
  alignment_score: number | null;
  alignment_grade: string | null;
}

function gradeVariant(grade: string): "success" | "warning" | "destructive" {
  if (grade.startsWith("A")) return "success";
  if (grade.startsWith("B")) return "warning";
  return "destructive";
}

function statusVariant(status: string): "success" | "warning" | "destructive" | "secondary" {
  switch (status) {
    case "applied": return "success";
    case "interested": return "warning";
    case "rejected":
    case "failed": return "destructive";
    default: return "secondary";
  }
}

const APP_STATUSES = ["interested", "applied", "skipped", "rejected"];

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [searchConfigs, setSearchConfigs] = useState<any[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [sortBy, setSortBy] = useState("date_extracted");
  const [sortOrder, setSortOrder] = useState("desc");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [jobDetails, setJobDetails] = useState<Record<string, JobDetail>>({});
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
  const [optimizing, setOptimizing] = useState<string | null>(null);
  const [bulkOptimizing, setBulkOptimizing] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const supabase = createClient();

  useEffect(() => {
    loadJobs();
  }, [selectedConfig, companyFilter, sortBy, sortOrder, page]);

  useEffect(() => {
    loadConfigs();
  }, []);

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

  async function loadJobs() {
    const api = await getApi();
    if (!api) return;

    const params: Record<string, string> = {
      page: page.toString(),
      per_page: "50",
      sort_by: sortBy,
      sort_order: sortOrder,
    };
    if (selectedConfig) params.search_config_id = selectedConfig;
    if (companyFilter) params.company = companyFilter;

    const [result, countResult] = await Promise.all([
      api.listJobs(params).catch(() => []),
      api.getJobCount(selectedConfig || undefined).catch(() => ({ count: 0 })),
    ]);
    setJobs(result as JobSummary[]);
    setTotalCount((countResult as { count: number }).count);
    setLoading(false);
  }

  async function handleExpand(jobId: string) {
    if (expandedJob === jobId) {
      setExpandedJob(null);
      return;
    }
    setExpandedJob(jobId);

    if (!jobDetails[jobId]) {
      const api = await getApi();
      if (!api) return;
      const detail = await api.getJob(jobId).catch(() => null);
      if (detail) {
        setJobDetails((prev) => ({ ...prev, [jobId]: detail as JobDetail }));
      }
    }
  }

  async function handleStatusChange(jobId: string, status: string) {
    const api = await getApi();
    if (!api) return;
    await api.updateJobStatus(jobId, status);
    setJobs(jobs.map((j) => j.id === jobId ? { ...j, application_status: status } : j));
    setMessage(null);
  }

  async function handleOptimize(jobId: string) {
    const api = await getApi();
    if (!api) return;
    setOptimizing(jobId);
    setMessage(null);
    try {
      await api.optimizeSingle(jobId);
      setMessage({ type: "success", text: "Resume optimized. View in Resumes > Optimized." });
    } catch (e: unknown) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Optimization failed" });
    }
    setOptimizing(null);
  }

  async function handleBulkOptimize() {
    if (!selectedConfig) {
      setMessage({ type: "error", text: "Select a search config to run bulk optimization." });
      return;
    }
    const api = await getApi();
    if (!api) return;
    setBulkOptimizing(true);
    setMessage(null);
    try {
      await api.bulkOptimize(selectedConfig);
      setMessage({ type: "success", text: "Bulk optimization started. Check Pipelines for progress." });
    } catch (e: unknown) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Bulk optimize failed" });
    }
    setBulkOptimizing(false);
  }

  async function handleBulkStatus(status: string) {
    if (selectedJobs.size === 0) return;
    const api = await getApi();
    if (!api) return;
    await api.bulkUpdateJobStatus(Array.from(selectedJobs), status);
    setJobs(jobs.map((j) => selectedJobs.has(j.id) ? { ...j, application_status: status } : j));
    setSelectedJobs(new Set());
    setMessage({ type: "success", text: `Updated ${selectedJobs.size} jobs to "${status}".` });
  }

  function toggleSelect(jobId: string) {
    setSelectedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectedJobs.size === jobs.length) {
      setSelectedJobs(new Set());
    } else {
      setSelectedJobs(new Set(jobs.map((j) => j.id)));
    }
  }

  const totalPages = Math.ceil(totalCount / 50);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Jobs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {totalCount} jobs collected
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleBulkOptimize}
            disabled={bulkOptimizing || !selectedConfig}
            title={!selectedConfig ? "Select a search to run bulk optimization" : ""}
          >
            {bulkOptimizing ? "Starting..." : "Bulk Optimize"}
          </Button>
        </div>
      </div>

      {/* Status message */}
      {message && (
        <div
          className={`rounded-md p-3 text-sm ${
            message.type === "success"
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-destructive/10 text-destructive"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Filters and sort */}
      <div className="flex flex-wrap gap-4 items-center">
        <select
          className="rounded-md border bg-background px-3 py-2 text-sm"
          value={selectedConfig}
          onChange={(e) => { setSelectedConfig(e.target.value); setPage(1); }}
        >
          <option value="">All searches</option>
          {searchConfigs.map((c: any) => (
            <option key={c.id} value={c.id}>{c.job_title}</option>
          ))}
        </select>

        <Input
          placeholder="Filter by company..."
          value={companyFilter}
          onChange={(e) => { setCompanyFilter(e.target.value); setPage(1); }}
          className="max-w-xs"
        />

        <select
          className="rounded-md border bg-background px-3 py-2 text-sm"
          value={`${sortBy}:${sortOrder}`}
          onChange={(e) => {
            const [field, order] = e.target.value.split(":");
            setSortBy(field);
            setSortOrder(order);
            setPage(1);
          }}
        >
          <option value="date_extracted:desc">Newest first</option>
          <option value="date_extracted:asc">Oldest first</option>
          <option value="job_title:asc">Title A-Z</option>
          <option value="job_title:desc">Title Z-A</option>
          <option value="company_title:asc">Company A-Z</option>
          <option value="company_title:desc">Company Z-A</option>
        </select>
      </div>

      {/* Bulk actions bar */}
      {selectedJobs.size > 0 && (
        <div className="flex items-center gap-3 rounded-md border bg-accent/50 p-3">
          <span className="text-sm font-medium">{selectedJobs.size} selected</span>
          <span className="text-muted-foreground">|</span>
          {APP_STATUSES.map((s) => (
            <Button
              key={s}
              variant="outline"
              size="sm"
              onClick={() => handleBulkStatus(s)}
            >
              Mark {s}
            </Button>
          ))}
          <Button variant="ghost" size="sm" onClick={() => setSelectedJobs(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {/* Jobs list */}
      {loading ? (
        <p className="text-muted-foreground">Loading jobs...</p>
      ) : jobs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No jobs found. Run a search pipeline to start collecting jobs.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {/* Select all */}
          <div className="flex items-center gap-2 px-2">
            <input
              type="checkbox"
              checked={selectedJobs.size === jobs.length && jobs.length > 0}
              onChange={toggleSelectAll}
              className="h-4 w-4 rounded border-muted-foreground"
            />
            <span className="text-xs text-muted-foreground">Select all on page</span>
          </div>

          {jobs.map((job) => {
            const detail = jobDetails[job.id];
            const isExpanded = expandedJob === job.id;
            const isSelected = selectedJobs.has(job.id);

            return (
              <Card
                key={job.id}
                className={`transition-shadow ${isExpanded ? "ring-2 ring-primary" : "hover:shadow-md"} ${isSelected ? "bg-accent/30" : ""}`}
              >
                <CardContent className="py-4">
                  {/* Summary row */}
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(job.id)}
                      className="h-4 w-4 rounded border-muted-foreground shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    />
                    <div
                      className="flex items-center justify-between flex-1 cursor-pointer"
                      onClick={() => handleExpand(job.id)}
                    >
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="font-medium truncate">{job.job_title}</p>
                          {job.remote_status && (
                            <Badge variant="outline" className="text-xs shrink-0">
                              {job.remote_status}
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                          {job.company_title && <span>{job.company_title}</span>}
                          {job.location && <span>{job.location}</span>}
                          {job.salary_range && <span>{job.salary_range}</span>}
                          {job.days_since_posted != null && (
                            <span>{job.days_since_posted === 0 ? "Today" : `${job.days_since_posted}d ago`}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 ml-4">
                        {job.application_status && (
                          <Badge variant={statusVariant(job.application_status)}>
                            {job.application_status}
                          </Badge>
                        )}
                        {detail?.alignment_grade && (
                          <Badge variant={gradeVariant(detail.alignment_grade)} className="px-2">
                            {detail.alignment_grade} ({(detail.alignment_score! * 100).toFixed(0)}%)
                          </Badge>
                        )}
                        <svg
                          className={`h-4 w-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                        >
                          <path d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="mt-4 border-t pt-4 space-y-4">
                      {detail ? (
                        <>
                          {detail.description ? (
                            <div>
                              <h4 className="text-sm font-medium mb-2">Job Description</h4>
                              <p className="text-sm text-muted-foreground whitespace-pre-wrap max-h-64 overflow-y-auto">
                                {detail.description}
                              </p>
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground italic">
                              No description available. Run the job details pipeline to fetch it.
                            </p>
                          )}

                          <div className="flex items-center gap-3 flex-wrap">
                            <a
                              href={job.job_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <Button variant="outline" size="sm">View on LinkedIn</Button>
                            </a>
                            {detail.application_url && detail.application_url !== "Easy Apply (LinkedIn)" && (
                              <a
                                href={detail.application_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <Button size="sm">Apply</Button>
                              </a>
                            )}
                            {detail.application_url === "Easy Apply (LinkedIn)" && (
                              <Badge variant="secondary">Easy Apply</Badge>
                            )}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOptimize(job.id)}
                              disabled={optimizing === job.id || !detail.description}
                            >
                              {optimizing === job.id ? "Optimizing..." : "Optimize Resume"}
                            </Button>
                            {detail.alignment_score != null && (
                              <span className="text-sm text-muted-foreground">
                                Alignment: {(detail.alignment_score * 100).toFixed(1)}%
                                ({detail.alignment_grade})
                              </span>
                            )}
                          </div>

                          {/* Application status selector */}
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">Status:</span>
                            {APP_STATUSES.map((s) => (
                              <Button
                                key={s}
                                variant={job.application_status === s ? "default" : "outline"}
                                size="sm"
                                className="text-xs h-7 px-2"
                                onClick={() => handleStatusChange(job.id, s)}
                              >
                                {s}
                              </Button>
                            ))}
                          </div>
                        </>
                      ) : (
                        <p className="text-sm text-muted-foreground">Loading details...</p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}

          {/* Pagination */}
          <div className="flex justify-center items-center gap-2 pt-4">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <span className="flex items-center px-3 text-sm text-muted-foreground">
              Page {page} of {totalPages || 1}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={jobs.length < 50}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
