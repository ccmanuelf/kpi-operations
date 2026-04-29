/**
 * Unit tests for Views
 * Tests: DashboardView (production overview), KPIDashboard (KPI detail view)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// ---------- Mocks ----------

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key) => key
  })
}))

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn()
  }),
  useRoute: () => ({
    params: {},
    query: {}
  }),
  onBeforeRouteLeave: vi.fn()
}))

// Mock date-fns
vi.mock('date-fns', () => ({
  format: vi.fn(() => '2026-02-15'),
  subDays: vi.fn((date, days) => new Date(date.getTime() - days * 86400000)),
  parseISO: vi.fn((str) => new Date(str))
}))

// Mock API
const mockApiGet = vi.fn()
const mockApiGetProducts = vi.fn(() => Promise.resolve({ data: [] }))
const mockApiGetShifts = vi.fn(() => Promise.resolve({ data: [] }))
const mockApiGetClients = vi.fn(() => Promise.resolve({ data: [] }))
vi.mock('@/services/api', () => ({
  default: {
    get: (...args) => mockApiGet(...args),
    getProducts: () => mockApiGetProducts(),
    getShifts: () => mockApiGetShifts(),
    getClients: () => mockApiGetClients(),
    getProductionEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getKPITrends: vi.fn(() => Promise.resolve({ data: {} })),
    sendEmailReport: vi.fn(() => Promise.resolve({ data: {} })),
    exportExcel: vi.fn(() => Promise.resolve({ data: new ArrayBuffer(0) })),
    downloadPDF: vi.fn(() => Promise.resolve({ data: new ArrayBuffer(0) }))
  }
}))

// Mock productionDataStore (used by DashboardView)
const mockProductionDataStore = {
  loading: false,
  productionEntries: [],
  fetchProductionEntries: vi.fn(() => Promise.resolve()),
  fetchKPIDashboard: vi.fn(() => Promise.resolve()),
  fetchAll: vi.fn(() => Promise.resolve())
}
vi.mock('@/stores/productionDataStore', () => ({
  useProductionDataStore: () => mockProductionDataStore
}))

// Mock kpiStore (used by KPIDashboard)
const mockKpiStore = {
  loading: false,
  allKPIs: [],
  fetchAll: vi.fn(() => Promise.resolve()),
  fetchAllKPIs: vi.fn(() => Promise.resolve()),
  kpiIcon: vi.fn(() => 'mdi-check'),
  summaryItems: [],
  trends: {
    efficiency: [],
    quality: [],
    availability: [],
    oee: [],
    performance: []
  }
}
vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => mockKpiStore
}))

// Mock dashboardStore
vi.mock('@/stores/dashboardStore', () => ({
  useDashboardStore: () => ({
    config: {},
    fetchConfig: vi.fn(() => Promise.resolve()),
    saveConfig: vi.fn(() => Promise.resolve()),
    initializePreferences: vi.fn(() => Promise.resolve())
  })
}))

// Mock filtersStore
vi.mock('@/stores/filtersStore', () => ({
  useFiltersStore: () => ({
    savedFilters: [],
    hasActiveFilter: false,
    activeFilter: null,
    clearActiveFilter: vi.fn(),
    fetchSavedFilters: vi.fn(() => Promise.resolve()),
    applyFilter: vi.fn(),
    saveFilter: vi.fn(() => Promise.resolve()),
    initializeFilters: vi.fn(() => Promise.resolve())
  })
}))

// Mock child components
vi.mock('@/components/dialogs/EmailReportsDialog.vue', () => ({
  default: { template: '<div class="email-dialog-stub"></div>' }
}))
vi.mock('@/components/ui/EmptyState.vue', () => ({
  default: { template: '<div class="empty-state-stub"><slot /></div>' }
}))
vi.mock('@/components/ui/TableSkeleton.vue', () => ({
  default: { template: '<div class="table-skeleton-stub"></div>', props: ['rows', 'columns'] }
}))
vi.mock('@/components/ui/CardSkeleton.vue', () => ({
  default: { template: '<div class="card-skeleton-stub"></div>', props: ['variant'] }
}))
vi.mock('@/components/grids/ProductionEntryGrid.vue', () => ({
  default: { template: '<div class="production-grid-stub"></div>' }
}))
vi.mock('@/components/CSVUploadDialogProduction.vue', () => ({
  default: { template: '<div class="csv-upload-stub"></div>' }
}))
vi.mock('@/components/filters/FilterBar.vue', () => ({
  default: { template: '<div class="filter-bar-stub"></div>', props: ['filterType', 'clients'] }
}))
vi.mock('@/components/dashboard/DashboardCustomizer.vue', () => ({
  default: { template: '<div class="customizer-stub"></div>', props: ['modelValue'] }
}))
vi.mock('@/components/filters/FilterManager.vue', () => ({
  default: { template: '<div class="filter-manager-stub"></div>', props: ['modelValue'] }
}))
vi.mock('@/components/QRCodeScanner.vue', () => ({
  default: { template: '<div class="qr-scanner-stub"></div>' }
}))
vi.mock('@/components/kpi/InferenceIndicator.vue', () => ({
  default: { template: '<div class="inference-stub"></div>', props: ['isEstimated', 'confidenceScore', 'inferenceDetails'] }
}))

// Mock vue-chartjs
vi.mock('vue-chartjs', () => ({
  Line: { template: '<canvas class="chart-stub"></canvas>', props: ['data', 'options'] },
  Bar: { template: '<canvas class="chart-stub"></canvas>', props: ['data', 'options'] }
}))

// Mock chart.js
vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  CategoryScale: {},
  LinearScale: {},
  PointElement: {},
  LineElement: {},
  Title: {},
  Tooltip: {},
  Legend: {},
  Filler: {}
}))

// Stubs for Vuetify components
const globalStubs = {
  'v-container': { template: '<div class="v-container"><slot /></div>' },
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-card-actions': { template: '<div class="v-card-actions"><slot /></div>' },
  'v-btn': { template: '<button class="v-btn"><slot /></button>', props: ['color', 'variant', 'loading', 'disabled', 'icon'] },
  'v-icon': { template: '<span class="v-icon"><slot /></span>' },
  'v-row': { template: '<div class="v-row"><slot /></div>' },
  'v-col': { template: '<div class="v-col"><slot /></div>' },
  'v-spacer': { template: '<div class="v-spacer"></div>' },
  'v-chip': { template: '<span class="v-chip"><slot /></span>', props: ['color', 'size', 'variant'] },
  'v-tooltip': { template: '<div class="v-tooltip"><slot /><slot name="activator" :props="{}" /></div>' },
  'v-select': { template: '<select class="v-select"></select>', props: ['modelValue', 'items', 'label'] },
  'v-data-table': { template: '<table class="v-data-table"><slot /></table>', props: ['headers', 'items', 'loading'] },
  'v-progress-linear': { template: '<div class="v-progress-linear"></div>', props: ['modelValue', 'color'] },
  'v-dialog': { template: '<div class="v-dialog"><slot /></div>', props: ['modelValue'] },
  'v-list': { template: '<ul class="v-list"><slot /></ul>' },
  'v-list-item': { template: '<li class="v-list-item"><slot /><slot name="prepend" /></li>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-list-subheader': { template: '<div class="v-list-subheader"><slot /></div>' },
  'v-menu': { template: '<div class="v-menu"><slot /><slot name="activator" :props="{}" /></div>' },
  'v-overlay': { template: '<div class="v-overlay"><slot /></div>', props: ['modelValue'] },
  'v-progress-circular': { template: '<div class="v-progress-circular"></div>' },
  'v-snackbar': { template: '<div class="v-snackbar"><slot /><slot name="actions" /></div>', props: ['modelValue', 'color'] },
  'v-form': { template: '<form class="v-form"><slot /></form>', props: ['modelValue'] },
  'v-combobox': { template: '<div class="v-combobox"></div>', props: ['modelValue'] },
  'v-text-field': { template: '<input class="v-text-field" />', props: ['modelValue', 'label'] },
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-btn-toggle': { template: '<div class="v-btn-toggle"><slot /></div>', props: ['modelValue'] },
  'v-checkbox': { template: '<input type="checkbox" class="v-checkbox" />', props: ['modelValue'] }
}

// ============================================================
// DashboardView
// ============================================================
describe('DashboardView', () => {
  let DashboardView

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockProductionDataStore.productionEntries = []
    mockProductionDataStore.loading = false
    const mod = await import('../DashboardView.vue')
    DashboardView = mod.default
  })

  it('renders the dashboard page title', () => {
    const wrapper = shallowMount(DashboardView, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('dashboard.title')
  })

  it('renders the overview subtitle', () => {
    const wrapper = shallowMount(DashboardView, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('dashboard.overview')
  })

  it('renders the production entries section title', () => {
    const wrapper = shallowMount(DashboardView, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('production.title')
  })

  it('renders export buttons for CSV and Excel', () => {
    const wrapper = shallowMount(DashboardView, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('reports.exportCsv')
    expect(wrapper.text()).toContain('reports.exportExcel')
  })

  it('renders email reports button', () => {
    const wrapper = shallowMount(DashboardView, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('reports.title')
  })
})

// ============================================================
// KPIDashboard
// ============================================================
describe('KPIDashboard', () => {
  let KPIDashboard

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockKpiStore.allKPIs = []
    mockKpiStore.loading = false
    const mod = await import('../KPIDashboard.vue')
    KPIDashboard = mod.default
  })

  it('renders the KPI dashboard title', () => {
    const wrapper = shallowMount(KPIDashboard, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('navigation.kpiDashboard')
  })

  it('renders the KPI subtitle', () => {
    const wrapper = shallowMount(KPIDashboard, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('kpi.title')
  })

  it('renders a refresh button', () => {
    const wrapper = shallowMount(KPIDashboard, {
      global: { stubs: globalStubs }
    })

    const buttons = wrapper.findAll('.v-btn')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('renders the trend period selector', () => {
    const wrapper = shallowMount(KPIDashboard, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('common.days')
  })

  it('renders reports section', () => {
    const wrapper = shallowMount(KPIDashboard, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('reports.title')
  })
})

// ============================================================
// ProductionEntry
// ============================================================
describe('ProductionEntry', () => {
  let ProductionEntry

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const mod = await import('../ProductionEntry.vue')
    ProductionEntry = mod.default
  })

  it('renders the production entry page title', () => {
    const wrapper = shallowMount(ProductionEntry, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('navigation.productionEntry')
  })

  it('renders the ProductionEntryGrid component', () => {
    const wrapper = shallowMount(ProductionEntry, {
      global: { stubs: globalStubs }
    })

    // shallowMount auto-stubs child components as <component-name-stub>
    expect(wrapper.find('production-entry-grid-stub').exists()).toBe(true)
  })

  it('renders child components for CSV upload and grid', () => {
    const wrapper = shallowMount(ProductionEntry, {
      global: { stubs: globalStubs }
    })

    // shallowMount replaces child components with stubs
    // Verify wrapper contains at least 2 auto-stubs (ProductionEntryGrid + CSVUploadDialogProduction)
    const html = wrapper.html()
    // The auto-stub tags end with -stub
    const stubCount = (html.match(/-stub/g) || []).length
    expect(stubCount).toBeGreaterThanOrEqual(2)
  })
})
