// ── Auth Token Management ───────────────────────────────────────────────────
// Handles JWT storage, retrieval, refresh, and expiry.
// JWT lives in chrome.storage.session (encrypted, cleared on browser close).
// Refresh token lives in chrome.storage.local (persistent).

import { STORAGE_KEYS, SUPABASE_URL, SUPABASE_ANON_KEY } from "@shared/constants";
import {
  getSession,
  setSession,
  removeSession,
  getLocal,
  setLocal,
  removeLocal,
} from "@shared/storage";
import type { AuthSetTokenPayload, AuthStatus } from "@shared/types";

/** Buffer before token expiry to trigger proactive refresh (60 seconds). */
const REFRESH_BUFFER_MS = 60_000;

/** Store tokens received from the popup after Supabase sign-in. */
export async function storeToken(payload: AuthSetTokenPayload): Promise<void> {
  await setSession(STORAGE_KEYS.JWT, payload.token);
  await setSession(STORAGE_KEYS.EXPIRES_AT, payload.expiresAt);
  await setLocal(STORAGE_KEYS.REFRESH_TOKEN, payload.refreshToken);
}

/** Clear all auth tokens (logout). */
export async function clearToken(): Promise<void> {
  await removeSession(STORAGE_KEYS.JWT);
  await removeSession(STORAGE_KEYS.EXPIRES_AT);
  await removeLocal(STORAGE_KEYS.REFRESH_TOKEN);
}

/** Check if the stored JWT is expired (or about to expire). */
async function isTokenExpired(): Promise<boolean> {
  const expiresAt = await getSession<number>(STORAGE_KEYS.EXPIRES_AT);
  if (!expiresAt) return true;
  return Date.now() >= expiresAt * 1000 - REFRESH_BUFFER_MS;
}

/** Refresh the JWT using the stored refresh token via Supabase REST API. */
async function refreshToken(): Promise<string | null> {
  const refreshTok = await getLocal<string>(STORAGE_KEYS.REFRESH_TOKEN);
  if (!refreshTok) return null;

  try {
    const resp = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({ refresh_token: refreshTok }),
    });

    if (!resp.ok) {
      console.warn("[auth] Refresh failed:", resp.status);
      await clearToken();
      return null;
    }

    const data = await resp.json();
    await storeToken({
      token: data.access_token,
      refreshToken: data.refresh_token,
      expiresAt: data.expires_at,
    });
    return data.access_token;
  } catch (err) {
    console.error("[auth] Refresh error:", err);
    await clearToken();
    return null;
  }
}

/**
 * Get a valid JWT, refreshing if necessary.
 * Returns null if not authenticated.
 */
export async function getValidToken(): Promise<string | null> {
  const jwt = await getSession<string>(STORAGE_KEYS.JWT);
  if (!jwt) {
    // Try to refresh from stored refresh token
    return refreshToken();
  }

  if (await isTokenExpired()) {
    return refreshToken();
  }

  return jwt;
}

/** Get the current authentication status without refreshing. */
export async function getAuthStatus(): Promise<AuthStatus> {
  const token = await getValidToken();
  if (!token) {
    return { authenticated: false };
  }

  // Decode JWT payload to get user info (no verification — Supabase handles that)
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      authenticated: true,
      email: payload.email,
      fullName: payload.user_metadata?.full_name,
    };
  } catch {
    return { authenticated: true };
  }
}
