# Cold-Start Login Recovery — Robustness Fix

**Date:** 2026-06-28
**Status:** Design approved → spec for implementation
**Scope:** Frontend only (`kpi-operations-frontend`). No backend changes.

## Problem

Testers on the Render free-tier demo (`kpi-operations-frontend.onrender.com`) cannot log
in during a backend cold start. The login spinner hangs for a long time, then surfaces
*"The demo server is still starting up. Please wait a few more seconds and try again."*
even though the backend comes up cleanly moments later.

### Evidence (gathered live, 2026-06-28)

The backend is **healthy**. Render app logs for `srv-d6eg4f41hm7c73f4iqk0` show a clean
cold boot:

- `Auto-seeding complete` at `18:46:00.648` — the DEMO_MODE seed finishes **before** the
  health check passes.
- `Application startup complete` at `18:46:00.657`; Uvicorn listening at `18:46:00.659`.
- `POST /api/auth/login … 200 OK time=1494ms`, `LOGIN_SUCCESS user=USER-ADMIN` at
  `18:46:24` — once up, login works and is fast.

A direct probe reproduced the cold start: `GET /health/live` **hung for 91 seconds**
before returning `200` (Render holds the wake-triggering connection open rather than
fast-failing). A warm login returns `200` in ~1.7s.

So nothing is broken server-side. The cold start to a fully-working backend is ~90s
(nominal) but **variable**.

### Root cause (frontend cold-start recovery is too fragile)

1. **No request timeout.** The shared axios client (`frontend/src/services/api/client.ts`)
   sets no `timeout`, so axios waits forever. During a wake Render holds the connection
   open (reproduced: a 91s hang), so a single login attempt can block indefinitely with no
   deterministic per-attempt bound. This is the "taking too long to fail" symptom.

2. **Retry budget too tight.** The retry loop in `frontend/src/views/LoginView.vue` is
   `MAX_ATTEMPTS = 15 × RETRY_DELAY_MS = 10000` ≈ 150s, of which ~140s is usable. A
   free-tier cold start is nominally ~90s but variable; under a slow/variable boot it can
   exceed the budget, so the loop hits `MAX_ATTEMPTS` and shows the hard error even though
   the backend comes up shortly after.

The failure classifier (`classifyAuthFailure` in `authStore.ts`) is **correct** — no
response / `0` / `429` / `5xx` / `ECONNABORTED` / `ERR_NETWORK` all map to `'waking'`,
and `401` maps to `'invalid'`. The fix does not touch classification; it makes the
recovery loop robust and bounds each attempt.

This work extends the existing cold-start UX from PRs #105–#107.

## Goals

- A tester surviving a typical cold start logs in automatically without ever seeing a
  scary error.
- Recovery tolerates a variable boot up to ~3 minutes before giving up.
- A hung attempt aborts predictably instead of blocking indefinitely.
- A genuine `401` still fails immediately (never masked by the retry loop).
- A real outage still fails in bounded time (~3 min) with a clear message.
- The long wait does not look frozen.

## Non-Goals

- No keep-warm cron / external uptime ping (declined previously; does not fix the in-app
  fragility).
- No global axios timeout (would change behavior of long-running requests app-wide —
  reports, simulation).
- No backend changes.

## Design

### Decisions (locked)

| Parameter | Value | Rationale |
|---|---|---|
| `BUDGET_MS` (total retry budget) | `180_000` (3 min) | Comfortable margin over ~90s nominal boot and most slow boots; still bounded. |
| `ATTEMPT_TIMEOUT_MS` (per login attempt) | `20_000` | Bounds a held-open/hung request so the loop keeps a predictable cadence. |
| `RETRY_DELAY_MS` (between attempts) | `10_000` | Unchanged; backs off from Render's edge throttling (429). |
| Live progress | elapsed seconds, 1s ticker | Reassures testers during a 90s+ wait. |

### 1. Per-attempt timeout, scoped to login

`frontend/src/services/api/auth.ts`:

```ts
export const login = (credentials: LoginCredentials, timeoutMs?: number) =>
  api.post('/auth/login', credentials, timeoutMs ? { timeout: timeoutMs } : undefined)
```

Axios aborts a hung attempt at `timeoutMs`, throwing `ECONNABORTED`, which the existing
classifier already maps to `'waking'`. The `timeout` is passed **only** when provided, so
every other call site (and `login` without the argument) is unchanged. No global default
timeout — blast radius is limited to the login retry loop.

