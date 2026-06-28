# Cold-Start Login Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Render free-tier cold-start login recovery robust — bound each login attempt with a timeout, retry on a 3-minute wall-clock budget, and show a live elapsed counter — so testers log in automatically instead of seeing a premature "still starting up" error.

**Architecture:** Frontend-only. (1) Thread an optional per-request `timeout` through `api.login` → `authStore.login` (scoped to login; no global axios timeout). (2) Extract the retry loop + elapsed ticker into a pure composable `useColdStartLogin` so the real recovery logic is unit-testable with fake timers (LoginView is `<script setup>`, whose internals are not reachable via Vue Test Utils `wrapper.vm`). (3) `LoginView` becomes a thin consumer and renders the live counter through the existing `auth.serverWaking` i18n message (now parameterised with `{seconds}`).

**Tech Stack:** Vue 3.5 (`<script setup>` LoginView is plain JS; composable is TS), Pinia (authStore, TS), axios, vue-i18n, Vitest + @vue/test-utils 2.4.6.

## Global Constraints

- No backend changes; no changes to `classifyAuthFailure` (its mapping is already correct).
- No global axios `timeout` on `client.ts` — the timeout is passed **only** on the login retry call.
- A `401` (`code === 'invalid'`) must still fail immediately; the retry guard continues **only** on `code === 'waking'`.
- i18n: en and es must define exactly the same key set (`locale-parity.spec.ts`); every `t()/$t()` literal key must exist in both locales (`referenced-keys.spec.ts`). No raw text in templates (`@intlify/vue-i18n/no-raw-text`).
- Frontend coverage thresholds must hold: statements 32 / branches 25 / functions 25 / lines 34.
- Verify with the repo workflow from `frontend/`: `npm run test`, `npm run lint`.
- Locked parameters (composable defaults): `BUDGET_MS = 180_000`, `ATTEMPT_TIMEOUT_MS = 20_000`, `RETRY_DELAY_MS = 10_000`.

---

## File Structure

- `frontend/src/services/api/auth.ts` — add optional `timeoutMs` param to `login`.
- `frontend/src/stores/authStore.ts` — add optional `timeoutMs` param to the `login` action; forward to `api.login`.
- `frontend/src/stores/__tests__/authStore.spec.ts` — assert timeout is forwarded / omitted.
- `frontend/src/composables/useColdStartLogin.ts` — **new.** Pure retry-loop + elapsed-ticker composable.
- `frontend/src/composables/__tests__/useColdStartLogin.spec.ts` — **new.** Unit tests (fake timers).
- `frontend/src/i18n/locales/en.json` + `es.json` — parameterise `auth.serverWaking` with `{seconds}`.
- `frontend/src/views/LoginView.vue` — consume the composable; bind elapsed seconds; wire `onUnmounted(stopTicker)`.

---

## Task 1: Thread a per-attempt timeout through `api.login` → `authStore.login`

**Files:**
- Modify: `frontend/src/services/api/auth.ts:17`
- Modify: `frontend/src/stores/authStore.ts:108-130`
- Test: `frontend/src/stores/__tests__/authStore.spec.ts` (Login Action describe block, ~line 162)

**Interfaces:**
- Produces: `login(credentials: LoginCredentials, timeoutMs?: number)` in `auth.ts` → `api.post('/auth/login', credentials, timeoutMs ? { timeout: timeoutMs } : undefined)`.
- Produces: `authStore.login(credentials: LoginCredentials, timeoutMs?: number): Promise<ActionResult>` — forwards `timeoutMs` to `api.login`; all existing success/catch/classify behavior unchanged.
- Consumed by: Task 2 (`useColdStartLogin` calls `loginFn(creds, ATTEMPT_TIMEOUT_MS)`; `LoginView` passes `authStore.login` as `loginFn`).

- [ ] **Step 1: Write the failing test**

Add these two tests inside the `describe('Login Action', …)` block in `frontend/src/stores/__tests__/authStore.spec.ts`:

