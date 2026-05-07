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

const apiMock = {
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
}
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

// ---------- helpers ----------
async function smokeMount(loader: () => Promise<unknown>) {
  setActivePinia(createPinia())
  const mod = (await loader()) as { default: unknown }
  const wrapper = shallowMount(mod.default as never, {
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

  it('Efficiency.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/Efficiency.vue'))
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('.v-container').exists()).toBe(true)
  })

  it('Performance.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/Performance.vue'))
    expect(wrapper.exists()).toBe(true)
  })

  it('Quality.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/Quality.vue'))
    expect(wrapper.exists()).toBe(true)
  })

  it('Availability.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/Availability.vue'))
    expect(wrapper.exists()).toBe(true)
  })

  it('OEE.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/OEE.vue'))
    expect(wrapper.exists()).toBe(true)
  })

  it('Absenteeism.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/Absenteeism.vue'))
    expect(wrapper.exists()).toBe(true)
  })

  it('OnTimeDelivery.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/OnTimeDelivery.vue'))
    expect(wrapper.exists()).toBe(true)
  })

  it('WIPAging.vue mounts without errors', async () => {
    const wrapper = await smokeMount(() => import('@/views/kpi/WIPAging.vue'))
    expect(wrapper.exists()).toBe(true)
  })
})
