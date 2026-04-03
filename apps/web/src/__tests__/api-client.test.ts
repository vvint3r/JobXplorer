/**
 * Unit tests for the ApiClient (src/lib/api.ts).
 *
 * fetch is mocked globally — no real network calls are made.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { ApiClient } from "@/lib/api";

// ── fetch mock setup ──────────────────────────────────────────────────────────

function mockFetch(status: number, body: unknown) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ── Constructor & auth header ─────────────────────────────────────────────────

describe("ApiClient", () => {
  it("attaches Bearer token to every request", async () => {
    mockFetch(200, { id: "1", email: "test@example.com", plan: "free", created_at: "" });

    const client = new ApiClient("my-jwt-token");
    await client.getProfile();

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const opts = call[1] as RequestInit;
    expect((opts.headers as Record<string, string>)["Authorization"]).toBe("Bearer my-jwt-token");
  });

  it("sends Content-Type: application/json", async () => {
    mockFetch(200, {});
    const client = new ApiClient("tok");
    await client.getProfile();

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const opts = call[1] as RequestInit;
    expect((opts.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("throws on non-ok response with detail", async () => {
    mockFetch(422, { detail: "Validation error" });
    const client = new ApiClient("tok");
    await expect(client.getProfile()).rejects.toThrow("Validation error");
  });

  it("throws generic message when response has no detail", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockRejectedValue(new Error("not json")),
    } as unknown as Response);

    const client = new ApiClient("tok");
    await expect(client.getProfile()).rejects.toThrow("API error: 500");
  });
});

// ── User endpoints ────────────────────────────────────────────────────────────

describe("ApiClient.getProfile", () => {
  it("calls GET /api/v1/users/profile", async () => {
    mockFetch(200, { id: "1", email: "test@example.com", plan: "free", created_at: "" });
    const client = new ApiClient("tok");
    await client.getProfile();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/users/profile"),
      expect.any(Object)
    );
  });
});

describe("ApiClient.updateProfile", () => {
  it("calls PUT /api/v1/users/profile with JSON body", async () => {
    mockFetch(200, { id: "1", email: "test@example.com", full_name: "Jane", plan: "free", created_at: "" });
    const client = new ApiClient("tok");
    await client.updateProfile({ full_name: "Jane" });

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[1].method).toBe("PUT");
    expect(call[1].body).toBe(JSON.stringify({ full_name: "Jane" }));
  });
});

describe("ApiClient.getLinkedInCookiesStatus", () => {
  it("returns uploaded status", async () => {
    mockFetch(200, { uploaded: false, path: null });
    const client = new ApiClient("tok");
    const result = await client.getLinkedInCookiesStatus();
    expect(result.uploaded).toBe(false);
    expect(result.path).toBeNull();
  });
});

// ── Notification endpoints ────────────────────────────────────────────────────

describe("ApiClient notification methods", () => {
  it("getNotifications calls /notifications/", async () => {
    mockFetch(200, []);
    const client = new ApiClient("tok");
    await client.getNotifications();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/notifications/"),
      expect.any(Object)
    );
  });

  it("getNotificationCount calls /notifications/count", async () => {
    mockFetch(200, { unread: 3 });
    const client = new ApiClient("tok");
    const result = await client.getNotificationCount();
    expect(result.unread).toBe(3);
  });

  it("markNotificationRead calls POST /notifications/{id}/read", async () => {
    const id = "abc-123";
    mockFetch(200, { id, read_at: new Date().toISOString() });
    const client = new ApiClient("tok");
    await client.markNotificationRead(id);

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toContain(`/notifications/${id}/read`);
    expect(call[1].method).toBe("POST");
  });

  it("markAllNotificationsRead calls POST /notifications/read-all", async () => {
    mockFetch(200, { unread: 0 });
    const client = new ApiClient("tok");
    await client.markAllNotificationsRead();

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toContain("/notifications/read-all");
    expect(call[1].method).toBe("POST");
  });
});

// ── Application logs endpoints ────────────────────────────────────────────────

describe("ApiClient application stats", () => {
  it("getApplicationStats sends period param", async () => {
    mockFetch(200, { total: 5, submitted: 3, filled: 1, failed: 1, partial: 0, by_board: {}, by_method: {} });
    const client = new ApiClient("tok");
    await client.getApplicationStats("week");

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("period=week"),
      expect.any(Object)
    );
  });

  it("getApplicationTimeline sends period param", async () => {
    mockFetch(200, { period: "month", entries: [] });
    const client = new ApiClient("tok");
    await client.getApplicationTimeline("month");

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("period=month"),
      expect.any(Object)
    );
  });

  it("listApplicationLogs builds query string correctly", async () => {
    mockFetch(200, []);
    const client = new ApiClient("tok");
    await client.listApplicationLogs({ status: "submitted", limit: 10 });

    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("status=submitted");
    expect(url).toContain("limit=10");
  });
});
