# Cold-Start Login — Browser-Direct Backend Wake

**Date:** 2026-07-02
**Status:** Design approved → spec for implementation
**Scope:** Frontend service only (`frontend/` — SPA + nginx entrypoint). No backend code changes, no Render dashboard changes, stays on the free tier.
**Supersedes the residual-stall acceptance in** `2026-06-28-cold-start-login-recovery-design.md` (its frontend robustness work remains valid and is kept).

## Problem

Testers still get stuck on the Render demo login: the "waking up" banner counts past the
3-minute budget and ends in *"The demo server is still starting up."* The prior fixes
(#105–#107, #114) made the retry loop robust, on the assumption that Render's wake is
variable and can stall. That assumption was wrong.

### Root cause (proven from live evidence, 2026-07-02)

**The wake is never triggered for these sessions.** All browser API traffic goes through
the frontend nginx proxy (`browser → kpi-operations-frontend → proxy_pass →
kpi-operations-api.onrender.com`), so the wake-triggering request originates from
Render's **shared egress IPs**, which Render's edge rate-limits for hibernation wakes
(`429`, `x-render-routing: hibernate-rate-limited`).

Evidence:

- **Tester session 2026-06-29 13:58–14:05 UTC** (matches the reported screenshots at
  8:05/8:10 AM Mexico): frontend nginx logs show every `POST /api/auth/login` **and**
  the warm-up `GET /api/health/live` answered with an instant `429` for 7+ minutes.
- **Backend logs for the same window: zero.** The backend emitted no logs at all from
  2026-06-28 21:01 (hibernate) until a direct probe on 2026-07-02 — it slept through
  every tester visit for four days.
- **Direct probe 2026-07-02 13:35 UTC:** `curl https://kpi-operations-api.onrender.com/health/live`
  from an external IP was held open ~92s → `200`. Backend boot logs confirm a clean
  cold boot (≈11s provision + 19s entrypoint/Alembic + 26s Python import + ≈35s demo
  re-seed on the ephemeral SQLite DB).
- The same signature appeared during #114's live verification ("proxied wakes got
  instant 429; a single direct request woke it in 92s") and was misread as a
  test-environment artifact. It is the production failure mode; intermittency tracks
  whether the shared-IP wake budget happens to be saturated.

### Contributing facts (all verified live 2026-07-02)

- The deployed SPA was built with `VITE_API_URL=/api` (the Dockerfile ARG default) —
  the `render.yaml` value never reached the Vite build, so *everything* including the
  warm-up ping is proxied. Any fix relying on build-time env vars repeats a mechanism
  that already failed silently once.
- Live CSP already contains `connect-src 'self' https://kpi-operations-api.onrender.com`
  (`CSP_CONNECT_EXTRA` is set on the live service) — a direct browser fetch to the API
  origin is *already permitted*. The old "CSP blocks direct fetch" note is outdated.
- Backend `CORS_ORIGINS` already equals the frontend origin → a **readable** (cors-mode)
  direct fetch is possible.
- The real backend health route is **`/health/live`** (`backend/routes/health.py`,
  router prefix `/health`). `/api/health/live` and `/api/v1/health/live` both 404 —
  the comments in `authStore.ts` are stale.
- nginx `proxy_*_timeout` is 60s, shorter than the ~92s wake — even a proxied request
  that *did* hold for a wake would be cut off.

## Fix

Make the **browser** wake the backend directly, from the tester's own IP — exactly the
path proven to wake it reliably in ~90–100s. Login itself stays on the same-origin proxy.

### 1. Runtime wake-origin injection — `frontend/docker-entrypoint.sh`

In the **external-HTTPS branch only** (the branch that already derives `BACKEND_HOST`
from `BACKEND_URL`):

- sed-inject `<meta name="backend-wake-origin" content="https://$BACKEND_HOST">` into
  `/usr/share/nginx/html/index.html` (before `</head>`).
- Append `https://$BACKEND_HOST` to the CSP `connect-src` replacement string alongside
  `CSP_CONNECT_EXTRA`, so the direct fetch works even if that env var is ever unset.
  Duplicate origins in a CSP source list are harmless.

The internal-Docker and no-backend branches inject nothing → local dev, docker-compose,
and `e2e-sqlite` keep today's behavior unchanged (no hibernation exists there).

Why a meta tag: the CSP has `script-src 'self'` (no `unsafe-inline`), so an injected
inline `<script>` would be blocked; a meta tag is inert and synchronously readable.
Why runtime injection: `BACKEND_URL` at container runtime is the one delivery path
proven to work (it already generates the proxy config); build args are not.

### 2. Wake service — new `frontend/src/services/backendWake.ts`

Small pure module, unit-testable:

- `getWakeOrigin(): string | null` — reads the meta tag from `document`.
- `wakeBackend(): Promise<void>` — best-effort `fetch(origin + '/health/live',
  { mode: 'cors' })` with **no timeout**: Render's edge holds the request open for the
  full boot, so its resolution *is* the "server is up" signal. Errors are swallowed
  (same best-effort contract as today's `warmUpBackend`).
- `pingWake(timeoutMs≈12000): Promise<void>` — short-timeout (AbortController),
  fire-and-forget variant for periodic re-pings during the waiting loop (redundant wake
  triggers in case the held request is dropped by a mobile network).

Both functions **no-op when `getWakeOrigin()` is null** — the guard lives in the
service, so consumers wire them unconditionally.

cors mode (not no-cors) because backend `CORS_ORIGINS` already allows the frontend
origin — readable responses cost nothing and keep the door open for status-aware UX.

### 3. Store + retry-loop integration — `authStore.ts`, `useColdStartLogin.ts`, `LoginView.vue`

- `authStore.warmUpBackend()`: if `getWakeOrigin()` returns an origin → `wakeBackend()`
  (direct); else → the current same-origin best-effort ping, unchanged. Correct the
  stale health-route comments while touching them.
- `useColdStartLogin(loginFn, options)` gains one optional hook: `wakePing?: () => void`,
  invoked fire-and-forget at the start of each `waking` retry iteration. No other
  behavior change: 20s per-attempt timeout, 10s retry delay, **180s budget stays**
  (the wake fires at page load, well before the user submits; 92s boot + margin fits).
- `LoginView.vue` wires `wakePing: pingWake` unconditionally (the service no-ops
  without a wake origin).

All 8 existing `useColdStartLogin` unit tests remain valid.

### 4. nginx proxy-timeout hardening — `frontend/docker-entrypoint.sh`

External-HTTPS proxy block: `proxy_connect_timeout` / `proxy_send_timeout` /
`proxy_read_timeout` 60s → **120s**, covering proxied requests that land mid-boot.
(The internal-Docker branch keeps its current values.)

## Explicitly out of scope

- Flipping the SPA to direct API calls (baking `VITE_API_URL`) — larger blast radius,
  depends on the build-arg path that already failed silently.
- Keep-warm pingers / paid tier — unnecessary once the wake actually triggers.
- Backend changes of any kind (CORS and health routes already suffice).

## Error handling

- No wake origin (local/docker/e2e): identical behavior to today.
- Direct fetch fails (network flake, CSP misconfig): swallowed; the login retry loop
  and its `waking` classification still function exactly as they do now — the fix is
  purely additive, there is no new failure mode that blocks login.
- Backend already awake: `wakeBackend()` resolves in ~1s; no-op in effect.

## Testing & verification

**Unit (Vitest):** `backendWake.ts` (meta present/absent; ok/failed fetch; abort on
timeout), `warmUpBackend` branch selection, `useColdStartLogin` invokes `wakePing` on
each waking iteration and never when absent.

**Shell:** entrypoint assertions in the `tooling-tests` pattern (PR #109) where it fits —
https branch injects meta tag + CSP origin + 120s timeouts; internal/no-backend branches
inject nothing.

**Gates:** existing frontend lint/tests/coverage, i18n gates (no new strings), a11y/CSP
gates, e2e-sqlite (unchanged behavior — internal branch).

**Live (decisive):** after merge + Render deploy, let the backend hibernate (15+ min
idle), then from an external browser load the login page and verify via Render MCP logs:
backend boot logs appear within seconds of page load (wake triggered by the page, not by
a manual curl); banner counts up; auto-login completes in ~90–120s. Confirm served HTML
contains the meta tag and the CSP header includes the API origin.

## Success criteria

1. Loading the login page from an external IP triggers a backend cold boot within
   seconds (observable in Render logs) — even when proxied requests are being 429'd.
2. Cold-start login auto-completes within the existing 180s budget.
3. No behavior change in local dev, docker-compose, or `e2e-sqlite`.
4. All CI gates green; no new i18n keys; coverage thresholds hold.
