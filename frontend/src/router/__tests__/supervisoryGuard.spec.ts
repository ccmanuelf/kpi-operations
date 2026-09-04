/**
 * Gates for the `requiresSupervisory` route guard.
 *
 * Unlike router.spec.ts — which builds its own router and re-implements the
 * guard, so it cannot catch drift — these import the SHIPPED guard and the
 * SHIPPED role list.
 *
 * The parity test reads `backend/orm/user.py` because the frontend cannot
 * import Python. Gating a screen tighter than its endpoints hides a capability
 * the API would have served; gating it looser hands the user a screen whose
 * every save 403s. Both are the same defect class this screen exists to close.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { RouteLocationNormalized, NavigationGuardNext } from 'vue-router'
import { navigationGuard, SUPERVISORY_ROLES } from '../index'

const storage: Record<string, string> = {}

beforeEach(() => {
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => storage[k] ?? null,
    setItem: (k: string, v: string) => {
      storage[k] = v
    },
    removeItem: (k: string) => {
      delete storage[k]
    },
    clear: () => {
      for (const k of Object.keys(storage)) delete storage[k]
    },
  })
  for (const k of Object.keys(storage)) delete storage[k]
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const signIn = (role: string) => {
  storage.access_token = 'token'
  storage.user = JSON.stringify({ role })
}

const visit = (role: string | null) => {
  if (role) signIn(role)
  const next = vi.fn() as unknown as NavigationGuardNext
  const to = {
    path: '/admin/hold-catalogs',
    meta: { requiresAuth: true, requiresSupervisory: true },
  } as unknown as RouteLocationNormalized
  navigationGuard.call(
    undefined,
    to,
    { path: '/' } as unknown as RouteLocationNormalized,
    next,
  )
  return next as unknown as ReturnType<typeof vi.fn>
}

describe('requiresSupervisory guard', () => {
  it.each(['admin', 'poweruser', 'leader', 'supervisor'])(
    'admits %s — the API accepts their catalog writes',
    (role) => {
      expect(visit(role)).toHaveBeenCalledWith()
    },
  )

  it.each(['operator', 'viewer'])('turns %s away from the screen', (role) => {
    expect(visit(role)).toHaveBeenCalledWith('/')
  })

  it('sends an unauthenticated visitor to login, not to the screen', () => {
    expect(visit(null)).toHaveBeenCalledWith('/login')
  })
})

describe('SUPERVISORY_ROLES parity with the backend', () => {
  it('matches backend/orm/user.py, the single source of truth for the tier', () => {
    const src = readFileSync(
      resolve(__dirname, '../../../../backend/orm/user.py'),
      'utf-8',
    )

    // Resolve `UserRole.X` -> its string value from the enum body.
    const enumValues: Record<string, string> = {}
    for (const [, name, value] of src.matchAll(/^\s{4}([A-Z_]+) = "([a-z]+)"/gm)) {
      enumValues[name] = value
    }
    expect(Object.keys(enumValues).length).toBeGreaterThan(0)

    const grab = (name: string): string => {
      const match = src.match(new RegExp(`^${name} = (.+)$`, 'm'))
      expect(match, `${name} not found in backend/orm/user.py`).not.toBeNull()
      return match![1]
    }

    const expand = (expr: string): string[] =>
      expr
        .split('+')
        .flatMap((term) =>
          term.includes('PLANNER_ROLES')
            ? expand(grab('PLANNER_ROLES'))
            : [...term.matchAll(/UserRole\.([A-Z_]+)\.value/g)].map(([, n]) => {
                expect(enumValues[n], `UserRole.${n} not found in the enum`).toBeDefined()
                return enumValues[n]
              }),
        )

    const backendTier = expand(grab('SUPERVISORY_ROLES'))

    expect(backendTier.length).toBe(4)
    expect([...backendTier].sort()).toEqual([...SUPERVISORY_ROLES].sort())
  })
})
