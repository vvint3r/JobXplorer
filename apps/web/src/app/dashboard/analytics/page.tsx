"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ApiClient } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface Stats {
  total: number;
  filled: number;
  submitted: number;
  failed: number;
  partial: number;
  by_board: Record<string, number>;
  by_method: Record<string, number>;
}

interface TimelineEntry {
  date: string;
  count: number;
}

interface Timeline {
  period: string;
  entries: TimelineEntry[];
}

interface AppLog {
  id: string;
  job_id: string;
  board_type: string;
  method: string;
  status: string;
  fields_filled: number | null;
  fields_total: number | null;
  applied_at: string;
}

const PERIODS = [
  { value: "today", label: "Today" },
  { value: "week", label: "This Week" },
  { value: "month", label: "This Month" },
  { value: "3mo", label: "3 Months" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All Time" },
];

const STATUS_COLORS: Record<string, string> = {
  submitted: "#22c55e",
  filled: "#3b82f6",
  partial: "#f59e0b",
  failed: "#ef4444",
};

const BOARD_COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6"];

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" | "success" | "warning" {
  if (status === "submitted") return "success";
  if (status === "failed") return "destructive";
  if (status === "partial") return "warning";
  return "secondary";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState("month");
  const [stats, setStats] = useState<Stats | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [logs, setLogs] = useState<AppLog[]>([]);
  const [loading, setLoading] = useState(true);
  const supabase = createClient();

  useEffect(() => {
    async function load() {
      setLoading(true);
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { setLoading(false); return; }

      const api = new ApiClient(session.access_token);
      const [s, t, l] = await Promise.all([
        api.getApplicationStats(period).catch(() => null),
        api.getApplicationTimeline(period).catch(() => null),
        api.listApplicationLogs({ limit: 10 }).catch(() => []),
      ]);

      setStats(s as Stats | null);
      setTimeline(t as Timeline | null);
      setLogs(l as AppLog[]);
      setLoading(false);
    }
    load();
  }, [period]);

  const boardData = stats
    ? Object.entries(stats.by_board).map(([name, value]) => ({ name, value }))
    : [];

  const statusData = stats
    ? [
        { name: "Submitted", value: stats.submitted, color: STATUS_COLORS.submitted },
        { name: "Filled", value: stats.filled, color: STATUS_COLORS.filled },
        { name: "Partial", value: stats.partial, color: STATUS_COLORS.partial },
        { name: "Failed", value: stats.failed, color: STATUS_COLORS.failed },
      ].filter((d) => d.value > 0)
    : [];

  const timelineData =
    timeline?.entries.map((e) => ({ date: formatDate(e.date), count: e.count })) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Application Analytics</h1>
      </div>

      {/* Period selector */}
      <div className="flex gap-2 flex-wrap">
        {PERIODS.map((p) => (
          <Button
            key={p.value}
            size="sm"
            variant={period === p.value ? "default" : "outline"}
            onClick={() => setPeriod(p.value)}
          >
            {p.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading analytics...</p>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Total Applied", value: stats?.total ?? 0, color: "text-foreground" },
              { label: "Submitted", value: stats?.submitted ?? 0, color: "text-green-600" },
              { label: "Form Filled", value: stats?.filled ?? 0, color: "text-blue-600" },
              { label: "Failed", value: stats?.failed ?? 0, color: "text-red-600" },
            ].map((card) => (
              <Card key={card.label}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {card.label}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className={`text-3xl font-bold ${card.color}`}>{card.value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Timeline chart */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Applications Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              {timelineData.length === 0 ? (
                <p className="text-sm text-muted-foreground py-8 text-center">
                  No applications logged in this period yet.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={timelineData}>
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#6366f1"
                      strokeWidth={2}
                      dot={timelineData.length <= 14}
                      name="Applications"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Board + Status breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By Job Board</CardTitle>
              </CardHeader>
              <CardContent>
                {boardData.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">No data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={boardData} layout="vertical">
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                      <Tooltip />
                      <Bar dataKey="value" name="Applications" radius={[0, 4, 4, 0]}>
                        {boardData.map((_, i) => (
                          <Cell key={i} fill={BOARD_COLORS[i % BOARD_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">By Status</CardTitle>
              </CardHeader>
              <CardContent>
                {statusData.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">No data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={statusData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={75}
                        label={({ name, percent }) =>
                          `${name} ${(percent * 100).toFixed(0)}%`
                        }
                        labelLine={false}
                      >
                        {statusData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Recent logs table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent Applications</CardTitle>
            </CardHeader>
            <CardContent>
              {logs.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No applications logged yet. Use the Chrome Extension to start auto-filling.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 pr-4 font-medium">Board</th>
                        <th className="pb-2 pr-4 font-medium">Method</th>
                        <th className="pb-2 pr-4 font-medium">Status</th>
                        <th className="pb-2 pr-4 font-medium">Fields</th>
                        <th className="pb-2 font-medium">Applied</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((log) => (
                        <tr key={log.id} className="border-b last:border-0">
                          <td className="py-2 pr-4 capitalize">{log.board_type}</td>
                          <td className="py-2 pr-4 text-muted-foreground text-xs">
                            {log.method.replace("_", " ")}
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant={statusVariant(log.status)} className="text-xs">
                              {log.status}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 text-muted-foreground">
                            {log.fields_filled != null && log.fields_total != null
                              ? `${log.fields_filled}/${log.fields_total}`
                              : "—"}
                          </td>
                          <td className="py-2 text-muted-foreground">
                            {formatDateTime(log.applied_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
