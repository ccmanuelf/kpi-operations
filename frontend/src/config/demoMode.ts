/**
 * Demo-mode flag for build-time UI gating.
 *
 * `VITE_DEMO_MODE` is baked in at build time (see frontend/Dockerfile),
 * mirroring the existing `VITE_API_URL` pattern: Render's demo deployment
 * sets it to "true"; the VM (and every other deployment) leaves it unset
 * (falsy). `POST /api/auth/register` is demo-only (403 outside DEMO_MODE —
 * see backend/routes/auth.py) so the Login view's self-registration button
 * must not render where the endpoint can't succeed (ISSUE-006).
 */
export function isDemoModeEnabled(): boolean {
  return import.meta.env.VITE_DEMO_MODE === 'true'
}