```ts
    it('forwards a per-attempt timeout to api.login when provided', async () => {
      const mockResponse = {
        data: { access_token: 't', user: { user_id: 1, role: 'admin' } },
      }
      api.login.mockResolvedValue(mockResponse)

      const store = useAuthStore()
      await store.login({ username: 'admin', password: 'admin123' }, 20000) // pragma: allowlist secret

      expect(api.login).toHaveBeenCalledWith(
        { username: 'admin', password: 'admin123' }, // pragma: allowlist secret
        20000,
      )
    })

    it('calls api.login without a timeout when none is provided', async () => {
      const mockResponse = {
        data: { access_token: 't', user: { user_id: 1, role: 'admin' } },
      }
      api.login.mockResolvedValue(mockResponse)

      const store = useAuthStore()
      await store.login({ username: 'admin', password: 'admin123' }) // pragma: allowlist secret

      expect(api.login).toHaveBeenCalledWith(
        { username: 'admin', password: 'admin123' }, // pragma: allowlist secret
        undefined,
      )
    })
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm run test -- src/stores/__tests__/authStore.spec.ts -t "timeout"`
Expected: FAIL — `api.login` is currently called with one argument, so the `(creds, 20000)` / `(creds, undefined)` assertions mismatch (received call had no second arg).

- [ ] **Step 3: Implement — `auth.ts`**

In `frontend/src/services/api/auth.ts`, replace line 17:

```ts
export const login = (credentials: LoginCredentials, timeoutMs?: number) =>
  api.post('/auth/login', credentials, timeoutMs ? { timeout: timeoutMs } : undefined)
```

- [ ] **Step 4: Implement — `authStore.ts`**

In `frontend/src/stores/authStore.ts`, change the `login` action signature and the `api.login` call (lines 108 and 110):

```ts
    async login(credentials: LoginCredentials, timeoutMs?: number): Promise<ActionResult> {
      try {
        const response = await api.login(credentials, timeoutMs)
```

Leave the rest of the action (token storage, `catch` → `classifyAuthFailure` / `extractErrorDetail`) unchanged.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm run test -- src/stores/__tests__/authStore.spec.ts`
Expected: PASS — both new tests pass and all existing Login Action tests still pass (the new `undefined` second arg does not change axios behavior).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/api/auth.ts frontend/src/stores/authStore.ts frontend/src/stores/__tests__/authStore.spec.ts
git commit -m "feat(auth): thread optional per-attempt timeout through login"
```

---

## Task 2: `useColdStartLogin` composable + unit tests

**Files:**
- Create: `frontend/src/composables/useColdStartLogin.ts`
- Test: `frontend/src/composables/__tests__/useColdStartLogin.spec.ts`

**Interfaces:**
- Consumes: a `loginFn(credentials, timeoutMs?) => Promise<{ success: boolean; code?: string; error?: string }>` (in production this is Task 1's `authStore.login`).
- Produces:
  ```ts
  function useColdStartLogin(
    loginFn: ColdStartLoginFn,
    options?: { budgetMs?: number; attemptTimeoutMs?: number; retryDelayMs?: number },
  ): {
    wakingUp: Ref<boolean>
    wakingElapsedSec: Ref<number>
    run: (credentials: Record<string, unknown>) => Promise<ColdStartLoginResult>
    stopTicker: () => void
  }
  ```
  `run` resolves with the terminal `loginFn` result (success, or the last failure when the budget is exhausted, or an immediate non-`waking` failure). It owns no Vue lifecycle hook — the consumer wires `stopTicker` into `onUnmounted`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/composables/__tests__/useColdStartLogin.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useColdStartLogin } from '@/composables/useColdStartLogin'

const OPTS = { budgetMs: 180000, attemptTimeoutMs: 20000, retryDelayMs: 10000 }
const CREDS = { username: 'admin', password: 'admin123' } // pragma: allowlist secret

