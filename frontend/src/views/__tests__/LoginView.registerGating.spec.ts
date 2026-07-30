/**
 * ISSUE-006: the Login view's self-registration button must only render
 * when `VITE_DEMO_MODE` was baked in as "true" at build time (Render demo
 * deployment). `POST /api/auth/register` 403s outside DEMO_MODE (see
 * backend/routes/auth.py), so on every other deployment (VM prod, local
 * dev, CI) the button must not appear at all.
 *
 * LoginView.vue reads the flag once, at module-eval time, via
 * `isDemoModeEnabled()` (frontend/src/config/demoMode.ts — separately unit
 * tested). To exercise both states here the module graph has to be
 * re-evaluated per case (vi.resetModules + dynamic import) since a
 * `<script setup>` SFC's top-level const isn't otherwise reactive to an
 * env change after mount.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {}, name: 'test' }),
}))
vi.mock('@/services/api', () => ({ default: apiMock }))
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    user: null,
    currentUser: null,
    isAuthenticated: false,
    login: vi.fn(() => Promise.resolve({ success: false })),
    warmUpBackend: vi.fn(() => Promise.resolve()),
    logout: vi.fn(),
  }),
}))
vi.mock('@/components/LanguageToggle.vue', () => ({
  default: { template: '<div class="language-toggle-stub" />' },
}))

const globalStubs = {
  'v-container': { template: '<div><slot /></div>' },
  'v-row': { template: '<div><slot /></div>' },
  'v-col': { template: '<div><slot /></div>' },
  'v-card': { template: '<div><slot /></div>' },
  'v-card-text': { template: '<div><slot /></div>' },
  'v-card-actions': { template: '<div><slot /></div>' },
  'v-toolbar': { template: '<div><slot /></div>' },
  'v-toolbar-title': { template: '<div><slot /></div>' },
  'v-spacer': { template: '<div><slot /></div>' },
  'v-form': { template: '<form><slot /></form>' },
  'v-text-field': { template: '<input />' },
  'v-alert': { template: '<div><slot /></div>' },
  'v-progress-circular': { template: '<div />' },
  // Respect v-model so the (initially closed) Register dialog doesn't
  // unconditionally render its own "auth.registerAccount" title text —
  // that would make the toggle-button assertions below ambiguous.
  'v-dialog': {
    template: '<div v-if="modelValue"><slot /></div>',
    props: ['modelValue'],
  },
  'v-btn': {
    template: '<button class="v-btn" :aria-label="ariaLabel"><slot /></button>',
    props: ['ariaLabel', 'color', 'variant', 'loading', 'block', 'size'],
  },
}

function stubbedMount(component: unknown) {
  setActivePinia(createPinia())
  return shallowMount(component as never, {
    global: { stubs: globalStubs, mocks: { $t: (k: string) => k } },
  })
}

describe('LoginView — register button demo-mode gating', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders the register button when VITE_DEMO_MODE is "true"', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'true')
    const { default: LoginView } = await import('@/views/LoginView.vue')
    const wrapper = stubbedMount(LoginView)
    expect(wrapper.text()).toContain('auth.registerAccount')
  })

  it('hides the register button when VITE_DEMO_MODE is "false"', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false')
    const { default: LoginView } = await import('@/views/LoginView.vue')
    const wrapper = stubbedMount(LoginView)
    expect(wrapper.text()).not.toContain('auth.registerAccount')
  })

  it('hides the register button when VITE_DEMO_MODE is unset', async () => {
    vi.stubEnv('VITE_DEMO_MODE', undefined)
    const { default: LoginView } = await import('@/views/LoginView.vue')
    const wrapper = stubbedMount(LoginView)
    expect(wrapper.text()).not.toContain('auth.registerAccount')
  })
})
