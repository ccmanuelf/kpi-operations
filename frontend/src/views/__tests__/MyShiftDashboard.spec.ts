/**
 * Rendering tests for MyShiftDashboard.vue — e2e-sweep ISSUE-007.
 *
 * The verified prod bug: an unassigned user (e.g. verify_bot, admin role,
 * no employee/line assignment) saw FABRICATED work orders (WO-2024-001/002/
 * 003), fake "Recent Activity" entries, and a hardcoded "Today's Summary"
 * that contradicted the real (zero) home-dashboard summary for the same day.
 *
 * These tests assert, at the rendered-DOM level:
 *  - the unassigned case renders the honest empty state and NEVER any
 *    fabricated record (checked structurally — the WO-2024-* pattern, not
 *    just a single literal string);
 *  - the assigned case (mocked composable data) renders the real records
 *    and hides the empty-state messaging.
 *
 * Per project convention, MyShiftDashboard.vue's <script setup> internals
 * aren't directly reachable from the test — instead the composables it
 * consumes (useShiftDashboardData, useShiftForms) are mocked at the module
 * boundary, same pattern as views/__tests__/misc-views.spec.ts.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { ref, computed } from 'vue'

// `@/i18n` — pulled in transitively by the api client's structured-error
// formatter — needs the real createI18n, so only useI18n is replaced.
vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {}, name: 'test' }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    user: { user_id: 'verify_bot', role: 'admin', client_id_assigned: null },
    currentUser: { user_id: 'verify_bot', role: 'admin', client_id_assigned: null },
    isAuthenticated: true,
    isAdmin: true,
  }),
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({ show: vi.fn(), showError: vi.fn(), showSuccess: vi.fn() }),
}))

const { shiftDashboardState } = vi.hoisted(() => ({
  shiftDashboardState: {
    assignedWorkOrders: [] as Array<Record<string, unknown>>,
    recentActivity: [] as Array<Record<string, unknown>>,
    myStats: { unitsProduced: 0, efficiency: 0, downtimeIncidents: 0, qualityChecks: 0 },
    hasAssignments: false,
    hasLoadError: false,
  },
}))

vi.mock('@/composables/useShiftDashboardData', () => ({
  useShiftDashboardData: () => ({
    assignedWorkOrders: ref(shiftDashboardState.assignedWorkOrders),
    recentActivity: ref(shiftDashboardState.recentActivity),
    myStats: ref(shiftDashboardState.myStats),
    hasAssignments: computed(() => shiftDashboardState.hasAssignments),
    hasLoadError: computed(() => shiftDashboardState.hasLoadError),
    currentDate: ref('2026-07-30'),
    currentDateFormatted: computed(() => 'July 30, 2026'),
    workOrderOptions: computed(() =>
      shiftDashboardState.assignedWorkOrders.map((wo) => ({
        text: `${wo.work_order_id} - ${wo.product_name}`,
        value: wo.id,
      })),
    ),
    formatRelativeTime: () => '15m ago',
    getProgressPercent: (wo: { produced?: number; target_qty?: number }) =>
      wo.target_qty ? Math.round(((wo.produced ?? 0) / wo.target_qty) * 100) : 0,
    getProgressColor: () => 'primary',
    getActivityColor: () => 'primary',
    getActivityIcon: () => 'mdi-package-variant',
    getActivityDescription: (activity: { description: string }) => activity.description,
    fetchMyShiftData: vi.fn(() => Promise.resolve()),
    initialize: vi.fn(() => Promise.resolve()),
    cleanup: vi.fn(),
  }),
}))

vi.mock('@/composables/useShiftForms', () => ({
  useShiftForms: () => ({
    showProductionDialog: ref(false),
    showDowntimeDialog: ref(false),
    showQualityDialog: ref(false),
    showHelpDialog: ref(false),
    isSubmitting: ref(false),
    showSuccess: ref(false),
    successMessage: ref(''),
    selectedWorkOrder: ref(null),
    productionForm: ref({}),
    downtimeForm: ref({}),
    qualityForm: ref({}),
    helpForm: ref({}),
    productionPresets: [10, 25, 50, 100],
    downtimeReasons: [],
    defectTypes: [],
    helpTypes: [],
    openQuickLog: vi.fn(),
    openQuickProductionDialog: vi.fn(),
    openDowntimeDialog: vi.fn(),
    openQualityDialog: vi.fn(),
    openHelpDialog: vi.fn(),
    quickLogProduction: vi.fn(),
    submitProduction: vi.fn(),
    submitDowntime: vi.fn(),
    submitQuality: vi.fn(),
    submitHelpRequest: vi.fn(),
  }),
}))

import MyShiftDashboard from '@/views/MyShiftDashboard.vue'

const globalStubs = {
  'v-row': { template: '<div class="v-row"><slot /></div>' },
  'v-col': { template: '<div class="v-col"><slot /></div>' },
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-icon': { template: '<span class="v-icon"><slot /></span>' },
  'v-avatar': { template: '<div class="v-avatar"><slot /></div>' },
  'v-chip': { template: '<span class="v-chip"><slot /></span>' },
  'v-spacer': { template: '<div class="v-spacer" />' },
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-btn': { template: '<button class="v-btn"><slot /></button>' },
  'v-list': { template: '<ul class="v-list"><slot /></ul>' },
  'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-progress-circular': { template: '<span class="v-progress-circular"><slot /></span>' },
  'v-snackbar': { template: '<div class="v-snackbar"><slot /><slot name="actions" /></div>' },
  'v-alert': { template: '<div class="v-alert" role="alert"><slot /></div>' },
}

function mountDashboard() {
  setActivePinia(createPinia())
  return shallowMount(MyShiftDashboard, {
    global: { stubs: globalStubs, mocks: { $t: (k: string) => k } },
  })
}

describe('MyShiftDashboard.vue', () => {
  beforeEach(() => {
    shiftDashboardState.assignedWorkOrders = []
    shiftDashboardState.recentActivity = []
    shiftDashboardState.myStats = { unitsProduced: 0, efficiency: 0, downtimeIncidents: 0, qualityChecks: 0 }
    shiftDashboardState.hasAssignments = false
    shiftDashboardState.hasLoadError = false
  })

  describe('unassigned user (verify_bot case)', () => {
    it('renders the honest empty-state message and never a fabricated work order', () => {
      const wrapper = mountDashboard()
      const html = wrapper.html()

      expect(wrapper.text()).toContain('myShift.noWorkOrders')
      expect(wrapper.text()).toContain('myShift.noWorkOrdersGuidance')

      // Structural: no WO-2024-* work order id anywhere in the render,
      // regardless of literal casing/spacing a future refactor might use.
      expect(html).not.toMatch(/WO-2024-\d+/)
      expect(html).not.toContain('Widget A')
      expect(html).not.toContain('Widget B')
      expect(html).not.toContain('Component X')
    })

    it('collapses the stats panel and quick-action tiles instead of showing dead 0% rings', () => {
      const wrapper = mountDashboard()
      const html = wrapper.html()

      // The stat-card grid and quick-action tiles are gated behind
      // hasAssignments; with none assigned they must not render at all.
      expect(html).not.toContain('stat-card')
      expect(html).not.toContain('quick-action-card')
    })
  })

  describe('assigned user (mocked real backend data)', () => {
    beforeEach(() => {
      shiftDashboardState.assignedWorkOrders = [
        { id: 1, work_order_id: 'WO-DEMO-042', product_name: 'Real Product', target_qty: 400, produced: 240 },
      ]
      shiftDashboardState.recentActivity = [
        { id: 'prod-501', type: 'production', description: 'Logged 80 units for WO-DEMO-042', timestamp: '2026-07-30T08:00:00Z' },
      ]
      shiftDashboardState.myStats = { unitsProduced: 240, efficiency: 92, downtimeIncidents: 1, qualityChecks: 3 }
      shiftDashboardState.hasAssignments = true
    })

    it('renders the real assigned work order and never the empty-state message', () => {
      const wrapper = mountDashboard()
      const html = wrapper.html()

      expect(wrapper.text()).toContain('WO-DEMO-042')
      expect(wrapper.text()).toContain('Real Product')
      expect(wrapper.text()).not.toContain('myShift.noWorkOrders')
      expect(html).not.toMatch(/WO-2024-\d+/)
    })

    it('renders the stats panel and quick-action tiles bound to real data', () => {
      const wrapper = mountDashboard()
      const html = wrapper.html()

      expect(html).toContain('stat-card')
      expect(html).toContain('quick-action-card')
    })
  })

  describe('load-failure state (distinguishable from genuine emptiness)', () => {
    it('shows the error indicator when the fetch failed', () => {
      shiftDashboardState.hasLoadError = true

      const wrapper = mountDashboard()

      expect(wrapper.find('.v-alert').exists()).toBe(true)
      expect(wrapper.text()).toContain('notifications.myShift.loadFailed')
    })

    it('does not show the error indicator on a genuinely empty (successful) fetch', () => {
      shiftDashboardState.hasLoadError = false
      shiftDashboardState.hasAssignments = false

      const wrapper = mountDashboard()

      expect(wrapper.find('.v-alert').exists()).toBe(false)
      // The empty state still renders — failure and emptiness are visually
      // distinct, not both silently absent.
      expect(wrapper.text()).toContain('myShift.noWorkOrders')
    })
  })
})
