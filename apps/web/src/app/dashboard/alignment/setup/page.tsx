"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface SupplementaryTerm {
  term: string;
  proficiency: string;
}

interface IndexInfo {
  id: string;
  master_job_title: string;
  inputs: { inputs?: unknown[]; metadata?: Record<string, unknown> };
  metadata: {
    version?: number;
    total_inputs?: number;
    created_at?: string;
    updated_at?: string;
  } | null;
  created_at: string;
  updated_at: string;
}

export default function AlignmentSetupPage() {
  const [terms, setTerms] = useState<SupplementaryTerm[]>([]);
  const [indexInfo, setIndexInfo] = useState<IndexInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [newTerm, setNewTerm] = useState("");
  const [newProficiency, setNewProficiency] = useState("intermediate");
  const [generateTitle, setGenerateTitle] = useState("");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const supabase = createClient();

  useEffect(() => {
    loadData();
  }, []);

  async function getApi() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return null;
    return new ApiClient(session.access_token);
  }

  async function loadData() {
    const api = await getApi();
    if (!api) return;

    const [termsResult, indexResult] = await Promise.all([
      api.getSupplementaryTerms().catch(() => ({ terms: [] })),
      api.getInputIndex().catch(() => null),
    ]);

    setTerms(termsResult.terms);
    setIndexInfo(indexResult as IndexInfo | null);
    if (indexResult) {
      setGenerateTitle((indexResult as IndexInfo).master_job_title || "");
    }
    setLoading(false);
  }

  async function handleSaveTerms() {
    const api = await getApi();
    if (!api) return;
    setSaving(true);
    setMessage(null);
    try {
      await api.updateSupplementaryTerms(terms);
      setMessage({ type: "success", text: "Supplementary terms saved." });
    } catch (e: unknown) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Failed to save" });
    }
    setSaving(false);
  }

  function handleAddTerm() {
    const trimmed = newTerm.trim();
    if (!trimmed) return;
    if (terms.some((t) => t.term.toLowerCase() === trimmed.toLowerCase())) {
      setMessage({ type: "error", text: `"${trimmed}" already exists.` });
      return;
    }
    setTerms([...terms, { term: trimmed, proficiency: newProficiency }]);
    setNewTerm("");
    setMessage(null);
  }

  function handleRemoveTerm(index: number) {
    setTerms(terms.filter((_, i) => i !== index));
  }

  function handleProficiencyChange(index: number, proficiency: string) {
    setTerms(terms.map((t, i) => (i === index ? { ...t, proficiency } : t)));
  }

  async function handleGenerateIndex() {
    const api = await getApi();
    if (!api || !generateTitle.trim()) return;
    setGenerating(true);
    setMessage(null);
    try {
      await api.generateInputIndex(generateTitle.trim());
      setMessage({
        type: "success",
        text: `Index generation started for "${generateTitle.trim()}". This takes 1-2 minutes.`,
      });
      // Poll for completion
      setTimeout(() => loadData(), 30000);
      setTimeout(() => loadData(), 60000);
      setTimeout(() => loadData(), 120000);
    } catch (e: unknown) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Failed to start" });
    }
    setGenerating(false);
  }

  const indexInputsCount =
    indexInfo?.metadata?.total_inputs ??
    (Array.isArray(indexInfo?.inputs) ? indexInfo.inputs.length : 0);

  if (loading) {
    return <p className="text-muted-foreground">Loading alignment setup...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Alignment Setup</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your input index and supplementary terms for alignment scoring.
          </p>
        </div>
        <Link href="/dashboard/alignment">
          <Button variant="outline" size="sm">View Scores</Button>
        </Link>
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

      {/* Input Index Section */}
      <Card>
        <CardHeader>
          <CardTitle>Input Index</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {indexInfo ? (
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <Badge variant="success">Active</Badge>
                <span className="text-sm font-medium">{indexInfo.master_job_title}</span>
              </div>
              <div className="text-sm text-muted-foreground space-y-1">
                <p>{indexInputsCount} indexed terms</p>
                <p>
                  Version {indexInfo.metadata?.version || 1}
                  {" --- "}
                  Updated {new Date(indexInfo.updated_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No input index found. Generate one to enable alignment scoring.
            </p>
          )}

          <div className="flex gap-2 items-end pt-2">
            <div className="flex-1">
              <label className="text-sm font-medium mb-1 block">
                {indexInfo ? "Regenerate for job title" : "Generate for job title"}
              </label>
              <Input
                placeholder="e.g., Marketing Analytics Manager"
                value={generateTitle}
                onChange={(e) => setGenerateTitle(e.target.value)}
              />
            </div>
            <Button
              onClick={handleGenerateIndex}
              disabled={generating || !generateTitle.trim()}
            >
              {generating ? "Starting..." : indexInfo ? "Regenerate" : "Generate"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Uses your OpenAI API key to generate a comprehensive skill/tool index for the target role.
            Takes 1-2 minutes.
          </p>
        </CardContent>
      </Card>

      {/* Supplementary Terms Section */}
      <Card>
        <CardHeader>
          <CardTitle>Supplementary Terms</CardTitle>
          <p className="text-sm text-muted-foreground">
            Skills, tools, or concepts you know but aren&apos;t on your resume.
            These count as partial matches during alignment scoring.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Add term form */}
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Input
                placeholder="Enter a skill or tool..."
                value={newTerm}
                onChange={(e) => setNewTerm(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAddTerm();
                }}
              />
            </div>
            <select
              className="rounded-md border bg-background px-3 py-2 text-sm h-10"
              value={newProficiency}
              onChange={(e) => setNewProficiency(e.target.value)}
            >
              <option value="entry">Entry</option>
              <option value="intermediate">Intermediate</option>
              <option value="expert">Expert</option>
            </select>
            <Button onClick={handleAddTerm} disabled={!newTerm.trim()}>
              Add
            </Button>
          </div>

          {/* Terms list */}
          {terms.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No supplementary terms added yet. Add skills you know but aren&apos;t listed on your resume.
            </p>
          ) : (
            <div className="space-y-2">
              {terms.map((term, i) => (
                <div
                  key={`${term.term}-${i}`}
                  className="flex items-center gap-2 rounded-md border px-3 py-2"
                >
                  <span className="flex-1 text-sm font-medium">{term.term}</span>
                  <select
                    className="rounded border bg-background px-2 py-1 text-xs"
                    value={term.proficiency}
                    onChange={(e) => handleProficiencyChange(i, e.target.value)}
                  >
                    <option value="entry">Entry</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="expert">Expert</option>
                  </select>
                  <Badge
                    variant={
                      term.proficiency === "expert"
                        ? "success"
                        : term.proficiency === "intermediate"
                        ? "warning"
                        : "secondary"
                    }
                    className="text-xs"
                  >
                    {term.proficiency}
                  </Badge>
                  <button
                    onClick={() => handleRemoveTerm(i)}
                    className="text-muted-foreground hover:text-destructive transition-colors p-1"
                    title="Remove"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path d="M18 6 6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Save button */}
          <div className="flex items-center justify-between pt-2">
            <p className="text-xs text-muted-foreground">
              {terms.length} term{terms.length !== 1 ? "s" : ""}
            </p>
            <Button onClick={handleSaveTerms} disabled={saving}>
              {saving ? "Saving..." : "Save Terms"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
