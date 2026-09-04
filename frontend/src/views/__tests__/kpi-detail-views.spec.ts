/**
 * Smoke-mount tests for the 8 KPI detail views (Phase B.3 Bucket 1).
 *
 * These views are presentation layers — the meaningful logic for Efficiency /
 * Performance / Quality lives in their composables (covered by separate specs).
 * The remaining 5 (Availability / OEE / Absenteeism / OnTimeDelivery / WIPAging)
 * still inline their logic in `<script setup>`; flagged in
 * `_audit/B3-zero-coverage-views.md` as composable-extraction follow-up.
 *
 * The intent here is to satisfy the B.3 acceptance criterion ("no view at 0%
 * lines") and to assert the views import + render under realistic store/API
 * mocks without throwing. Behavioral tests live alongside the composables
 * (see `composables/__tests__/useEfficiencyData.spec.ts`).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// ---------- mocks ----------
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

// Wrapped in vi.hoisted so it initialises BEFORE the hoisted vi.mock factory
// that closes over it. A plain top-level const only worked while every view was
// imported dynamically from inside a test; the static imports below evaluate at
// module load, which would hit the TDZ. (Same shape as admin-views.spec.ts.)
const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getPrediction: vi.fn(() => Promise.resolve({ data: null })),
    get: vi.fn(() => Promise.resolve({ data: [] })),
    getKPITrends: vi.fn(() => Promise.resolve({ data: {} })),
    getOEEHistory: vi.fn(() => Promise.resolve({ data: [] })),
    getAvailabilityHistory: vi.fn(() => Promise.resolve({ data: [] })),
    getAbsenteeismHistory: vi.fn(() => Promise.resolve({ data: [] })),
    getOnTimeDeliveryHistory: vi.fn(() => Promise.resolve({ data: [] })),
    getWIPAgingHistory: vi.fn(() => Promise.resolve({ data: [] })),
    getAttendanceEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getHoldEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getProductionEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getDowntimeEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getQualityEntries: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('@/services/api', () => ({ default: apiMock }))

vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({
    efficiency: { current: 85 },
    performance: { current: 90 },
    quality: { current: 95 },
    availability: { current: 88 },
    oee: { current: 80 },
    absenteeism: { current: 5 },
    on_time_delivery: { current: 90 },
    onTimeDelivery: { current: 90 },
    wipAging: { current: 3 },
    wip_aging: { current: 3 },
    otd: { current: 90 },
    dashboard: [],
    // Inline views (Availability/OEE/Absenteeism/OnTimeDelivery/WIPAging) read
    // kpiStore.trends.<key> directly to build chart data; provide empty arrays
    // so the computed chartData refs don't throw on map/length calls.
    trends: {
      efficiency: [],
      performance: [],
      quality: [],
      availability: [],
      oee: [],
      absenteeism: [],
      onTimeDelivery: [],
      on_time_delivery: [],
      otd: [],
      wipAging: [],
      wip_aging: [],
    },
    fetchEfficiency: vi.fn(() => Promise.resolve()),
    fetchPerformance: vi.fn(() => Promise.resolve()),
    fetchQuality: vi.fn(() => Promise.resolve()),
    fetchAvailability: vi.fn(() => Promise.resolve()),
    fetchOEE: vi.fn(() => Promise.resolve()),
    fetchAbsenteeism: vi.fn(() => Promise.resolve()),
    fetchOnTimeDelivery: vi.fn(() => Promise.resolve()),
    fetchWIPAging: vi.fn(() => Promise.resolve()),
    fetchOTD: vi.fn(() => Promise.resolve()),
    fetchDashboard: vi.fn(() => Promise.resolve()),
    fetchTrend: vi.fn(() => Promise.resolve()),
    setClient: vi.fn(),
    setDateRange: vi.fn(),
  }),
}))

vi.mock('vue-chartjs', () => ({
  Line: { template: '<canvas class="chart-stub" />', props: ['data', 'options'] },
  Bar: { template: '<canvas class="chart-stub" />', props: ['data', 'options'] },
}))
vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  CategoryScale: {},
  LinearScale: {},
  PointElement: {},
  LineElement: {},
  BarElement: {},
  Title: {},
  Tooltip: {},
  Legend: {},
  Filler: {},
}))

const globalStubs = {
  'v-container': { template: '<div class="v-container"><slot /></div>' },
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-row': { template: '<div class="v-row"><slot /></div>' },
  'v-col': { template: '<div class="v-col"><slot /></div>' },
  'v-spacer': { template: '<div class="v-spacer" />' },
  'v-btn': {
    template: '<button class="v-btn"><slot /></button>',
    props: ['color', 'variant', 'loading', 'disabled', 'icon', 'size'],
  },
  'v-icon': { template: '<span class="v-icon"><slot /></span>', props: ['start', 'size', 'color'] },
  'v-chip': {
    template: '<span class="v-chip"><slot /></span>',
    props: ['color', 'size', 'variant'],
  },
  'v-text-field': {
    template: '<input class="v-text-field" />',
    props: ['modelValue', 'type', 'label', 'density', 'variant', 'singleLine', 'hideDetails', 'appendIcon'],
  },
  'v-select': {
    template: '<select class="v-select"><slot /></select>',
    props: [
      'modelValue',
      'items',
      'itemTitle',
      'itemValue',
      'label',
      'clearable',
      'density',
      'variant',
    ],
  },
  'v-switch': {
    template: '<input type="checkbox" class="v-switch" />',
    props: ['modelValue', 'label', 'color', 'inset'],
  },
  'v-data-table': {
    template: '<table class="v-data-table"><slot /></table>',
    props: ['headers', 'items', 'search', 'loading', 'itemsPerPage', 'noDataText', 'density'],
  },
  'v-progress-circular': {
    template: '<span class="v-progress-circular"><slot /></span>',
    props: ['modelValue', 'color', 'size', 'width', 'indeterminate'],
  },
  'v-overlay': {
    template: '<div class="v-overlay"><slot /></div>',
    props: ['modelValue', 'contained'],
  },
  'v-list': { template: '<ul class="v-list"><slot /></ul>', props: ['density'] },
  'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-tooltip': { template: '<div class="v-tooltip"><slot /></div>', props: ['text', 'location'] },
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-alert': { template: '<div class="v-alert"><slot /></div>', props: ['type', 'variant', 'density'] },
}


// Static imports — see the note in smokeMount on why these are not dynamic.
import Efficiency from '@/views/kpi/Efficiency.vue'
import Performance from '@/views/kpi/Performance.vue'
import Quality from '@/views/kpi/Quality.vue'
import Availability from '@/views/kpi/Availability.vue'
import OEE from '@/views/kpi/OEE.vue'
import Absenteeism from '@/views/kpi/Absenteeism.vue'
import OnTimeDelivery from '@/views/kpi/OnTimeDelivery.vue'
import WIPAging from '@/views/kpi/WIPAging.vue'

// ---------- helpers ----------
/**
 * Takes an already-imported component on purpose.
 *
 * These were `await smokeMount(() => import(...))`. The first such test paid
 * the cold transform of the whole dependency graph the 8 KPI views share
 * INSIDE the 5s per-test timeout — measured at 7727ms under full-suite load
 * against 77-406ms for every later one, which is exactly the ~1-in-15
 * "Efficiency.vue timed out" flake, never reproducible in isolation because
 * an isolated run has no contention. Static imports are hoisted to module
 * load, which vitest does not bill against the per-test timeout, so the race
 * is gone rather than merely widened. `vi.mock` is hoisted above them and
 * still applies. Matches admin-views.spec.ts, which has never flaked.
 */
