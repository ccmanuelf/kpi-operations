/**
 * Gates the onboarding checklist's destinations against the shipped router.
 *
 * The first step, "configure shifts", pointed at /admin/settings — a screen
 * with no shift UI whatsoever. The backend really computes the step (it flips
 * true when SHIFT rows exist), so a new admin was told to do something the
 * product gave them no way to do: the item was un-completable except by the
 * seeder or direct DB access.
 *
 * Route existence alone would not have caught that (/admin/settings is a real
 * route), so the shifts step is pinned to the screen that can actually
 * complete it, by route NAME rather than by path string.
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))
vi.mock('@/services/api/onboarding', () => ({
  getOnboardingStatus: vi.fn(() => Promise.resolve({ data: null })),
}))

import { useOnboarding } from '../useOnboarding'
import router from '@/router'

const steps = () => useOnboarding().steps.value

describe('onboarding step destinations', () => {
  it('every step routes somewhere the shipped router actually knows', () => {
    for (const step of steps()) {
      const resolved = router.resolve(step.route)
      expect(resolved.matched.length, `${step.key} -> ${step.route} matches no route`).toBeGreaterThan(0)
    }
  })

  it('the shifts step lands on the shift admin screen, not on settings', () => {
    const shifts = steps().find((s) => s.key === 'shifts_configured')
    expect(shifts, 'shifts_configured step is missing').toBeDefined()
    expect(router.resolve(shifts!.route).name).toBe('admin-shifts')
  })
})
