// ── Background Service Worker Entry ─────────────────────────────────────────
// MV3 service worker: manages auth, routes messages, handles alarms.

import type { ExtensionMessage } from "@shared/types";
import { handleMessage } from "./message-router";

// ── Install / Startup ──────────────────────────────────────────────────────

const NOTIFICATION_ALARM = "checkNotifications";

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("[background] Extension installed");
  } else if (details.reason === "update") {
    console.log("[background] Extension updated to", chrome.runtime.getManifest().version);
  }
  // Register periodic alarm for notification polling
  chrome.alarms.create(NOTIFICATION_ALARM, { periodInMinutes: 5 });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(NOTIFICATION_ALARM, { periodInMinutes: 5 });
});

// ── Alarm: Notification Polling ────────────────────────────────────────────

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== NOTIFICATION_ALARM) return;
  try {
    const { getValidToken } = await import("./auth");
    const { getApiUrl } = await import("./api-client");
    const [token, apiUrl] = await Promise.all([getValidToken(), getApiUrl()]);
    if (!token) return;

    const res = await fetch(`${apiUrl}/api/v1/notifications/count`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;

    const { unread } = await res.json() as { unread: number };

    // Update extension badge
    chrome.action.setBadgeText({ text: unread > 0 ? String(unread) : "" });
    chrome.action.setBadgeBackgroundColor({ color: "#ef4444" });

    // Fire OS notification if there are new unread notifications
    if (unread > 0) {
      chrome.notifications.create(`jobxplore-notif-${Date.now()}`, {
        type: "basic",
        iconUrl: chrome.runtime.getURL("src/assets/icon48.png"),
        title: "JobXplore",
        message: `You have ${unread} new notification${unread > 1 ? "s" : ""}`,
      });
    }
  } catch (err) {
    console.warn("[background] Notification poll failed:", err);
  }
});

// ── Message Listener ───────────────────────────────────────────────────────
// All messages from popup and content scripts are routed through here.

chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, _sender, sendResponse) => {
    handleMessage(message)
      .then(sendResponse)
      .catch((err) => {
        console.error("[background] Message handler error:", err);
        sendResponse({ error: err.message ?? "Unknown error" });
      });

    // Return true to indicate we will call sendResponse asynchronously
    return true;
  },
);
