/**
 * Session watchdog: redirect to login when the server reports session expiry.
 * Prefer Server-Sent Events; fall back to short polling if SSE is unavailable.
 * Status checks do not count as user activity (server peek-only).
 */
(function () {
  "use strict";

  var cfg = window.CHRONOLOG_SESSION;
  if (!cfg || !cfg.eventsUrl || !cfg.logoutUrl) return;

  var redirected = false;

  function goToLogin() {
    if (redirected) return;
    redirected = true;
    try {
      if (es) es.close();
    } catch (e) { /* ignore */ }
    window.location.replace(cfg.logoutUrl);
  }

  // --- Server-Sent Events (primary) ---
  var es = null;
  if (typeof window.EventSource === "function") {
    try {
      es = new EventSource(cfg.eventsUrl);
      es.addEventListener("session-expired", function () {
        goToLogin();
      });
      es.onerror = function () {
        // Connection dropped; EventSource reconnects automatically.
        // If the tab was offline a long time, a subsequent status poll helps.
      };
      return;
    } catch (e) {
      es = null;
    }
  }

  // --- Polling fallback ---
  if (!cfg.statusUrl) return;

  function poll() {
    if (redirected) return;
    fetch(cfg.statusUrl, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then(function (res) {
        if (res.status === 401 || res.status === 403) {
          goToLogin();
          return null;
        }
        return res.json();
      })
      .then(function (data) {
        if (!data) return;
        if (!data.active) {
          goToLogin();
          return;
        }
        var remaining = typeof data.seconds_remaining === "number" ? data.seconds_remaining : 30;
        var delayMs = Math.max(1000, Math.min(remaining, 15) * 1000);
        setTimeout(poll, delayMs);
      })
      .catch(function () {
        setTimeout(poll, 15000);
      });
  }

  poll();
})();
