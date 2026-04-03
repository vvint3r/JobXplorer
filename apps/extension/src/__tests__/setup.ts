/**
 * Vitest global setup — runs before every test file.
 * Provides a minimal chrome.* mock so extension modules can be imported
 * in a jsdom environment without throwing "chrome is not defined".
 */

const chromeMock = {
  runtime: {
    id: "test-extension-id",
    sendMessage: vi.fn(),
    onMessage: {
      addListener: vi.fn(),
      removeListener: vi.fn(),
    },
    getURL: (path: string) => `chrome-extension://test-id/${path}`,
  },
  storage: {
    local: {
      get: vi.fn().mockResolvedValue({}),
      set: vi.fn().mockResolvedValue(undefined),
      remove: vi.fn().mockResolvedValue(undefined),
    },
  },
  action: {
    setBadgeText: vi.fn(),
    setBadgeBackgroundColor: vi.fn(),
  },
  notifications: {
    create: vi.fn(),
    clear: vi.fn(),
  },
  alarms: {
    create: vi.fn(),
    onAlarm: { addListener: vi.fn() },
  },
  tabs: {
    query: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
  },
};

// Attach to global so extension code can do `chrome.runtime.sendMessage(...)` etc.
Object.defineProperty(globalThis, "chrome", {
  value: chromeMock,
  writable: true,
});
