# Cold-Start Browser-Direct Backend Wake — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the visitor's browser wake the hibernated Render backend directly (proxied requests are 429'd by Render's edge and never trigger the wake), so cold-start login completes inside the existing 180s budget.

**Architecture:** The nginx entrypoint (which already receives `BACKEND_URL` at runtime) injects a `<meta name="backend-wake-origin">` tag into `index.html` in its external-HTTPS branch only, and appends that origin to the CSP `connect-src`. A new pure service `backendWake.ts` reads the tag and fires direct `GET /health/live` requests (held-open wake on page load, short-timeout re-pings during the retry loop). `authStore.warmUpBackend()` and `useColdStartLogin` consume it. nginx proxy timeouts go 60s→120s.

**Tech Stack:** Vue 3 + Pinia + Vitest (happy-dom), POSIX sh entrypoint tested via `tests/scripts/*.sh` (tooling-tests CI job).

**Spec:** `docs/superpowers/specs/2026-07-02-cold-start-direct-wake-design.md`

**Branch:** `fix/cold-start-direct-wake` (already exists, carries the spec commit).

## Global Constraints

- Frontend-only; NO backend code changes, NO Render dashboard changes, NO new env vars required at deploy time.
- No new i18n strings (i18n gates must stay green); no new user-facing copy.
- Permissive assertions forbidden — each test asserts ONE expected value.
- Local dev / docker-compose / e2e-sqlite behavior must be byte-identical except for the entrypoint's testability env overrides (defaults preserve current paths).
- Coverage thresholds 32/25/25/34 must hold (`npm run test` from `frontend/`).
- All fetches in `backendWake.ts` are best-effort: they must NEVER throw to callers.
- Existing 8 `useColdStartLogin` tests must pass unmodified; existing `warmUpBackend` tests must pass unmodified (they run without a meta tag → fallback branch).

---

### Task 1: `backendWake.ts` service

**Files:**
- Create: `frontend/src/services/backendWake.ts`
- Test: `frontend/src/services/__tests__/backendWake.spec.ts`

**Interfaces:**
- Consumes: nothing (reads `document` + `fetch`).
- Produces (used by Tasks 2 & 4):
  - `getWakeOrigin(): string | null`
  - `wakeBackend(): Promise<void>` — no-timeout held-open wake, no-ops without origin
  - `pingWake(timeoutMs?: number): Promise<void>` — aborts after `timeoutMs` (default 12000), no-ops without origin

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/services/__tests__/backendWake.spec.ts
import { describe, it, expect, vi, afterEach } from 'vitest'
import { getWakeOrigin, wakeBackend, pingWake } from '@/services/backendWake'

const setMeta = (content: string) => {
  const m = document.createElement('meta')
  m.setAttribute('name', 'backend-wake-origin')
  m.setAttribute('content', content)
  document.head.appendChild(m)
}

afterEach(() => {
  document.querySelector('meta[name="backend-wake-origin"]')?.remove()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('backendWake', () => {
  it('getWakeOrigin returns null when the meta tag is absent', () => {
    expect(getWakeOrigin()).toBeNull()
  })

  it('getWakeOrigin returns the origin with trailing slashes stripped', () => {
    setMeta('https://kpi-operations-api.onrender.com/')
    expect(getWakeOrigin()).toBe('https://kpi-operations-api.onrender.com')
  })

  it('wakeBackend no-ops (no fetch) when no wake origin is configured', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)
    await wakeBackend()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('wakeBackend fetches <origin>/health/live in cors mode', async () => {
    setMeta('https://kpi-operations-api.onrender.com')
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)
    await wakeBackend()
    expect(String(fetchSpy.mock.calls[0]?.[0])).toBe('https://kpi-operations-api.onrender.com/health/live')
    expect((fetchSpy.mock.calls[0]?.[1] as RequestInit).mode).toBe('cors')
  })

  it('wakeBackend never throws when the fetch rejects', async () => {
    setMeta('https://kpi-operations-api.onrender.com')
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('backend asleep'))
    await expect(wakeBackend()).resolves.toBeUndefined()
  })

  it('pingWake no-ops (no fetch) when no wake origin is configured', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)
    await pingWake()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('pingWake aborts the request after timeoutMs and resolves without throwing', async () => {
    vi.useFakeTimers()
    setMeta('https://kpi-operations-api.onrender.com')
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          )
        }) as Promise<Response>,
    )
    const done = pingWake(12000)
    await vi.advanceTimersByTimeAsync(12000)
    await expect(done).resolves.toBeUndefined()
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/services/__tests__/backendWake.spec.ts`
Expected: FAIL — cannot resolve `@/services/backendWake`.

- [ ] **Step 3: Write the implementation**

```typescript
// frontend/src/services/backendWake.ts
// Direct backend wake for free-tier hosting (Render hibernation).
//
// Requests proxied through this frontend's nginx originate from the host's
// shared egress IPs, which Render's edge answers with 429
// (x-render-routing: hibernate-rate-limited) WITHOUT triggering a wake — the
// backend can sleep through an entire login session (verified live 2026-07-02;
// see docs/superpowers/specs/2026-07-02-cold-start-direct-wake-design.md).
// Only a request from the visitor's own browser reliably wakes it (~90-100s,
// held open by the edge until the app is up).
//
// The wake origin is injected at container start as
// <meta name="backend-wake-origin"> (frontend/docker-entrypoint.sh, external
// HTTPS branch only). Locally / in docker-compose the tag is absent and every
// function here no-ops. All requests are best-effort and never throw: cors
// mode is used because the backend's CORS_ORIGINS already allows this origin.

