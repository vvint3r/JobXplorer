// ── Settings ────────────────────────────────────────────────────────────────
// Extension configuration: API URL, behaviour toggles.

import React, { useState, useEffect, useCallback } from "react";
import {
  STORAGE_KEYS,
  DEFAULT_API_URL,
  DEFAULT_SETTINGS,
  type ExtensionSettings,
} from "@shared/constants";
import { getLocal, setLocal } from "@shared/storage";

export function Settings() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [settings, setSettings] = useState<ExtensionSettings>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load() {
      const storedUrl = await getLocal<string>(STORAGE_KEYS.API_URL);
      if (storedUrl) setApiUrl(storedUrl);

      const storedSettings = await getLocal<ExtensionSettings>(STORAGE_KEYS.SETTINGS);
      if (storedSettings) setSettings({ ...DEFAULT_SETTINGS, ...storedSettings });
    }
    load();
  }, []);

  const save = useCallback(
    async (newSettings: ExtensionSettings, newApiUrl: string) => {
      await setLocal(STORAGE_KEYS.API_URL, newApiUrl);
      await setLocal(STORAGE_KEYS.SETTINGS, newSettings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
    [],
  );

  const handleApiUrlChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setApiUrl(val);
      save(settings, val);
    },
    [settings, save],
  );

  const handleToggle = useCallback(
    (key: keyof ExtensionSettings) => {
      const updated = { ...settings, [key]: !settings[key] };
      setSettings(updated);
      save(updated, apiUrl);
    },
    [settings, apiUrl, save],
  );

  return (
    <div>
      {/* API URL */}
      <div className="jx-settings-section">
        <div className="jx-settings-section-title">Connection</div>
        <div className="jx-settings-input-row">
          <div className="jx-form-group">
            <label htmlFor="jx-api-url">API URL</label>
            <input
              id="jx-api-url"
              className="jx-input"
              type="url"
              value={apiUrl}
              onChange={handleApiUrlChange}
              placeholder="http://localhost:8000"
            />
          </div>
        </div>
      </div>

      {/* Behaviour Toggles */}
      <div className="jx-settings-section">
        <div className="jx-settings-section-title">Behaviour</div>

        <ToggleRow
          label="Auto-detect job boards"
          description="Show overlay on recognized ATS pages"
          checked={settings.autoDetect}
          onChange={() => handleToggle("autoDetect")}
        />

        <ToggleRow
          label="Random delays"
          description="Add human-like delays between field fills"
          checked={settings.randomDelays}
          onChange={() => handleToggle("randomDelays")}
        />

        <ToggleRow
          label="Fill voluntary disclosures"
          description="Auto-fill gender, veteran, disability questions"
          checked={settings.fillVoluntaryDisclosures}
          onChange={() => handleToggle("fillVoluntaryDisclosures")}
        />

        <ToggleRow
          label="Auto-submit"
          description="Automatically submit after filling (use with caution)"
          checked={settings.autoSubmit}
          onChange={() => handleToggle("autoSubmit")}
        />
      </div>

      {saved && <div className="jx-settings-saved">Settings saved</div>}

      <div className="jx-settings-version">
        JobXplore Extension v0.1.0
      </div>
    </div>
  );
}

// ── Toggle Row Component ──────────────────────────────────────────────────

interface ToggleRowProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: () => void;
}

function ToggleRow({ label, description, checked, onChange }: ToggleRowProps) {
  return (
    <div className="jx-toggle-row">
      <div>
        <div className="jx-toggle-label">{label}</div>
        <div className="jx-toggle-desc">{description}</div>
      </div>
      <label className="jx-toggle">
        <input type="checkbox" checked={checked} onChange={onChange} />
        <span className="jx-toggle-track" />
      </label>
    </div>
  );
}