function smokeMount(component: unknown) {
  setActivePinia(createPinia())
  const wrapper = shallowMount(component as never, {
    global: {
      stubs: globalStubs,
      // KPI views use template-side $t directly (vs `t()` from useI18n),
      // so we provide an identity translator on globalProperties.
      mocks: { $t: (k: string) => k },
    },
  })
  return wrapper
}

// ---------- specs ----------
describe('KPI detail views — smoke mount', () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((fn) => {
      if (typeof fn === 'function') (fn as { mockClear?: () => void }).mockClear?.()
    })
  })

  it('Efficiency.vue mounts without errors', () => {
    const wrapper = smokeMount(Efficiency)
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.v-container').exists()).toBe(true)
  })

  it('Performance.vue mounts without errors', () => {
    const wrapper = smokeMount(Performance)
    expect(wrapper.exists()).toBe(true)
  })

  it('Quality.vue mounts without errors', () => {
    const wrapper = smokeMount(Quality)
    expect(wrapper.exists()).toBe(true)
  })

  it('Availability.vue mounts without errors', () => {
    const wrapper = smokeMount(Availability)
    expect(wrapper.exists()).toBe(true)
  })

  it('OEE.vue mounts without errors', () => {
    const wrapper = smokeMount(OEE)
    expect(wrapper.exists()).toBe(true)
  })

  it('Absenteeism.vue mounts without errors', () => {
    const wrapper = smokeMount(Absenteeism)
    expect(wrapper.exists()).toBe(true)
  })

  it('OnTimeDelivery.vue mounts without errors', () => {
    const wrapper = smokeMount(OnTimeDelivery)
    expect(wrapper.exists()).toBe(true)
  })

  it('WIPAging.vue mounts without errors', () => {
    const wrapper = smokeMount(WIPAging)
    expect(wrapper.exists()).toBe(true)
  })
})
