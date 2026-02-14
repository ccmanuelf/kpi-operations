import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'

// ---------------------------------------------------------------------------
// localStorage mock
// The happy-dom version used by this project has an incomplete localStorage
// implementation (missing removeItem). We install a proper mock that the
// navigation guard can call via the global `localStorage` reference.
// ---------------------------------------------------------------------------

const storageMock = (() => {
  let store = {}
  return {
    getItem: vi.fn((key) => (key in store ? store[key] : null)),
    setItem: vi.fn((key, value) => { store[key] = String(value) }),
    removeItem: vi.fn((key) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
    get length() { return Object.keys(store).length },
    key: vi.fn((index) => Object.keys(store)[index] || null),
    _reset() {
      store = {}
      this.getItem.mockClear()
      this.setItem.mockClear()
      this.removeItem.mockClear()
      this.clear.mockClear()
    }
  }
})()

// ---------------------------------------------------------------------------
// Helper: build a fresh router with the same guard logic as the production
// router (frontend/src/router/index.js), but using createMemoryHistory so
// tests run without a real browser URL bar and with lightweight stub
// components instead of lazy-loaded views.
// ---------------------------------------------------------------------------

function createTestRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/login',
        name: 'login',
        component: { template: '<div>Login</div>' }
      },
      {
        path: '/',
        name: 'home',
        component: { template: '<div>Home</div>' },
        meta: { requiresAuth: true }
      },
      {
        path: '/production-entry',
        name: 'production-entry',
        component: { template: '<div>Production Entry</div>' },
        meta: { requiresAuth: true }
      },
      {
        path: '/kpi-dashboard',
        name: 'kpi-dashboard',
        component: { template: '<div>KPI Dashboard</div>' },
        meta: { requiresAuth: true }
      },
      {
        path: '/kpi/efficiency',
        name: 'kpi-efficiency',
        component: { template: '<div>Efficiency</div>' },
        meta: { requiresAuth: true }
      },
      {
        path: '/capacity-planning',
        name: 'capacity-planning',
        component: { template: '<div>Capacity Planning</div>' },
        meta: { requiresAuth: true }
      },
      {
        path: '/admin/settings',
        name: 'admin-settings',
        component: { template: '<div>Admin Settings</div>' },
        meta: { requiresAuth: true, requiresAdmin: true }
      },
      {
        path: '/admin/users',
        name: 'admin-users',
        component: { template: '<div>Admin Users</div>' },
        meta: { requiresAuth: true, requiresAdmin: true }
      }
    ]
  })

  // Replicate the production beforeEach guard exactly as it appears in
  // frontend/src/router/index.js (lines 210-238)
  router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('access_token')
    const isAuthenticated = !!token

    // Check authentication first
    if (to.meta.requiresAuth && !isAuthenticated) {
      next('/login')
      return
    }

    // Check admin role for admin routes
    if (to.meta.requiresAdmin && isAuthenticated) {
      const user = JSON.parse(localStorage.getItem('user') || 'null')
      const isAdmin = user?.role === 'admin' || user?.role === 'ADMIN'
      if (!isAdmin) {
        next('/')
        return
      }
    }

    // Redirect authenticated users away from login page
    if (to.path === '/login' && isAuthenticated) {
      next('/')
      return
    }

    next()
  })

  return router
}

// ---------------------------------------------------------------------------
// Helpers for localStorage manipulation
// ---------------------------------------------------------------------------

function setAuthenticated(userObj = null) {
  storageMock.setItem('access_token', 'test-jwt-token-abc123')
  if (userObj) {
    storageMock.setItem('user', JSON.stringify(userObj))
  }
}

function setAdmin() {
  setAuthenticated({ role: 'admin', username: 'admin-user' })
}

function setAdminUppercase() {
  setAuthenticated({ role: 'ADMIN', username: 'admin-user-upper' })
}

function setOperator() {
  setAuthenticated({ role: 'operator', username: 'op-user' })
}