describe('useColdStartLogin', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('retries while waking and resolves success within budget', async () => {
    const loginFn = vi
      .fn()
      .mockResolvedValueOnce({ success: false, code: 'waking' })
      .mockResolvedValueOnce({ success: false, code: 'waking' })
      .mockResolvedValueOnce({ success: true })
    const { run, wakingUp } = useColdStartLogin(loginFn, OPTS)

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0) // attempt 1
    await vi.advanceTimersByTimeAsync(10000) // wait + attempt 2
    await vi.advanceTimersByTimeAsync(10000) // wait + attempt 3 (success)
    const result = await done

    expect(result).toEqual({ success: true })
    expect(loginFn).toHaveBeenCalledTimes(3)
    expect(loginFn).toHaveBeenLastCalledWith(CREDS, 20000)
    expect(wakingUp.value).toBe(false)
  })

  it('passes the attempt timeout to loginFn on every attempt', async () => {
    const loginFn = vi.fn().mockResolvedValue({ success: true })
    const { run } = useColdStartLogin(loginFn, OPTS)

    await run(CREDS)

    expect(loginFn).toHaveBeenCalledWith(CREDS, 20000)
  })

  it('returns the waking result after the budget is exhausted', async () => {
    const loginFn = vi.fn().mockResolvedValue({ success: false, code: 'waking' })
    const { run } = useColdStartLogin(loginFn, OPTS)

    const done = run(CREDS)
    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(10000)
    }
    const result = await done

    expect(result.code).toBe('waking')
    expect(result.success).toBe(false)
  })

  it('returns immediately on invalid credentials without retrying', async () => {
    const loginFn = vi
      .fn()
      .mockResolvedValue({ success: false, code: 'invalid', error: 'Bad creds' })
    const { run } = useColdStartLogin(loginFn, OPTS)

    const result = await run(CREDS)

    expect(result).toEqual({ success: false, code: 'invalid', error: 'Bad creds' })
    expect(loginFn).toHaveBeenCalledTimes(1)
  })

  it('advances the elapsed counter while waking and stops it on stopTicker', async () => {
    const loginFn = vi.fn().mockResolvedValue({ success: false, code: 'waking' })
    const { run, wakingElapsedSec, stopTicker } = useColdStartLogin(loginFn, OPTS)

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0) // first attempt → 'waking' starts the ticker
    await vi.advanceTimersByTimeAsync(3000) // 3 one-second ticks
    expect(wakingElapsedSec.value).toBeGreaterThanOrEqual(3)

    stopTicker()
    const before = wakingElapsedSec.value
    await vi.advanceTimersByTimeAsync(3000)
    expect(wakingElapsedSec.value).toBe(before) // no leaked interval

    // let the budget run out so the pending run() resolves and leaves no open timers
    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(10000)
    }
    await done
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test -- src/composables/__tests__/useColdStartLogin.spec.ts`
Expected: FAIL — `Cannot find module '@/composables/useColdStartLogin'` (file does not exist yet).

- [ ] **Step 3: Implement the composable**

Create `frontend/src/composables/useColdStartLogin.ts`:

```ts
import { ref, type Ref } from 'vue'

export interface ColdStartLoginResult {
  success: boolean
  code?: string
  error?: string
  [key: string]: unknown
}

export type ColdStartLoginFn = (
  credentials: Record<string, unknown>,
  timeoutMs?: number,
) => Promise<ColdStartLoginResult>

export interface ColdStartLoginOptions {
  budgetMs?: number
  attemptTimeoutMs?: number
  retryDelayMs?: number
}

