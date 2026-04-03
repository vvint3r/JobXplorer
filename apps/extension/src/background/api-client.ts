// ── Extension API Client ────────────────────────────────────────────────────
// All API communication with the JobXplore backend happens here.
// The background service worker is the sole caller — content scripts and
// popup send chrome.runtime messages, background routes to this client.

import { PROFILE_CACHE_TTL } from "@shared/constants";
import { getApiUrl } from "@shared/storage";
import type { ApplicationLogPayload, JobMatch, ResumeComponents, UserConfig } from "@shared/types";
import { getValidToken } from "./auth";

interface CacheEntry<T> {
  data: T;
  fetchedAt: number;
}

let profileCache: CacheEntry<UserConfig> | null = null;

/** Invalidate the in-memory profile cache. */
export function invalidateProfileCache(): void {
  profileCache = null;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getValidToken();
  if (!token) throw new Error("Not authenticated");

  const baseUrl = await getApiUrl();
  const url = `${baseUrl}/api/v1${path}`;

  const resp = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status}: ${body}`);
  }

  return resp.json();
}

async function apiFetchBlob(path: string): Promise<ArrayBuffer> {
  const token = await getValidToken();
  if (!token) throw new Error("Not authenticated");

  const baseUrl = await getApiUrl();
  const url = `${baseUrl}/api/v1${path}`;

  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${resp.statusText}`);
  }

  return resp.arrayBuffer();
}

// ── Profile ─────────────────────────────────────────────────────────────────

export async function getProfile(): Promise<UserConfig> {
  if (profileCache && Date.now() - profileCache.fetchedAt < PROFILE_CACHE_TTL) {
    return profileCache.data;
  }

  const data = await apiFetch<UserConfig>("/users/me/config");
  profileCache = { data, fetchedAt: Date.now() };
  return data;
}

// ── Job Lookup ──────────────────────────────────────────────────────────────

export async function lookupJobByUrl(url: string): Promise<JobMatch | null> {
  try {
    return await apiFetch<JobMatch | null>(`/jobs/lookup?url=${encodeURIComponent(url)}`);
  } catch {
    return null;
  }
}

// ── Jobs List ───────────────────────────────────────────────────────────────

export async function getJobs(params: {
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_order?: string;
}): Promise<unknown[]> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.per_page) qs.set("per_page", String(params.per_page));
  if (params.sort_by) qs.set("sort_by", params.sort_by);
  if (params.sort_order) qs.set("sort_order", params.sort_order);

  return apiFetch<unknown[]>(`/jobs/?${qs.toString()}`);
}

// ── Optimized Resume ────────────────────────────────────────────────────────

export async function getOptimizedResume(resumeId: string): Promise<ResumeComponents> {
  return apiFetch<ResumeComponents>(`/optimized-resumes/${resumeId}`);
}

export async function downloadResumePdf(resumeId: string): Promise<string> {
  const buffer = await apiFetchBlob(`/optimized-resumes/${resumeId}/pdf`);
  // Convert ArrayBuffer to base64 for transfer to content script
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

// ── Application Logging ─────────────────────────────────────────────────────

export async function logApplication(payload: ApplicationLogPayload): Promise<void> {
  await apiFetch("/application-logs/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Job Status ──────────────────────────────────────────────────────────────

export async function updateJobStatus(
  jobId: string,
  status: string,
): Promise<void> {
  await apiFetch(`/jobs/${jobId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function getNotificationCount(): Promise<{ unread: number }> {
  return apiFetch<{ unread: number }>("/notifications/count");
}

export async function markNotificationRead(payload: { id: string }): Promise<void> {
  await apiFetch(`/notifications/${payload.id}/read`, { method: "POST" });
}

/** Re-export so background/index.ts can call it without importing from storage. */
export { getApiUrl } from "@shared/storage";
