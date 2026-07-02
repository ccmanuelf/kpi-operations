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
