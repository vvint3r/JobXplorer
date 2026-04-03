"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface SearchConfig {
  id: string;
  job_title: string;
  job_title_clean: string;
  salary_min: number | null;
  salary_max: number | null;
  job_type: string | null;
  search_type: string | null;
  remote_filter: string | null;
  work_geo_codes: string[] | null;
  is_active: boolean;
  created_at: string;
}

export default function SearchesPage() {
  const [configs, setConfigs] = useState<SearchConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState<string | null>(null);
  const supabase = createClient();

  // Form state
  const [jobTitle, setJobTitle] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [jobType, setJobType] = useState("full_time");
  const [searchType, setSearchType] = useState("exact");
  const [remoteFilter, setRemoteFilter] = useState("remote");

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
    const result = await api.listSearchConfigs().catch(() => []);
    setConfigs(result as SearchConfig[]);
    setLoading(false);
  }

  function resetForm() {
    setJobTitle("");
    setSalaryMin("");
    setSalaryMax("");
    setJobType("full_time");
    setSearchType("exact");
    setRemoteFilter("remote");
    setEditing(null);
  }

  function editConfig(config: SearchConfig) {
    setJobTitle(config.job_title);
    setSalaryMin(config.salary_min?.toString() || "");
    setSalaryMax(config.salary_max?.toString() || "");
    setJobType(config.job_type || "full_time");
    setSearchType(config.search_type || "exact");
    setRemoteFilter(config.remote_filter || "remote");
    setEditing(config.id);
    setShowForm(true);
  }

  async function handleSubmit() {
    const api = await getApi();
    if (!api || !jobTitle.trim()) return;

    const data: Record<string, unknown> = {
      job_title: jobTitle.trim(),
      salary_min: salaryMin ? parseInt(salaryMin) : null,
      salary_max: salaryMax ? parseInt(salaryMax) : null,
      job_type: jobType,
      search_type: searchType,
      remote_filter: remoteFilter || null,
    };

    if (editing) {
      await api.updateSearchConfig(editing, data);
    } else {
      await api.createSearchConfig(data);
    }

    resetForm();
    setShowForm(false);
    loadConfigs();
  }

  async function handleDelete(id: string) {
    const api = await getApi();
    if (!api) return;
    await api.deleteSearchConfig(id);
    loadConfigs();
  }

  async function handleRunPipeline(configId: string, type: string) {
    const api = await getApi();
    if (!api) return;
    setPipelineLoading(configId);
    try {
      await api.startPipeline(configId, type);
    } catch (e: any) {
      alert(e.message || "Failed to start pipeline");
    }
    setPipelineLoading(null);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Search Configs</h1>
        <Button
          onClick={() => { resetForm(); setShowForm(!showForm); }}
        >
          {showForm ? "Cancel" : "New Search"}
        </Button>
      </div>

      {/* Create / Edit form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editing ? "Edit Search Config" : "Create Search Config"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Job Title *</label>
              <Input
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="e.g., Marketing Analytics"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Min Salary ($)</label>
                <Input
                  type="number"
                  value={salaryMin}
                  onChange={(e) => setSalaryMin(e.target.value)}
                  placeholder="120000"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Max Salary ($)</label>
                <Input
                  type="number"
                  value={salaryMax}
                  onChange={(e) => setSalaryMax(e.target.value)}
                  placeholder="200000"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium">Job Type</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value)}
                >
                  <option value="full_time">Full-time</option>
                  <option value="contract">Contract</option>
                  <option value="part_time">Part-time</option>
                  <option value="internship">Internship</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Search Type</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={searchType}
                  onChange={(e) => setSearchType(e.target.value)}
                >
                  <option value="exact">Exact match</option>
                  <option value="broad">Broad</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Remote</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={remoteFilter}
                  onChange={(e) => setRemoteFilter(e.target.value)}
                >
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">On-site</option>
                  <option value="">Any</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3">
              <Button onClick={handleSubmit} disabled={!jobTitle.trim()}>
                {editing ? "Save Changes" : "Create Config"}
              </Button>
              {editing && (
                <Button variant="outline" onClick={() => { resetForm(); setShowForm(false); }}>
                  Cancel
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Configs list */}
      {loading ? (
        <p className="text-muted-foreground">Loading search configs...</p>
      ) : configs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No search configs yet. Create one to start finding jobs.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {configs.map((config) => (
            <Card key={config.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-lg">{config.job_title}</p>
                      <Badge variant={config.is_active ? "success" : "secondary"}>
                        {config.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                    <div className="flex gap-3 text-sm text-muted-foreground">
                      {config.salary_min && (
                        <span>
                          ${config.salary_min.toLocaleString()}
                          {config.salary_max ? ` – $${config.salary_max.toLocaleString()}` : "+"}
                        </span>
                      )}
                      {config.job_type && <span>{config.job_type.replace("_", "-")}</span>}
                      {config.remote_filter && <span>{config.remote_filter}</span>}
                      {config.search_type && <span>{config.search_type}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Pipeline actions */}
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        onClick={() => handleRunPipeline(config.id, "search")}
                        disabled={pipelineLoading === config.id}
                      >
                        {pipelineLoading === config.id ? "Starting..." : "Run Search"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRunPipeline(config.id, "full")}
                        disabled={pipelineLoading === config.id}
                      >
                        Full Pipeline
                      </Button>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => editConfig(config)}>
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(config.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
