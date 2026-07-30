import { describe, it, expect, afterEach, vi } from 'vitest'
import { isDemoModeEnabled } from '../demoMode'

// ISSUE-006: the Login view's self-registration button must only render
// when VITE_DEMO_MODE was baked in as "true" at build time (Render demo).
// Every other deployment (VM prod, local dev, CI) leaves it unset/false,
// and the backend 403s the endpoint outside DEMO_MODE.
describe('isDemoModeEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('returns true when VITE_DEMO_MODE is "true"', () => {
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    expect(isDemoModeEnabled()).toBe(true)
  })

  it('returns false when VITE_DEMO_MODE is "false"', () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    expect(isDemoModeEnabled()).toBe(false)
  })

  it('returns false when VITE_DEMO_MODE is unset', () => {
    vi.stubEnv('VITE_DEMO_MODE', undefined)
    expect(isDemoModeEnabled()).toBe(false)
  })
})
