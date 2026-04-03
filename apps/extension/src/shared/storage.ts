import { STORAGE_KEYS, DEFAULT_SETTINGS, type ExtensionSettings } from "./constants";

// ── chrome.storage helpers ───────────────────────────────────────────────────

/** Get a value from chrome.storage.session (encrypted, cleared on close). */
export async function getSession<T>(key: string): Promise<T | undefined> {
  const result = await chrome.storage.session.get(key);
  return result[key] as T | undefined;
}

/** Set a value in chrome.storage.session. */
export async function setSession(key: string, value: unknown): Promise<void> {
  await chrome.storage.session.set({ [key]: value });
}

/** Remove a value from chrome.storage.session. */
export async function removeSession(key: string): Promise<void> {
  await chrome.storage.session.remove(key);
}

/** Get a value from chrome.storage.local (persistent across sessions). */
export async function getLocal<T>(key: string): Promise<T | undefined> {
  const result = await chrome.storage.local.get(key);
  return result[key] as T | undefined;
}

/** Set a value in chrome.storage.local. */
export async function setLocal(key: string, value: unknown): Promise<void> {
  await chrome.storage.local.set({ [key]: value });
}

/** Remove a value from chrome.storage.local. */
export async function removeLocal(key: string): Promise<void> {
  await chrome.storage.local.remove(key);
}

// ── Convenience wrappers ─────────────────────────────────────────────────────

export async function getApiUrl(): Promise<string> {
  const url = await getLocal<string>(STORAGE_KEYS.API_URL);
  return url ?? "http://localhost:8000";
}

export async function setApiUrl(url: string): Promise<void> {
  await setLocal(STORAGE_KEYS.API_URL, url);
}

export async function getSettings(): Promise<ExtensionSettings> {
  const settings = await chrome.storage.sync.get(STORAGE_KEYS.SETTINGS);
  return { ...DEFAULT_SETTINGS, ...(settings[STORAGE_KEYS.SETTINGS] ?? {}) };
}

export async function saveSettings(settings: Partial<ExtensionSettings>): Promise<void> {
  const current = await getSettings();
  await chrome.storage.sync.set({
    [STORAGE_KEYS.SETTINGS]: { ...current, ...settings },
  });
}