`frontend/src/stores/authStore.ts`:

```ts
async login(credentials: LoginCredentials, timeoutMs?: number): Promise<ActionResult> {
  // ...
  const response = await api.login(credentials, timeoutMs)
  // ... unchanged success/catch/classify logic
}
```

### 2. Wall-clock retry budget in `LoginView.vue`

Replace the fixed-attempt loop with a wall-clock budget:

```ts
const BUDGET_MS = 180_000
const ATTEMPT_TIMEOUT_MS = 20_000
const RETRY_DELAY_MS = 10_000

const start = Date.now()
do {
  const result = await authStore.login(
    { username: username.value, password: password.value },
    ATTEMPT_TIMEOUT_MS,
  )

  if (result.success) {
    // stop ticker, redirect by role (unchanged map)
    return
  }

  if (result.code === 'waking' && Date.now() - start < BUDGET_MS) {
    wakingUp.value = true            // starts the elapsed ticker
    await delay(RETRY_DELAY_MS)
    continue
  }

  // Genuine failure (401 / other) OR budget exhausted while still 'waking'.
  // stop ticker
  errorMessage.value =
    result.code === 'waking' ? t('auth.serverStillStarting') : (result.error || t('auth.loginFailed'))
  return
} while (Date.now() - start < BUDGET_MS)
```

Key behaviors preserved:
- A `401` → `code === 'invalid'` → falls straight to the error branch on the first
  attempt; the retry guard only continues on `code === 'waking'`. A real bad password is
  never masked.
- Budget is checked **before** waiting again, so the loop never sleeps past the budget.

### 3. Live progress indicator

- New ref `wakingElapsedSec` (number, seconds since the wait began).
- A 1-second `setInterval` ticker starts when `wakingUp` first flips `true` and is cleared
  on success, on failure, and in `onUnmounted` (no leaked interval).
- The existing banner (`LoginView.vue`) shows `$t('auth.serverWaking')` next to a
  `<v-progress-circular indeterminate>`. The elapsed seconds must be rendered through an
  **interpolated i18n key** — the `@intlify/vue-i18n/no-raw-text` gate rejects a bare
  `"{{ n }}s"` literal in the template.
- Add a new key `auth.serverWakingElapsed` with a `{seconds}` parameter in **both** `en`
  and `es` locales (the repo's `referenced-keys` gate requires every key to resolve in
  both locales), e.g.
  `"The demo server is waking up (free hosting)… {seconds}s. We'll sign you in automatically once it's ready."`
  Render `auth.serverWaking` for the first ~tick, then switch to
  `$t('auth.serverWakingElapsed', { seconds: wakingElapsedSec })`, or render
  `serverWakingElapsed` from the start with `seconds` initialised to `0`. The exact key
  shape (one combined key vs. base key + a separate `{seconds}s` suffix key) is finalised
  in the implementation plan; either must keep both locales in sync and use no raw text.

### Error handling summary

| Condition | Classified | Loop behavior | User sees |
|---|---|---|---|
| Cold start (429 / 5xx / no response / timeout) | `waking` | retry within 180s | waking banner + live counter, then auto-login |
| Wrong credentials (401) | `invalid` | break immediately | login-failed error |
| Other 4xx / app error | `error` | break immediately | error detail / generic |
| Backend down for >180s | `waking` | exhaust budget | `serverStillStarting` |

## Testing

- **`authStore.spec.ts`** — `login` forwards `timeoutMs` to `api.login` as
  `{ timeout }`; omitted when not passed; classifier mapping unchanged (`ECONNABORTED` →
  `waking`).
- **`LoginView` tests** (fake timers):
  - Retries on `'waking'` and succeeds on a later attempt within budget → redirects.
  - Stops and shows `serverStillStarting` after the budget elapses while still `'waking'`.
  - Breaks immediately and shows the credentials error on `401` (no retry).
  - Ticker interval is cleared on unmount (no leaked timer).
- **Manual** — after merge, verify against the live Render cold start (hibernate the
  service, then log in) per the local==GitHub==Render convention.

## Rollout

Standard disciplined cycle: spec → plan → implement via PR → `npm run test` +
`npm run lint` green → `/cross-review` (DeepSeek adversarial pass) → `/code-review` →
merge on green → verify on Render. Frontend coverage thresholds (32/25/25/34) must hold.