// On free hosting the backend sleeps after inactivity; a cold start was measured at ~90s
// (variable) and Render can hold the wake request open. We bound each attempt with a
// timeout so a hung request cannot block the loop, retry on a wall-clock budget that
// comfortably exceeds the cold start, and expose a live elapsed counter so the wait does
// not look frozen — without ever masking a real 401 (only `code === 'waking'` retries).
export function useColdStartLogin(
  loginFn: ColdStartLoginFn,
  options: ColdStartLoginOptions = {},
): {
  wakingUp: Ref<boolean>
  wakingElapsedSec: Ref<number>
  run: (credentials: Record<string, unknown>) => Promise<ColdStartLoginResult>
  stopTicker: () => void
} {
  const budgetMs = options.budgetMs ?? 180000
  const attemptTimeoutMs = options.attemptTimeoutMs ?? 20000
  const retryDelayMs = options.retryDelayMs ?? 10000

  const wakingUp = ref(false)
  const wakingElapsedSec = ref(0)
  let ticker: ReturnType<typeof setInterval> | null = null

  function startTicker(): void {
    if (ticker !== null) return
    wakingElapsedSec.value = 0
    ticker = setInterval(() => {
      wakingElapsedSec.value += 1
    }, 1000)
  }

  function stopTicker(): void {
    if (ticker !== null) {
      clearInterval(ticker)
      ticker = null
    }
  }

  async function run(credentials: Record<string, unknown>): Promise<ColdStartLoginResult> {
    const start = Date.now()
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const result = await loginFn(credentials, attemptTimeoutMs)

      if (result.success) {
        stopTicker()
        wakingUp.value = false
        return result
      }

      if (result.code === 'waking' && Date.now() - start < budgetMs) {
        wakingUp.value = true
        startTicker()
        await new Promise((resolve) => setTimeout(resolve, retryDelayMs))
        continue
      }

      stopTicker()
      wakingUp.value = false
      return result
    }
  }

  return { wakingUp, wakingElapsedSec, run, stopTicker }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test -- src/composables/__tests__/useColdStartLogin.spec.ts`
Expected: PASS — all five cases pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useColdStartLogin.ts frontend/src/composables/__tests__/useColdStartLogin.spec.ts
git commit -m "feat(login): add useColdStartLogin recovery composable"
```

---

## Task 3: Wire `LoginView` to the composable + live elapsed copy

**Files:**
- Modify: `frontend/src/i18n/locales/en.json:212`
- Modify: `frontend/src/i18n/locales/es.json:212`
- Modify: `frontend/src/views/LoginView.vue` (import line 224; template line 51; refs ~line 247; `handleLogin` loop lines 288-332; add `onUnmounted`)

**Interfaces:**
- Consumes: `useColdStartLogin` (Task 2) and `authStore.login` (Task 1).

- [ ] **Step 1: Parameterise the i18n message (both locales)**

In `frontend/src/i18n/locales/en.json`, replace the `serverWaking` line (212):

```json
    "serverWaking": "The demo server is waking up (free hosting)… {seconds}s. We'll sign you in automatically once it's ready.",
```

In `frontend/src/i18n/locales/es.json`, replace the `serverWaking` line (212):

```json
    "serverWaking": "El servidor de demostración se está activando (alojamiento gratuito)… {seconds}s. Iniciaremos tu sesión automáticamente cuando esté listo.",
```

(Key name unchanged → `locale-parity` and `referenced-keys` both stay green.)

- [ ] **Step 2: Wire the composable into the script**

In `frontend/src/views/LoginView.vue`:

(a) Update the Vue import (line 224):

```js
import { ref, reactive, onMounted, onUnmounted } from 'vue'
```

(b) Add the composable import next to the other `@/` imports (after line 229):

```js
import { useColdStartLogin } from '@/composables/useColdStartLogin'
```

(c) After `const authStore = useAuthStore()` (line 234), instantiate the composable and
wire cleanup. `authStore.login` is a Pinia action (already bound), so it can be passed
directly. `stopWakingTicker` is wired into `onUnmounted` to guard an unmount that happens
mid-wait (the composable also calls it whenever `run()` settles):

```js
const {
  wakingUp,
  wakingElapsedSec,
  run: runColdStartLogin,
  stopTicker: stopWakingTicker,
} = useColdStartLogin((credentials, timeoutMs) => authStore.login(credentials, timeoutMs))
onUnmounted(stopWakingTicker)
```