export function getWakeOrigin(): string | null {
  const content = document
    .querySelector('meta[name="backend-wake-origin"]')
    ?.getAttribute('content')
    ?.trim()
  return content ? content.replace(/\/+$/, '') : null
}

// Held-open wake: no timeout on purpose — the hosting edge holds the request
// for the full cold boot, so resolution doubles as the "server is up" signal.
export async function wakeBackend(): Promise<void> {
  const origin = getWakeOrigin()
  if (!origin) return
  try {
    await fetch(`${origin}/health/live`, { method: 'GET', mode: 'cors' })
  } catch {
    /* best-effort — a failed wake ping must never surface to the caller */
  }
}

// Short-timeout re-ping for the login retry loop: a redundant wake trigger in
// case the held-open request was dropped (e.g. flaky mobile network).
export async function pingWake(timeoutMs = 12000): Promise<void> {
  const origin = getWakeOrigin()
  if (!origin) return
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    await fetch(`${origin}/health/live`, { method: 'GET', mode: 'cors', signal: controller.signal })
  } catch {
    /* best-effort */
  } finally {
    clearTimeout(timer)
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/services/__tests__/backendWake.spec.ts`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/backendWake.ts frontend/src/services/__tests__/backendWake.spec.ts
git commit -m "feat(login): backendWake service for direct free-tier wake pings"
```

---

### Task 2: `authStore.warmUpBackend()` direct-wake branch

**Files:**
- Modify: `frontend/src/stores/authStore.ts` (the `warmUpBackend` action and its comment block, lines ~132–152)
- Test: `frontend/src/stores/__tests__/authStore.spec.ts` (add to the existing `warmUpBackend` group, after line ~271)

**Interfaces:**
- Consumes: `getWakeOrigin()`, `wakeBackend()` from Task 1.
- Produces: `warmUpBackend(): Promise<void>` (signature unchanged; `LoginView` already calls it on mount).

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/stores/__tests__/authStore.spec.ts` next to the two existing `warmUpBackend` tests (which must keep passing unmodified — they run without a meta tag and therefore exercise the fallback branch):

```typescript
    // With a backend-wake-origin meta tag (injected by the nginx entrypoint on
    // free-tier hosting), the warm-up MUST go DIRECTLY to the backend origin:
    // proxied pings originate from the host's shared egress IPs, which the
    // hosting edge 429s without waking the backend.
    it('warmUpBackend pings the backend origin directly when a wake origin is injected', async () => {
      const meta = document.createElement('meta')
      meta.setAttribute('name', 'backend-wake-origin')
      meta.setAttribute('content', 'https://kpi-operations-api.onrender.com')
      document.head.appendChild(meta)
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)

      const store = useAuthStore()
      await store.warmUpBackend()

      expect(String(fetchSpy.mock.calls[0]?.[0])).toBe('https://kpi-operations-api.onrender.com/health/live')

      fetchSpy.mockRestore()
      meta.remove()
    })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/stores/__tests__/authStore.spec.ts -t "wake origin is injected"`
Expected: FAIL — fetch was called with `/api/v1/health/live` (fallback path), not the direct origin.

- [ ] **Step 3: Implement the branch + fix stale comments**

In `frontend/src/stores/authStore.ts`, add the import at the top with the other imports:

```typescript
import { getWakeOrigin, wakeBackend } from '@/services/backendWake'
```

Replace the entire `warmUpBackend` action (current comment block + method) with:

```typescript
    // Best-effort backend warm-up as the login page mounts, so a sleeping
    // free-tier API starts booting while the user reads and types (a cold
    // start is ~90-100s, so the head start matters).
    //
    // Two paths:
    // - Wake origin injected (free-tier deploy, see frontend/docker-entrypoint.sh):
    //   ping the backend origin DIRECTLY from the browser. Proxied pings
    //   originate from the host's shared egress IPs, which the hosting edge
    //   429s (hibernate-rate-limited) WITHOUT triggering the wake — the direct
    //   path is the only one that reliably wakes the backend.
    // - No wake origin (local dev / docker-compose): keep the same-origin ping
    //   under the /api proxy as a harmless reachability best-effort. NOTE the
    //   backend's real health route is /health/live (no /api prefix) — the
    //   proxied path 404s once the app is up, which is fine for a wake signal
    //   but do not rely on it returning 200.
    //
    // Bare fetch (NOT the api client) on purpose — the shared axios client runs
    // a 401 interceptor that redirects to /login and would loop the page.
    async warmUpBackend(): Promise<void> {
      if (getWakeOrigin()) {
        await wakeBackend()
        return
      }
      const base = (import.meta.env.VITE_API_URL as string | undefined) || '/api/v1'
      try {
        await fetch(`${base}/health/live`, { method: 'GET', mode: 'no-cors' })
      } catch {
        /* best-effort — a sleeping or unreachable backend just stays unwarmed */
      }
    },
