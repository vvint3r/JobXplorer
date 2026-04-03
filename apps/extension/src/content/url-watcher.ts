// ── URL Watcher ─────────────────────────────────────────────────────────────
// Detects SPA navigations (pushState/replaceState) and re-evaluates the page.
// Many ATS platforms (Workday, Greenhouse) use client-side routing.

type UrlChangeCallback = (newUrl: string) => void;

let currentUrl = location.href;
let observer: MutationObserver | null = null;

/**
 * Start watching for URL changes.
 * Intercepts history.pushState/replaceState and listens for popstate.
 */
export function watchUrlChanges(callback: UrlChangeCallback): () => void {
  currentUrl = location.href;

  // Intercept history methods
  const origPushState = history.pushState.bind(history);
  const origReplaceState = history.replaceState.bind(history);

  history.pushState = function (...args) {
    origPushState(...args);
    checkUrlChange();
  };

  history.replaceState = function (...args) {
    origReplaceState(...args);
    checkUrlChange();
  };

  // Listen for back/forward navigation
  window.addEventListener("popstate", checkUrlChange);

  // Also watch for href attribute changes on <a> tags triggering navigation
  // via MutationObserver on the document title (changes often indicate navigation)
  observer = new MutationObserver(checkUrlChange);
  const titleEl = document.querySelector("title");
  if (titleEl) {
    observer.observe(titleEl, { childList: true, characterData: true, subtree: true });
  }

  function checkUrlChange() {
    if (location.href !== currentUrl) {
      currentUrl = location.href;
      callback(currentUrl);
    }
  }

  // Return cleanup function
  return () => {
    history.pushState = origPushState;
    history.replaceState = origReplaceState;
    window.removeEventListener("popstate", checkUrlChange);
    observer?.disconnect();
  };
}