(d) Remove the now-duplicated local declaration `const wakingUp = ref(false)` (line 247) —
`wakingUp` now comes from the composable. Leave `loading`, `errorMessage`, `errors`, etc.
as-is.

- [ ] **Step 3: Replace the retry loop in `handleLogin`**

In `frontend/src/views/LoginView.vue`, replace the existing loop block (the comment +
`const MAX_ATTEMPTS = 15` through the closing `}` of the `for` loop, lines 288-332) with a
thin consumer of the composable:

```js
  const result = await runColdStartLogin({
    username: username.value,
    password: password.value,
  })

  loading.value = false

  if (result.success) {
    // Role-based landing — keep this in sync with the same map in router/index.ts.
    const role = authStore.currentUser?.role
    const landing = {
      operator: '/my-shift',
      leader: '/',
      poweruser: '/capacity-planning',
      admin: '/kpi-dashboard',
    }
    router.push((role && landing[role]) || '/')
    return
  }

  // Genuine failure (wrong credentials / other) or still not up after the 3-min budget.
  errorMessage.value =
    result.code === 'waking' ? t('auth.serverStillStarting') : (result.error || t('auth.loginFailed'))
```

(The `wakingUp.value = false` resets are now handled inside the composable; `loading` is
owned by the view.)

- [ ] **Step 4: Bind elapsed seconds in the banner**

In `frontend/src/views/LoginView.vue`, replace the banner text (line 51):

```html
                  <span>{{ $t('auth.serverWaking', { seconds: wakingElapsedSec }) }}</span>
```

- [ ] **Step 5: Run the i18n + smoke suites**

Run: `npm run test -- src/i18n src/views/__tests__/misc-views.spec.ts`
Expected: PASS — `locale-parity`, `referenced-keys`, `reactive-resolution`, and the
existing `LoginView.vue mounts without errors` smoke test stay green.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/i18n/locales/en.json frontend/src/i18n/locales/es.json
git commit -m "feat(login): consume cold-start composable + live elapsed banner"
```

---

## Task 4: Full verification + lint

**Files:** none (verification only).

- [ ] **Step 1: Run the full frontend test suite with coverage**

Run: `npm run test`
Expected: PASS — full Vitest suite green; coverage stays above 32/25/25/34 (statements/branches/functions/lines).

- [ ] **Step 2: Run lint**

Run: `npm run lint`
Expected: PASS — no `@intlify/vue-i18n/no-raw-text` violations (elapsed is rendered through `$t` with a `{seconds}` param); no unused-import (`ref` still used) or unused-var issues.

- [ ] **Step 3: Commit any lint fixups (only if Step 2 changed files)**

```bash
git add -A
git commit -m "chore(login): lint fixups for cold-start recovery"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** per-attempt timeout (spec §1 → Task 1); wall-clock budget loop extracted into `useColdStartLogin`, preserving 401-immediate / budget-exhaust behavior (spec §2 → Task 2); live progress via parameterised `auth.serverWaking` and ticker (spec §3 → Task 2 composable + Task 3 Steps 1, 4); thin `LoginView` consumer with `onUnmounted` cleanup (Task 3). No backend / no global timeout / no keep-warm (Global Constraints). All covered.
- **Placeholder scan:** none — every code and test step contains complete, final content.
- **Type consistency:** `login(credentials, timeoutMs?)` signature identical in `auth.ts`, `authStore.ts`, and the composable's `loginFn`; composable returns `{ wakingUp, wakingElapsedSec, run, stopTicker }`, consumed in `LoginView` as `wakingUp` / `wakingElapsedSec` (template) / `runColdStartLogin` / `stopWakingTicker` (onUnmounted); `auth.serverWaking` key name unchanged so both i18n gates hold.

## Post-merge verification (manual)

After CI is green and the PR is merged: hibernate the Render backend (≥15 min idle or redeploy), then log in at `kpi-operations-frontend.onrender.com` with `admin / admin123` and confirm the banner shows a climbing counter and auto-signs in once the backend is up (~90s). Confirms local==GitHub==Render.
