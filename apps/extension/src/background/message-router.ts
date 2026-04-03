// ── Message Router ──────────────────────────────────────────────────────────
// Routes chrome.runtime messages from popup/content scripts to handlers.

import type { ExtensionMessage, AuthSetTokenPayload } from "@shared/types";
import { storeToken, clearToken, getAuthStatus } from "./auth";
import {
  getProfile,
  lookupJobByUrl,
  getOptimizedResume,
  downloadResumePdf,
  logApplication,
  updateJobStatus,
  invalidateProfileCache,
  getJobs,
  getNotificationCount,
  markNotificationRead,
} from "./api-client";

export async function handleMessage(
  message: ExtensionMessage,
): Promise<unknown> {
  switch (message.type) {
    // ── Auth ───────────────────────────────────────────────────────────────
    case "AUTH_SET_TOKEN":
      await storeToken(message.payload as AuthSetTokenPayload);
      return { ok: true };

    case "AUTH_GET_STATUS":
      return getAuthStatus();

    case "AUTH_LOGOUT":
      await clearToken();
      invalidateProfileCache();
      return { ok: true };

    // ── API Calls ──────────────────────────────────────────────────────────
    case "API_GET_PROFILE":
      return getProfile();

    case "API_LOOKUP_JOB_BY_URL":
      return lookupJobByUrl(message.url as string);

    case "API_GET_OPTIMIZED_RESUME":
      return getOptimizedResume(message.resumeId as string);

    case "API_DOWNLOAD_RESUME_PDF":
      return downloadResumePdf(message.resumeId as string);

    case "API_OPTIMIZE_RESUME":
      // Trigger resume optimization on the server — returns the new resume ID
      // This is handled by the API directly; we just proxy the request
      return null; // TODO: implement when resume optimization endpoint is ready

    case "API_LOG_APPLICATION":
      await logApplication(message.payload as Parameters<typeof logApplication>[0]);
      return { ok: true };

    case "API_UPDATE_JOB_STATUS":
      await updateJobStatus(
        message.jobId as string,
        message.status as string,
      );
      return { ok: true };

    case "API_GET_JOBS":
      return getJobs(message.params as Parameters<typeof getJobs>[0]);

    // ── Notifications ──────────────────────────────────────────────────────
    case "NOTIFICATIONS_GET_COUNT":
      return getNotificationCount();

    case "NOTIFICATIONS_MARK_READ":
      return markNotificationRead(message.payload as { id: string });

    // ── Cache ──────────────────────────────────────────────────────────────
    case "CACHE_INVALIDATE":
      invalidateProfileCache();
      return { ok: true };

    default:
      console.warn("[background] Unknown message type:", message.type);
      return { error: `Unknown message type: ${message.type}` };
  }
}
