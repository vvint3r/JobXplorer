// ── Login Form ──────────────────────────────────────────────────────────────
// Email/password login via Supabase REST API.
// Sends JWT + refresh token to background service worker after sign-in.

import React, { useState, useCallback } from "react";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "@shared/constants";
import type { AuthSetTokenPayload } from "@shared/types";

interface LoginFormProps {
  onSuccess: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setLoading(true);

      try {
        // Call Supabase REST API directly (no SDK in popup to keep bundle small)
        const resp = await fetch(
          `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              apikey: SUPABASE_ANON_KEY,
            },
            body: JSON.stringify({ email, password }),
          },
        );

        if (!resp.ok) {
          const data = await resp.json().catch(() => null);
          throw new Error(
            data?.error_description ?? data?.msg ?? `Login failed (${resp.status})`,
          );
        }

        const data = await resp.json();

        // Send tokens to background service worker
        const payload: AuthSetTokenPayload = {
          token: data.access_token,
          refreshToken: data.refresh_token,
          expiresAt: data.expires_at,
        };

        await chrome.runtime.sendMessage({
          type: "AUTH_SET_TOKEN",
          ...payload,
        });

        onSuccess();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Login failed");
      } finally {
        setLoading(false);
      }
    },
    [email, password, onSuccess],
  );

  return (
    <div className="jx-login">
      <div className="jx-login-title">Sign In</div>
      <div className="jx-login-subtitle">
        Use your JobXplore account credentials
      </div>

      <form onSubmit={handleSubmit}>
        <div className="jx-form-group">
          <label htmlFor="jx-email">Email</label>
          <input
            id="jx-email"
            className="jx-input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            autoFocus
          />
        </div>

        <div className="jx-form-group">
          <label htmlFor="jx-password">Password</label>
          <input
            id="jx-password"
            className="jx-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            required
          />
        </div>

        <button
          type="submit"
          className="jx-btn jx-btn-primary"
          disabled={loading || !email || !password}
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>

        {error && <div className="jx-error">{error}</div>}
      </form>
    </div>
  );
}
