"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface OptimizedResumeSummary {
  id: string;
  job_id: string;
  resume_id: string;
  method: string;
  job_title: string | null;
  company: string | null;
  alignment_score: number | null;
  created_at: string;
}

interface OptimizedResumeDetail {
  id: string;
  job_id: string;
  resume_id: string;
  method: string;
  optimized_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export default function OptimizedResumesPage() {
  const [resumes, setResumes] = useState<OptimizedResumeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<OptimizedResumeDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const supabase = createClient();

  useEffect(() => {
    loadResumes();
  }, []);

  async function getApi() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    return new ApiClient(session.access_token);
  }

  async function loadResumes() {
    const api = await getApi();
    if (!api) return;
    const result = await api.listOptimizedResumes().catch(() => []);
    setResumes(result as OptimizedResumeSummary[]);
    setLoading(false);
  }

  async function handleViewDetail(id: string) {
    const api = await getApi();
    if (!api) return;
    setLoadingDetail(true);
    const detail = await api.getOptimizedResume(id).catch(() => null);
    setSelected(detail as OptimizedResumeDetail | null);
    setLoadingDetail(false);
  }

  async function handleDelete(id: string) {
    const api = await getApi();
    if (!api) return;
    await api.deleteOptimizedResume(id);
    if (selected?.id === id) setSelected(null);
    loadResumes();
  }

  async function handleDownloadPdf(id: string) {
    const api = await getApi();
    if (!api) return;
    setDownloading(true);
    try {
      await api.downloadOptimizedResumePdf(id);
    } catch {
      // silently fail — user sees no file downloaded
    }
    setDownloading(false);
  }

  const optimizedJson = selected?.optimized_json as Record<string, unknown> | null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Optimized Resumes</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Resumes tailored to specific job descriptions. {resumes.length} total.
          </p>
        </div>
        <Link href="/dashboard/resumes">
          <Button variant="outline" size="sm">Base Resumes</Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading optimized resumes...</p>
      ) : resumes.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No optimized resumes yet. Run a full pipeline or optimize from the Jobs page.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* List */}
          <div className="space-y-3">
            {resumes.map((r) => (
              <Card
                key={r.id}
                className={`cursor-pointer transition-shadow hover:shadow-md ${
                  selected?.id === r.id ? "ring-2 ring-primary" : ""
                }`}
                onClick={() => handleViewDetail(r.id)}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">
                          {r.job_title || "Untitled"}
                        </span>
                        <Badge
                          variant={r.method === "llm" ? "success" : "secondary"}
                          className="text-xs"
                        >
                          {r.method === "llm" ? "AI" : "Keyword"}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {r.company || "Unknown"}{" "}
                        {r.alignment_score != null && (
                          <span>
                            {" --- "} Alignment: {Math.round(r.alignment_score)}%
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Created {new Date(r.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadPdf(r.id);
                        }}
                        disabled={downloading}
                      >
                        PDF
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(r.id);
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Detail panel */}
          {selected && optimizedJson && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">
                      {(optimizedJson._optimised_for as Record<string, unknown>)?.job_title as string || "Optimized Resume"}
                    </CardTitle>
                    <p className="text-xs text-muted-foreground">
                      {(optimizedJson._optimised_for as Record<string, unknown>)?.company as string || ""}{" "}
                      --- Method: {selected.method}
                    </p>
                  </div>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => handleDownloadPdf(selected.id)}
                    disabled={downloading}
                  >
                    {downloading ? "Downloading..." : "Download PDF"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {loadingDetail ? (
                  <p className="text-muted-foreground text-sm">Loading...</p>
                ) : (
                  <>
                    {/* JD Alignment Notes */}
                    {optimizedJson.jd_alignment_notes && (
                      <div>
                        <h4 className="text-sm font-medium mb-2">Alignment Notes</h4>
                        {typeof optimizedJson.jd_alignment_notes === "object" && (
                          <div className="space-y-2">
                            {(optimizedJson.jd_alignment_notes as Record<string, unknown>).top_jd_keywords && (
                              <div>
                                <p className="text-xs text-muted-foreground mb-1">Top JD Keywords</p>
                                <div className="flex flex-wrap gap-1">
                                  {((optimizedJson.jd_alignment_notes as Record<string, unknown>).top_jd_keywords as string[]).map((kw, i) => (
                                    <Badge key={i} variant="outline" className="text-xs">{kw}</Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                            {(optimizedJson.jd_alignment_notes as Record<string, unknown>).keywords_to_emphasise && (
                              <div>
                                <p className="text-xs text-muted-foreground mb-1">Keywords to Emphasise</p>
                                <div className="flex flex-wrap gap-1">
                                  {((optimizedJson.jd_alignment_notes as Record<string, unknown>).keywords_to_emphasise as string[]).map((kw, i) => (
                                    <Badge key={i} variant="warning" className="text-xs">{kw}</Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Professional Summary */}
                    {optimizedJson.professional_summary && (
                      <div>
                        <h4 className="text-sm font-medium mb-1">Professional Summary</h4>
                        <p className="text-sm text-muted-foreground">
                          {optimizedJson.professional_summary as string}
                        </p>
                      </div>
                    )}

                    {/* Skills */}
                    {Array.isArray(optimizedJson.skills) && optimizedJson.skills.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium mb-2">Skills (Reordered)</h4>
                        <div className="flex flex-wrap gap-1">
                          {(optimizedJson.skills as string[]).map((skill, i) => (
                            <Badge key={i} variant="outline" className="text-xs">{skill}</Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Work Experience */}
                    {Array.isArray(optimizedJson.work_experience) && optimizedJson.work_experience.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium mb-2">Work Experience</h4>
                        <div className="space-y-3">
                          {(optimizedJson.work_experience as Record<string, unknown>[]).map((exp, i) => (
                            <div key={i} className="border-l-2 border-muted pl-3">
                              <p className="font-medium text-sm">{exp.job_title as string}</p>
                              <p className="text-xs text-muted-foreground">{exp.company as string}</p>
                              {exp.role_description && (
                                <div className="mt-1 text-xs text-muted-foreground whitespace-pre-line">
                                  {(exp.role_description as string).split("\n").slice(0, 3).join("\n")}
                                  {(exp.role_description as string).split("\n").length > 3 && " ..."}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Raw JSON toggle */}
                    <details className="mt-4">
                      <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                        View raw JSON
                      </summary>
                      <pre className="mt-2 text-xs bg-muted p-3 rounded-md overflow-auto max-h-96">
                        {JSON.stringify(optimizedJson, null, 2)}
                      </pre>
                    </details>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