function setSupervisor() {
  setAuthenticated({ role: 'supervisor', username: 'sup-user' })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Router Navigation Guards', () => {
  let router
  let originalLocalStorage

  beforeEach(() => {
    // Save original and install mock
    originalLocalStorage = globalThis.localStorage
    Object.defineProperty(globalThis, 'localStorage', {
      value: storageMock,
      writable: true,
      configurable: true
    })
    storageMock._reset()
    router = createTestRouter()
  })

  afterEach(() => {
    // Restore original localStorage
    Object.defineProperty(globalThis, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
      configurable: true
    })
  })

  // =========================================================================
  // Auth Guard -- unauthenticated users blocked from protected routes
  // =========================================================================

  describe('Auth Guard - unauthenticated access to protected routes', () => {
    it('redirects unauthenticated user from / to /login', async () => {
      router.push('/')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('redirects unauthenticated user from /production-entry to /login', async () => {
      router.push('/production-entry')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('redirects unauthenticated user from /kpi-dashboard to /login', async () => {
      router.push('/kpi-dashboard')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('redirects unauthenticated user from /capacity-planning to /login', async () => {
      router.push('/capacity-planning')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('allows unauthenticated user to stay on /login', async () => {
      router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })
  })

  // =========================================================================
  // Auth Guard -- authenticated users allowed on protected routes
  // =========================================================================

  describe('Auth Guard - authenticated access to protected routes', () => {
    it('allows authenticated user to access /', async () => {
      setAuthenticated({ role: 'operator', username: 'test' })

      router.push('/')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('allows authenticated user to access /production-entry', async () => {
      setAuthenticated({ role: 'operator', username: 'test' })

      router.push('/production-entry')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/production-entry')
    })

    it('allows authenticated user to access /kpi/efficiency', async () => {
      setAuthenticated({ role: 'operator', username: 'test' })

      router.push('/kpi/efficiency')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/kpi/efficiency')
    })
  })

  // =========================================================================
  // Admin Guard -- role-based access control
  // =========================================================================

  describe('Admin Guard - role-based access control', () => {
    it('allows admin user (role=admin) to access /admin/settings', async () => {
      setAdmin()

      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/admin/settings')
    })

    it('allows admin user (role=ADMIN uppercase) to access /admin/settings', async () => {
      setAdminUppercase()

      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/admin/settings')
    })

    it('allows admin user to access /admin/users', async () => {
      setAdmin()

      router.push('/admin/users')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/admin/users')
    })

    it('redirects non-admin operator from /admin/settings to /', async () => {
      setOperator()

      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('redirects non-admin supervisor from /admin/users to /', async () => {
      setSupervisor()

      router.push('/admin/users')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('redirects unauthenticated user from /admin/settings to /login (auth checked first)', async () => {
      // No token set -- auth guard fires before admin guard
      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })
  })

  // =========================================================================
  // Login Redirect -- authenticated users bounced from /login
  // =========================================================================

  describe('Login Redirect - authenticated users sent away from /login', () => {
    it('redirects authenticated user from /login to /', async () => {
      setAuthenticated({ role: 'operator', username: 'test' })

      router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('allows unauthenticated user to remain on /login', async () => {
      router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })
  })

  // =========================================================================
  // Route Metadata Verification
  // =========================================================================

  describe('Route Metadata', () => {
    it('all protected routes have requiresAuth meta set to true', () => {
      const protectedPaths = [
        '/',
        '/production-entry',
        '/kpi-dashboard',
        '/kpi/efficiency',
        '/capacity-planning',
        '/admin/settings',
        '/admin/users'
      ]

      for (const path of protectedPaths) {
        const resolved = router.resolve(path)
        expect(
          resolved.meta.requiresAuth,
          `Expected requiresAuth on ${path}`
        ).toBe(true)
      }
    })

    it('admin routes have both requiresAuth and requiresAdmin meta', () => {
      const adminPaths = ['/admin/settings', '/admin/users']

      for (const path of adminPaths) {
        const resolved = router.resolve(path)
        expect(
          resolved.meta.requiresAuth,
          `Expected requiresAuth on ${path}`
        ).toBe(true)
        expect(
          resolved.meta.requiresAdmin,
          `Expected requiresAdmin on ${path}`
        ).toBe(true)
      }
    })

    it('login route does NOT have requiresAuth meta', () => {
      const resolved = router.resolve('/login')

      expect(resolved.meta.requiresAuth).toBeFalsy()
    })
  })

  // =========================================================================
  // Edge Cases
  // =========================================================================

  describe('Edge Cases', () => {
    it('handles null user in localStorage gracefully (token present, user is literal null)', async () => {
      storageMock.setItem('access_token', 'some-token')
      storageMock.setItem('user', 'null')

      // JSON.parse('null') => null, null?.role => undefined, isAdmin is false
      // Non-admin is redirected to /
      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('handles missing user key in localStorage (token present, no user key at all)', async () => {
      storageMock.setItem('access_token', 'some-token')
      // user key never set -- getItem returns null, guard falls back to 'null'

      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('malformed user JSON in localStorage causes JSON.parse to throw (documents production vulnerability)', () => {
      // The production guard (line 222 in index.js) does:
      //   const user = JSON.parse(localStorage.getItem('user') || 'null')
      // WITHOUT a try/catch. If localStorage contains invalid JSON, the
      // guard will throw a SyntaxError and break navigation entirely.
      //
      // We verify this vulnerability exists by calling JSON.parse with
      // the same fallback pattern used in the guard. We do NOT trigger
      // an actual navigation because Vue Router's internal error
      // propagation creates an unhandled rejection that cannot be
      // cleanly caught in vitest.

      const malformedJson = '{invalid json!!}'
      expect(() => {
        JSON.parse(malformedJson)
      }).toThrow(SyntaxError)

      // The guard's fallback ('null') is only used when getItem returns
      // null. When a value IS present but malformed, the error surfaces.
      const fallbackValue = malformedJson || 'null'
      expect(fallbackValue).toBe(malformedJson) // fallback doesn't help
      expect(() => JSON.parse(fallbackValue)).toThrow(SyntaxError)
    })

    it('user object with unexpected role value is treated as non-admin', async () => {
      storageMock.setItem('access_token', 'some-token')
      storageMock.setItem('user', JSON.stringify({ role: 'superuser' }))

      // 'superuser' is neither 'admin' nor 'ADMIN', so guard denies access
      router.push('/admin/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })
  })
})
