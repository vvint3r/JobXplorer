"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CategoryData {
  name: string;
  count: number;
}

interface InsightData {
  id: string;
  search_config_id: string;
  total_jobs_analysed: number;
  categorised_phrases: Record<string, [string, number][]> | null;
  summary: {
    total_jobs: number;
    top_terms: [string, number][];
    top_companies: [string, number][];
    top_locations: [string, number][];
  } | null;
  updated_at: string;
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightData[]>([]);
  const [selectedInsight, setSelectedInsight] = useState<InsightData | null>(null);
  const [searchConfigs, setSearchConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const supabase = createClient();

  useEffect(() => {
    async function load() {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const api = new ApiClient(session.access_token);
      const [result, configs] = await Promise.all([
        api.listInsights().catch(() => []),
        api.listSearchConfigs().catch(() => []),
      ]);
      const list = result as InsightData[];
      setInsights(list);
      setSearchConfigs(configs as any[]);
      if (list.length > 0) setSelectedInsight(list[0]);
      setLoading(false);
    }
    load();
  }, []);

  function getCategoryItems(phrases: Record<string, [string, number][]>, category: string): CategoryData[] {
    const items = phrases?.[category] || [];
    return items.slice(0, 15).map(([name, count]: [string, number]) => ({ name, count }));
  }

  function getConfigTitle(configId: string): string {
    const config = searchConfigs.find((c: any) => c.id === configId);
    return config?.job_title || "Unknown Search";
  }

  const skillCategories = [
    { key: "technical_skill", label: "Technical Skills" },
    { key: "tools_platforms", label: "Tools & Platforms" },
    { key: "analytics_function", label: "Analytics Functions" },
    { key: "soft_skill", label: "Soft Skills" },
    { key: "domain_expertise", label: "Domain Expertise" },
    { key: "methodology_approach", label: "Methodologies" },
  ];

  const overviewCategories = [
    { key: "description_terms", label: "Top Terms in Descriptions" },
    { key: "title_terms", label: "Top Terms in Titles" },
    { key: "phrases", label: "Common Phrases" },
  ];

  if (loading) {
    return <p className="text-muted-foreground">Loading insights...</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">JD Insights</h1>

      {insights.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No insights yet. Run the insights pipeline on your collected jobs.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Selector */}
          {insights.length > 1 && (
            <select
              className="rounded-md border bg-background px-3 py-2 text-sm"
              value={selectedInsight?.id || ""}
              onChange={(e) => setSelectedInsight(insights.find((i) => i.id === e.target.value) || null)}
            >
              {insights.map((i) => (
                <option key={i.id} value={i.id}>
                  {getConfigTitle(i.search_config_id)} — {i.total_jobs_analysed} jobs
                </option>
              ))}
            </select>
          )}

          {selectedInsight && (
            <>
              {/* Summary stats */}
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-2xl font-bold">{selectedInsight.total_jobs_analysed}</p>
                    <p className="text-sm text-muted-foreground">Jobs Analysed</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm font-medium mb-2">Top Companies</p>
                    <div className="flex flex-wrap gap-1">
                      {(selectedInsight.summary?.top_companies || []).slice(0, 5).map(([name, count]) => (
                        <Badge key={name} variant="outline" className="text-xs">
                          {name} ({count})
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm font-medium mb-2">Top Locations</p>
                    <div className="flex flex-wrap gap-1">
                      {(selectedInsight.summary?.top_locations || []).slice(0, 5).map(([name, count]) => (
                        <Badge key={name} variant="outline" className="text-xs">
                          {name} ({count})
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Overview categories (terms, phrases) */}
              <div className="grid gap-4 md:grid-cols-3">
                {overviewCategories.map(({ key, label }) => {
                  const items = getCategoryItems(selectedInsight.categorised_phrases || {}, key);
                  if (items.length === 0) return null;
                  const maxCount = items[0]?.count || 1;

                  return (
                    <Card key={key}>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg">{label}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {items.map(({ name, count }) => (
                            <div key={name} className="flex items-center gap-2">
                              <div className="flex-1">
                                <div className="flex justify-between text-sm">
                                  <span className="truncate">{name}</span>
                                  <span className="text-muted-foreground shrink-0 ml-2">{count}</span>
                                </div>
                                <div className="mt-1 h-1.5 w-full rounded-full bg-secondary">
                                  <div
                                    className="h-1.5 rounded-full bg-blue-500"
                                    style={{ width: `${(count / maxCount) * 100}%` }}
                                  />
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              {/* Skill categories */}
              <h2 className="text-xl font-semibold pt-2">Skills & Requirements Breakdown</h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {skillCategories.map(({ key, label }) => {
                  const items = getCategoryItems(selectedInsight.categorised_phrases || {}, key);
                  if (items.length === 0) return null;
                  const maxCount = items[0]?.count || 1;

                  return (
                    <Card key={key}>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg">{label}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {items.map(({ name, count }) => (
                            <div key={name} className="flex items-center gap-2">
                              <div className="flex-1">
                                <div className="flex justify-between text-sm">
                                  <span className="truncate">{name}</span>
                                  <span className="text-muted-foreground shrink-0 ml-2">{count}</span>
                                </div>
                                <div className="mt-1 h-1.5 w-full rounded-full bg-secondary">
                                  <div
                                    className="h-1.5 rounded-full bg-primary"
                                    style={{ width: `${(count / maxCount) * 100}%` }}
                                  />
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