```

- [ ] **Step 4: Run the full store suite to verify all pass (including the 2 pre-existing warm-up tests)**

Run: `cd frontend && npx vitest run src/stores/__tests__/authStore.spec.ts`
Expected: all pass, 1 new test added.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/authStore.ts frontend/src/stores/__tests__/authStore.spec.ts
git commit -m "feat(login): warmUpBackend wakes the backend directly when a wake origin is injected"
```

---

### Task 3: `useColdStartLogin` optional `wakePing` hook

**Files:**
- Modify: `frontend/src/composables/useColdStartLogin.ts`
- Test: `frontend/src/composables/__tests__/useColdStartLogin.spec.ts` (append; the 8 existing tests must pass unmodified)

**Interfaces:**
- Consumes: nothing new (hook is injected by the caller).
- Produces: `ColdStartLoginOptions.wakePing?: () => void` — invoked fire-and-forget once per `waking` retry iteration, exceptions swallowed.

- [ ] **Step 1: Write the failing tests**

Append inside the existing `describe('useColdStartLogin', ...)` block:

```typescript
  it('fires wakePing once per waking retry and survives a throwing hook', async () => {
    const wakePing = vi.fn(() => {
      throw new Error('boom')
    })
    const loginFn = vi
      .fn()
      .mockResolvedValueOnce({ success: false, code: 'waking' })
      .mockResolvedValueOnce({ success: false, code: 'waking' })
      .mockResolvedValueOnce({ success: true })
    const { run } = useColdStartLogin(loginFn, { ...OPTS, wakePing })

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(10000)
    await vi.advanceTimersByTimeAsync(10000)
    const result = await done

    expect(result).toEqual({ success: true })
    expect(wakePing).toHaveBeenCalledTimes(2)
  })

  it('does not fire wakePing when login succeeds immediately', async () => {
    const wakePing = vi.fn()
    const loginFn = vi.fn().mockResolvedValue({ success: true })
    const { run } = useColdStartLogin(loginFn, { ...OPTS, wakePing })

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0)
    await done

    expect(wakePing).not.toHaveBeenCalled()
  })

  it('does not fire wakePing on invalid credentials', async () => {
    const wakePing = vi.fn()
    const loginFn = vi.fn().mockResolvedValue({ success: false, code: 'invalid' })
    const { run } = useColdStartLogin(loginFn, { ...OPTS, wakePing })

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0)
    const result = await done

    expect(result.code).toBe('invalid')
    expect(wakePing).not.toHaveBeenCalled()
  })
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd frontend && npx vitest run src/composables/__tests__/useColdStartLogin.spec.ts`
Expected: 8 pass, 1 FAILS (`wakePing` never called — option not implemented; the two "not called" tests pass vacuously, that's expected).

- [ ] **Step 3: Implement the hook**

In `frontend/src/composables/useColdStartLogin.ts`:

Add to the options interface:

```typescript
export interface ColdStartLoginOptions {
  budgetMs?: number
  attemptTimeoutMs?: number
  retryDelayMs?: number
  // Fire-and-forget re-wake ping (e.g. a direct backend /health/live request on
  // free-tier hosting), fired once per waking retry. Exceptions are swallowed.
  wakePing?: () => void
}
```

Inside `useColdStartLogin`, after the existing option defaults:

```typescript
  const wakePing = options.wakePing
```

In `run()`, inside the `waking` branch, immediately after `startTicker()`:

```typescript
      if (result.code === 'waking' && Date.now() - start < budgetMs) {
        wakingUp.value = true
        startTicker()
        try {
          wakePing?.()
        } catch {
          /* best-effort re-wake ping — must never break the retry loop */
        }
        await new Promise((resolve) => setTimeout(resolve, retryDelayMs))
```

(No other lines in the branch change.)

- [ ] **Step 4: Run the full composable suite**

Run: `cd frontend && npx vitest run src/composables/__tests__/useColdStartLogin.spec.ts`
Expected: 11 passed (8 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useColdStartLogin.ts frontend/src/composables/__tests__/useColdStartLogin.spec.ts
git commit -m "feat(login): optional wakePing hook fired on each cold-start retry"
```

---

### Task 4: Wire `pingWake` into `LoginView`

**Files:**
- Modify: `frontend/src/views/LoginView.vue` (script setup, ~line 230 imports and ~line 237 composable call)

**Interfaces:**
- Consumes: `pingWake` (Task 1), `wakePing` option (Task 3).
- Produces: nothing new.

- [ ] **Step 1: Make the edit**

Add the import next to the `useColdStartLogin` import:

```typescript
import { pingWake } from '@/services/backendWake'
```

Change the composable call (currently a single-argument call) to pass the hook — `pingWake` no-ops without a wake origin, so this is wired unconditionally:

```typescript
const {
  wakingUp,
  wakingElapsedSec,
  run: runColdStartLogin,
  cancel: stopWakingTicker,
} = useColdStartLogin((credentials, timeoutMs) => authStore.login(credentials, timeoutMs), {
  wakePing: () => {
    void pingWake()
  },
})
```

- [ ] **Step 2: Verify with lint + typecheck + the view's existing tests**

Run: `cd frontend && npm run lint && npm run typecheck && npx vitest run src/views/__tests__/misc-views.spec.ts`
Expected: all clean/passing (behavioral coverage lives in the Task 1–3 unit tests; `<script setup>` internals are not reachable via VTU — repo convention).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "feat(login): wire direct wake re-ping into the cold-start retry loop"
```

---

### Task 5: Entrypoint — wake-origin injection, CSP append, 120s proxy timeouts + shell test

**Files:**
- Modify: `frontend/docker-entrypoint.sh`
- Test: `tests/scripts/test_frontend_entrypoint.sh` (picked up automatically by the `tooling-tests` CI job, which globs `tests/scripts/*.sh`)

**Interfaces:**
- Consumes: `BACKEND_URL`, `CSP_CONNECT_EXTRA` (existing runtime env vars — both already set on the live service).
- Produces: `<meta name="backend-wake-origin" content="https://<BACKEND_HOST>">` in `index.html` (read by Task 1's `getWakeOrigin()`); testability env overrides `ENTRYPOINT_CONF`, `ENTRYPOINT_UPSTREAM`, `ENTRYPOINT_INDEX_HTML`, `ENTRYPOINT_SKIP_NGINX` (defaults preserve production paths/behavior exactly).

- [ ] **Step 1: Write the failing shell test**

```bash
#!/usr/bin/env bash
# Unit test for frontend/docker-entrypoint.sh: wake-origin meta injection,
# CSP connect-src append, and proxy timeouts, per BACKEND_URL branch.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENTRYPOINT="$SCRIPT_DIR/frontend/docker-entrypoint.sh"
fail=0
assert() { if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

# The entrypoint uses `sed -i` (GNU/busybox form); macOS BSD sed differs — skip there.
if ! sed --version >/dev/null 2>&1; then echo "SKIP: requires GNU sed"; exit 0; fi

setup() {
  TMP="$(mktemp -d)"
  echo 'connect-src self CSP_CONNECT_EXTRA_PLACEHOLDER;' > "$TMP/default.conf"
  printf '<html><head><title>x</title></head><body></body></html>' > "$TMP/index.html"
}
run_entrypoint() {
  ENTRYPOINT_CONF="$TMP/default.conf" ENTRYPOINT_UPSTREAM="$TMP/upstream.inc" \
  ENTRYPOINT_INDEX_HTML="$TMP/index.html" ENTRYPOINT_SKIP_NGINX=1 \
  BACKEND_URL="${1-}" CSP_CONNECT_EXTRA="${2-}" sh "$ENTRYPOINT"
}

# --- external HTTPS branch ---
setup; run_entrypoint "https://kpi-operations-api.onrender.com" ""
grep -q '<meta name="backend-wake-origin" content="https://kpi-operations-api.onrender.com">' "$TMP/index.html"
assert "https: wake-origin meta tag injected" $?
grep -q 'proxy_read_timeout 120s' "$TMP/upstream.inc"; assert "https: proxy_read_timeout 120s" $?
grep -q 'proxy_connect_timeout 120s' "$TMP/upstream.inc"; assert "https: proxy_connect_timeout 120s" $?
grep -q 'connect-src self https://kpi-operations-api.onrender.com;' "$TMP/default.conf"
assert "https: CSP gains backend origin without CSP_CONNECT_EXTRA" $?
rm -rf "$TMP"

# --- external HTTPS branch with CSP_CONNECT_EXTRA preset keeps both origins ---
setup; run_entrypoint "https://kpi-operations-api.onrender.com" "https://other.example.com"
grep -q 'connect-src self https://other.example.com https://kpi-operations-api.onrender.com;' "$TMP/default.conf"
assert "https: preset CSP_CONNECT_EXTRA preserved alongside backend origin" $?
rm -rf "$TMP"

# --- internal Docker branch: no meta tag, no CSP origin, timeouts unchanged ---
setup; run_entrypoint "http://backend:8000" ""
grep -q 'backend-wake-origin' "$TMP/index.html"; [ $? -ne 0 ]; assert "internal: no meta tag" $?
grep -q 'proxy_read_timeout 60s' "$TMP/upstream.inc"; assert "internal: 60s timeout kept" $?
grep -q 'CSP_CONNECT_EXTRA_PLACEHOLDER' "$TMP/default.conf"; [ $? -ne 0 ]; assert "internal: placeholder removed" $?
rm -rf "$TMP"

# --- no-backend branch: empty upstream, untouched index.html ---
setup; run_entrypoint "" ""
[ -s "$TMP/upstream.inc" ]; [ $? -ne 0 ]; assert "empty: upstream.inc empty" $?
grep -q 'backend-wake-origin' "$TMP/index.html"; [ $? -ne 0 ]; assert "empty: no meta tag" $?
rm -rf "$TMP"

exit $fail
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/scripts/test_frontend_entrypoint.sh`
Expected: FAILs — the entrypoint ignores the `ENTRYPOINT_*` overrides (writes to `/etc/nginx/...`, permission error or wrong-path assertions) and injects no meta tag.

- [ ] **Step 3: Modify the entrypoint**

Apply these changes to `frontend/docker-entrypoint.sh` (everything not shown stays as-is):

Replace the fixed paths at the top:

```sh
#!/bin/sh
set -e

# ENTRYPOINT_* overrides exist for the shell unit test
# (tests/scripts/test_frontend_entrypoint.sh); production uses the defaults.
CONF="${ENTRYPOINT_CONF:-/etc/nginx/conf.d/default.conf}"
UPSTREAM="${ENTRYPOINT_UPSTREAM:-/etc/nginx/conf.d/upstream.inc}"
INDEX_HTML="${ENTRYPOINT_INDEX_HTML:-/usr/share/nginx/html/index.html}"
```

In the external-HTTPS branch: change the three `proxy_*_timeout` lines from `60s` to `120s` (a Render cold boot is ~92s; 60s cut proxied requests off mid-boot), and append after the heredoc, still inside the `elif`:

```sh
  # Free-tier hibernation wake (spec: 2026-07-02-cold-start-direct-wake-design.md):
  # requests proxied from this container originate from the host's shared egress
  # IPs, which the hosting edge 429s (hibernate-rate-limited) WITHOUT waking the
  # backend. Expose the backend origin to the SPA so the VISITOR'S browser sends
  # the wake request directly — that path reliably wakes it in ~90-100s.
  if [ -f "$INDEX_HTML" ]; then
    sed -i "s|</head>|<meta name=\"backend-wake-origin\" content=\"https://$BACKEND_HOST\"></head>|" "$INDEX_HTML"
  fi
  # The direct wake fetch needs the backend origin in CSP connect-src even when
  # CSP_CONNECT_EXTRA is not configured (duplicates are harmless in a CSP list).
  CSP_CONNECT_EXTRA="${CSP_CONNECT_EXTRA:+$CSP_CONNECT_EXTRA }https://$BACKEND_HOST"
```

Replace the final `exec` line with:

```sh
# Test hook: the shell unit test can't exec a real nginx.
if [ "${ENTRYPOINT_SKIP_NGINX:-0}" = "1" ]; then
  exit 0
fi

exec nginx -g 'daemon off;'
```

(The `--- CSP connect-src handling ---` block already reads `$CSP_CONNECT_EXTRA` and `$CONF`, so it picks the appended origin up unchanged.)

- [ ] **Step 4: Run the shell test to verify it passes**

Run: `bash tests/scripts/test_frontend_entrypoint.sh`
Expected: 10 PASS lines, exit 0. (On macOS it prints `SKIP: requires GNU sed` — run it in CI or a Linux container for the real check.)

- [ ] **Step 5: Commit**

```bash
git add frontend/docker-entrypoint.sh tests/scripts/test_frontend_entrypoint.sh
git commit -m "feat(deploy): inject backend wake origin + CSP at container start; 120s proxy timeouts"
```

---

### Task 6: Full gates + PR

**Files:** none new.

- [ ] **Step 1: Full frontend suite + gates**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test`
Expected: lint clean, typecheck clean, all tests pass, coverage ≥ 32/25/25/34.

- [ ] **Step 2: All shell tooling tests**

Run: `for t in tests/scripts/*.sh; do bash "$t" || echo "FAILED: $t"; done`
Expected: no `FAILED:` lines (macOS: entrypoint test prints SKIP; CI runs it for real).

- [ ] **Step 3: Push branch, cross-review, PR**

```bash
git push -u origin fix/cold-start-direct-wake
```

Then run `/cross-review` (writes the HEAD marker the PR gate requires) and `/code-review`, then create the PR:

```bash
gh pr create --title "fix(login): browser-direct backend wake for Render cold-start" \
  --body "$(cat <<'EOF'
## Problem
Proxied requests originate from Render's shared egress IPs, which the edge 429s
(hibernate-rate-limited) WITHOUT triggering the wake — the backend can sleep through
an entire login session (tester session 2026-06-29: 7+ min of 429s, zero boot logs).

## Fix (spec: docs/superpowers/specs/2026-07-02-cold-start-direct-wake-design.md)
- nginx entrypoint injects <meta name="backend-wake-origin"> + CSP connect-src origin
  (external-HTTPS branch only; local/docker-compose byte-identical)
- backendWake.ts: held-open direct GET /health/live on page load + short-timeout
  re-pings each cold-start retry
- nginx proxy timeouts 60s -> 120s (cold boot is ~92s)

## Verification
- 10-assert shell test for the entrypoint (tooling-tests job)
- 11 composable + 3 store + 7 service unit tests
- Post-merge live check: page load must trigger backend boot within seconds
  (Render logs), auto-login within the 180s budget

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Post-merge live verification (after user merges on green)**

1. Wait for the Render deploy of `main` to go live, then let both services idle 15+ min (hibernate).
2. From an external browser (or headless), load `https://kpi-operations-frontend.onrender.com/login`.
3. Via Render MCP: backend app logs must show the boot sequence starting within seconds of the page load (wake triggered by the page, no manual curl).
4. Login auto-completes within ~90–120s; banner counts; no "still starting" error.
5. `curl -s https://kpi-operations-frontend.onrender.com/ | grep backend-wake-origin` shows the meta tag; the CSP response header contains the API origin.
