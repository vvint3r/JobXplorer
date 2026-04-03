"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function ResumesPage() {
  const [resumes, setResumes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [name, setName] = useState("");
  const [selectedResume, setSelectedResume] = useState<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);
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
    const result = await api.listResumes().catch(() => []);
    setResumes(result as any[]);
    setLoading(false);
  }

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file || !name) return;

    setUploading(true);
    const api = await getApi();
    if (!api) return;
    await api.uploadResume(name, file, resumes.length === 0);
    setName("");
    if (fileRef.current) fileRef.current.value = "";
    setUploading(false);
    loadResumes();
  }

  async function handleDelete(id: string) {
    const api = await getApi();
    if (!api) return;
    await api.deleteResume(id);
    if (selectedResume?.id === id) setSelectedResume(null);
    loadResumes();
  }

  async function handleViewDetails(id: string) {
    const api = await getApi();
    if (!api) return;
    const detail = await api.getResume(id);
    setSelectedResume(detail);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Resumes</h1>
        <Link href="/dashboard/resumes/optimized">
          <Button variant="outline" size="sm">View Optimized</Button>
        </Link>
      </div>

      {/* Upload form */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Resume</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <label className="text-sm font-medium">Resume name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Marketing Analytics Resume"
              />
            </div>
            <div>
              <label className="text-sm font-medium">PDF file</label>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:opacity-90"
              />
            </div>
            <Button onClick={handleUpload} disabled={uploading || !name}>
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Resume list */}
        <div className="space-y-3">
          {loading ? (
            <p className="text-muted-foreground">Loading resumes...</p>
          ) : resumes.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground">No resumes uploaded yet.</p>
              </CardContent>
            </Card>
          ) : (
            resumes.map((resume: any) => (
              <Card
                key={resume.id}
                className={`cursor-pointer transition-shadow hover:shadow-md ${selectedResume?.id === resume.id ? "ring-2 ring-primary" : ""}`}
                onClick={() => handleViewDetails(resume.id)}
              >
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    <svg className="h-8 w-8 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
                      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
                    </svg>
                    <div>
                      <p className="font-medium">{resume.name}</p>
                      <p className="text-xs text-muted-foreground">
                        Uploaded {new Date(resume.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      {resume.is_default && <Badge variant="success">Default</Badge>}
                      {resume.components_json ? (
                        <Badge variant="secondary">Parsed</Badge>
                      ) : (
                        <Badge variant="warning">Parsing...</Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handleDelete(resume.id); }}
                  >
                    Delete
                  </Button>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Resume preview panel */}
        {selectedResume && (
          <Card>
            <CardHeader>
              <CardTitle>{selectedResume.name}</CardTitle>
            </CardHeader>
            <CardContent>
              {selectedResume.components_json ? (
                <div className="space-y-4">
                  {/* Skills */}
                  {selectedResume.components_json.skills?.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Skills</h4>
                      <div className="flex flex-wrap gap-1">
                        {selectedResume.components_json.skills.map((skill: string, i: number) => (
                          <Badge key={i} variant="outline">{skill}</Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Summary */}
                  {selectedResume.components_json.professional_summary && (
                    <div>
                      <h4 className="text-sm font-medium mb-1">Professional Summary</h4>
                      <p className="text-sm text-muted-foreground">
                        {selectedResume.components_json.professional_summary}
                      </p>
                    </div>
                  )}

                  {/* Work Experience */}
                  {selectedResume.components_json.work_experience?.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Work Experience</h4>
                      <div className="space-y-3">
                        {selectedResume.components_json.work_experience.map((exp: any, i: number) => (
                          <div key={i} className="border-l-2 border-muted pl-3">
                            <p className="font-medium text-sm">{exp.job_title}</p>
                            <p className="text-xs text-muted-foreground">{exp.company}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Education */}
                  {selectedResume.components_json.education?.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Education</h4>
                      <div className="space-y-2">
                        {selectedResume.components_json.education.map((edu: any, i: number) => (
                          <div key={i} className="text-sm">
                            <p className="font-medium">{edu.degree} — {edu.field_of_study}</p>
                            <p className="text-xs text-muted-foreground">{edu.school_or_university}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Raw components JSON (collapsed) */}
                  <details className="mt-4">
                    <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                      View raw JSON
                    </summary>
                    <pre className="mt-2 text-xs bg-muted p-3 rounded-md overflow-auto max-h-64">
                      {JSON.stringify(selectedResume.components_json, null, 2)}
                    </pre>
                  </details>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-muted-foreground text-sm">
                    Resume is being parsed. Refresh in a few seconds.
                  </p>
                  <Button variant="outline" size="sm" className="mt-3" onClick={() => handleViewDetails(selectedResume.id)}>
                    Refresh
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
