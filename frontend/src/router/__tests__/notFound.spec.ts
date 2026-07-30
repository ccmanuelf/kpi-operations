import { describe, it, expect } from 'vitest'
import router from '../index'

// ISSUE 015: unknown routes used to render a blank app shell. Verifies the
// production router (not a hand-rolled test copy) resolves ANY unmatched
// path to the dedicated not-found view via the catch-all route.
describe('Router catch-all (ISSUE 015)', () => {
  it.each([
    '/quality',
    '/admin/assumption-variance',
    '/this/does/not/exist',
    '/random-typo',
  ])('resolves unknown path %s to the not-found route', (path) => {
    const resolved = router.resolve(path)
    expect(resolved.name).toBe('not-found')
    expect(resolved.matched.some((r) => r.name === 'not-found')).toBe(true)
  })

  it('does not shadow a real, registered route', () => {
    const resolved = router.resolve('/kpi-dashboard')
    expect(resolved.name).toBe('kpi-dashboard')
  })
})
