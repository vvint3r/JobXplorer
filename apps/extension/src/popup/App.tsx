import React, { useState, useEffect, useCallback } from "react";
import type { AuthStatus } from "@shared/types";
import { LoginForm } from "./components/LoginForm";
import { Dashboard } from "./components/Dashboard";
import { JobQueue } from "./components/JobQueue";
import { Settings } from "./components/Settings";

type Tab = "dashboard" | "jobs" | "settings";

export function App() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");

  const checkAuth = useCallback(async () => {
    try {
      const status: AuthStatus = await chrome.runtime.sendMessage({
        type: "AUTH_GET_STATUS",
      });
      setAuth(status);
    } catch {
      setAuth({ authenticated: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const handleLoginSuccess = useCallback(() => {
    checkAuth();
  }, [checkAuth]);

  const handleLogout = useCallback(async () => {
    await chrome.runtime.sendMessage({ type: "AUTH_LOGOUT" });
    setAuth({ authenticated: false });
    setActiveTab("dashboard");
  }, []);

  if (loading) {
    return (
      <div className="jx-popup">
        <div className="jx-loading">Loading...</div>
      </div>
    );
  }

  if (!auth?.authenticated) {
    return (
      <div className="jx-popup">
        <div className="jx-popup-header">
          <span className="jx-logo">JX</span>
          <span className="jx-popup-title">JobXplore</span>
        </div>
        <LoginForm onSuccess={handleLoginSuccess} />
      </div>
    );
  }

  return (
    <div className="jx-popup">
      {/* Header */}
      <div className="jx-popup-header">
        <div className="jx-header-left">
          <span className="jx-logo">JX</span>
          <span className="jx-popup-title">JobXplore</span>
        </div>
        <button className="jx-logout-btn" onClick={handleLogout} title="Sign out">
          Sign Out
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="jx-tabs">
        <button
          className={`jx-tab ${activeTab === "dashboard" ? "active" : ""}`}
          onClick={() => setActiveTab("dashboard")}
        >
          Dashboard
        </button>
        <button
          className={`jx-tab ${activeTab === "jobs" ? "active" : ""}`}
          onClick={() => setActiveTab("jobs")}
        >
          Jobs
        </button>
        <button
          className={`jx-tab ${activeTab === "settings" ? "active" : ""}`}
          onClick={() => setActiveTab("settings")}
        >
          Settings
        </button>
      </div>

      {/* Tab Content */}
      <div className="jx-tab-content">
        {activeTab === "dashboard" && <Dashboard auth={auth} />}
        {activeTab === "jobs" && <JobQueue />}
        {activeTab === "settings" && <Settings />}
      </div>
    </div>
  );
}
