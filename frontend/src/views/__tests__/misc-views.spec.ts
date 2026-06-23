/**
 * Smoke-mount tests for misc views (Phase B.3 Buckets 4 + 5).
 *
 * Covers entry-page wrappers (AttendanceEntry, DowntimeEntry,
 * HoldResumeEntry, QualityEntry — Bucket 4, 8 stmts each) plus the
 * remaining large 0%-coverage views: LoginView, MyShiftDashboard,
 * AlertsView, HelpCenter, PlanVsActualView, WorkOrderManagement.
 *
 * SimulationV2View (924 stmts) is exercised by `simulation-v2.spec.ts`
 * (E2E), and CapacityPlanningView (222 stmts) by `capacity-*.spec.ts`
 * — both already covered by E2E so a smoke unit-test would duplicate
 * the existing coverage path. Skipped here per the strategy doc.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { ref, computed } from 'vue'

// ---------- shared mocks ----------
const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getProductionEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getDowntimeEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getQualityEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getAttendanceEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getHoldEntries: vi.fn(() => Promise.resolve({ data: [] })),
    getWorkOrders: vi.fn(() => Promise.resolve({ data: [] })),
    createWorkOrder: vi.fn(() => Promise.resolve({ data: {} })),
    updateWorkOrder: vi.fn(() => Promise.resolve({ data: {} })),
    deleteWorkOrder: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('@/i18n', () => ({
  default: {
    global: {
      t: (k: string) => k,
      locale: { value: 'en' },
    },
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
    user: { user_id: 'u1', role: 'OPERATOR', client_id_assigned: 'C1' },
    currentUser: { user_id: 'u1', role: 'OPERATOR' },
    isAuthenticated: true,
    isAdmin: false,
    login: vi.fn(() => Promise.resolve({ success: true })),
    warmUpBackend: vi.fn(() => Promise.resolve()),
    logout: vi.fn(),
  }),
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({
    show: vi.fn(),
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}))

// ---------- composables used by misc views ----------
vi.mock('@/composables/useShiftDashboardData', () => ({
  useShiftDashboardData: () => ({
    assignedWorkOrders: ref([]),
    recentActivity: ref([]),
    myStats: ref({}),
    currentDate: ref(new Date()),
    currentDateFormatted: computed(() => 'May 07, 2026'),
    workOrderOptions: ref([]),
    formatTime: () => '',
    formatRelativeTime: () => '',
    getProgressPercent: () => 0,
    getProgressColor: () => 'grey',
    getActivityColor: () => 'grey',
    getActivityIcon: () => 'mdi-clock',
    fetchMyShiftData: vi.fn(() => Promise.resolve()),
    initialize: vi.fn(() => Promise.resolve()),
    cleanup: vi.fn(),
  }),
}))

vi.mock('@/composables/useShiftForms', () => ({
  useShiftForms: () => ({
    showProductionDialog: ref(false),
    showQualityDialog: ref(false),
    showDowntimeDialog: ref(false),
    productionForm: ref({}),
    qualityForm: ref({}),
    downtimeForm: ref({}),
    submitting: ref(false),
    submitProduction: vi.fn(() => Promise.resolve()),
    submitQuality: vi.fn(() => Promise.resolve()),
    submitDowntime: vi.fn(() => Promise.resolve()),
    openProductionDialog: vi.fn(),
    openQualityDialog: vi.fn(),
    openDowntimeDialog: vi.fn(),
    closeProductionDialog: vi.fn(),
    closeQualityDialog: vi.fn(),
    closeDowntimeDialog: vi.fn(),
  }),
  downtimeReasonToCode: (r: string) => r,
}))

vi.mock('@/composables/usePlanVsActual', () => ({
  usePlanVsActual: () => ({
    orders: ref([]),
    summary: computed(() => ({})),
    loading: ref(false),
    filters: ref({}),
    statusOptions: ref([]),
    headers: ref([]),
    fetchData: vi.fn(() => Promise.resolve()),
    resetFilters: vi.fn(),
    getRiskColor: () => 'grey',
    getVarianceColor: () => 'grey',
    getVarianceClass: () => '',
    getCompletionColor: () => 'grey',
    formatDate: (d: string) => d,
  }),
}))

vi.mock('@/help', () => ({
  getAllDocs: () => [],
  getDocById: () => null,
  getDefaultDocId: () => 'getting-started',
}))

// ---------- child components stubbed ----------
vi.mock('@/components/LanguageToggle.vue', () => ({
  default: { template: '<div class="language-toggle-stub" />' },
}))
vi.mock('@/components/DataCompletenessIndicator.vue', () => ({
  default: { template: '<div class="data-completeness-stub" />' },
}))
vi.mock('@/components/dialogs/ShiftDashboardDialogs.vue', () => ({
  default: { template: '<div class="shift-dashboard-dialogs-stub" />' },
}))
vi.mock('@/components/dual_view/DualViewKPIPanel.vue', () => ({
  default: { template: '<div class="dual-view-kpi-panel-stub" />' },
}))
vi.mock('@/components/alerts/AlertDashboard.vue', () => ({
  default: { template: '<div class="alert-dashboard-stub" />' },
}))
vi.mock('@/components/grids/AttendanceEntryGrid.vue', () => ({
  default: { template: '<div class="attendance-entry-grid-stub" />' },
}))
vi.mock('@/components/grids/DowntimeEntryGrid.vue', () => ({
  default: { template: '<div class="downtime-entry-grid-stub" />' },
}))
vi.mock('@/components/grids/HoldEntryGrid.vue', () => ({
  default: { template: '<div class="hold-entry-grid-stub" />' },
}))
vi.mock('@/components/grids/QualityEntryGrid.vue', () => ({
  default: { template: '<div class="quality-entry-grid-stub" />' },
}))
vi.mock('@/components/CSVUploadDialogAttendance.vue', () => ({
  default: { template: '<div class="csv-upload-attendance-stub" />' },
}))
vi.mock('@/components/CSVUploadDialogDowntime.vue', () => ({
  default: { template: '<div class="csv-upload-downtime-stub" />' },
}))
vi.mock('@/components/CSVUploadDialogHold.vue', () => ({
  default: { template: '<div class="csv-upload-hold-stub" />' },
}))
vi.mock('@/components/CSVUploadDialogQuality.vue', () => ({
  default: { template: '<div class="csv-upload-quality-stub" />' },
}))
vi.mock('@/components/grids/WorkOrderGrid.vue', () => ({
  default: { template: '<div class="work-order-grid-stub" />' },
}))
vi.mock('@/components/CSVUploadDialogWorkOrders.vue', () => ({
  default: { template: '<div class="csv-upload-work-orders-stub" />' },
}))

// Static imports — vitest resolves the @/ alias at compile time.
import LoginView from '@/views/LoginView.vue'
import MyShiftDashboard from '@/views/MyShiftDashboard.vue'
import AlertsView from '@/views/AlertsView.vue'
import HelpCenter from '@/views/HelpCenter.vue'
import PlanVsActualView from '@/views/PlanVsActualView.vue'
import WorkOrderManagement from '@/views/WorkOrderManagement.vue'
import AttendanceEntry from '@/views/AttendanceEntry.vue'
import DowntimeEntry from '@/views/DowntimeEntry.vue'
import HoldResumeEntry from '@/views/HoldResumeEntry.vue'
import QualityEntry from '@/views/QualityEntry.vue'

const globalStubs = {
  'v-container': { template: '<div class="v-container"><slot /></div>' },
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-subtitle': { template: '<div class="v-card-subtitle"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-card-actions': { template: '<div class="v-card-actions"><slot /></div>' },
  'v-row': { template: '<div class="v-row"><slot /></div>' },
  'v-col': { template: '<div class="v-col"><slot /></div>' },
  'v-spacer': { template: '<div class="v-spacer" />' },
  'v-btn': {
    template: '<button class="v-btn"><slot /></button>',
    props: ['color', 'variant', 'loading', 'disabled', 'icon', 'size', 'block', 'type'],
  },
  'v-icon': {
    template: '<span class="v-icon"><slot /></span>',
    props: ['start', 'size', 'color', 'left'],
  },
  'v-chip': {
    template: '<span class="v-chip"><slot /></span>',
    props: ['color', 'size', 'variant'],
  },
  'v-text-field': {
    template: '<input class="v-text-field" />',
    props: [
      'modelValue',
      'type',
      'label',
      'density',
      'variant',
      'rules',
      'hideDetails',
      'clearable',
      'autofocus',
      'autocomplete',
      'prependInnerIcon',
      'appendInnerIcon',
    ],
  },
  'v-select': {
    template: '<select class="v-select"><slot /></select>',
    props: ['modelValue', 'items', 'itemTitle', 'itemValue', 'label'],
  },
  'v-checkbox': {
    template: '<input type="checkbox" class="v-checkbox" />',
    props: ['modelValue', 'label'],
  },
  'v-textarea': {
    template: '<textarea class="v-textarea" />',
    props: ['modelValue', 'label'],
  },
  'v-data-table': {
    template: '<table class="v-data-table"><slot /></table>',
    props: ['headers', 'items', 'loading'],
  },
  'v-dialog': {
    template: '<div class="v-dialog"><slot /></div>',
    props: ['modelValue', 'maxWidth', 'persistent'],
  },
  'v-form': { template: '<form class="v-form"><slot /></form>', props: ['modelValue'] },
  'v-snackbar': {
    template: '<div class="v-snackbar"><slot /></div>',
    props: ['modelValue', 'color'],
  },
  'v-overlay': {
    template: '<div class="v-overlay"><slot /></div>',
    props: ['modelValue'],
  },
  'v-progress-circular': {
    template: '<span class="v-progress-circular" />',
    props: ['modelValue', 'indeterminate', 'color', 'size'],
  },
  'v-tabs': { template: '<div class="v-tabs"><slot /></div>', props: ['modelValue'] },
  'v-tab': { template: '<button class="v-tab"><slot /></button>', props: ['value'] },
  'v-window': { template: '<div class="v-window"><slot /></div>', props: ['modelValue'] },
  'v-window-item': { template: '<div class="v-window-item"><slot /></div>' },
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-alert': {
    template: '<div class="v-alert"><slot /></div>',
    props: ['type', 'variant', 'density'],
  },
  'v-list': { template: '<ul class="v-list"><slot /></ul>' },
  'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-tooltip': { template: '<div class="v-tooltip"><slot /></div>' },
  'v-img': { template: '<img class="v-img" />', props: ['src', 'alt'] },
  'v-avatar': { template: '<div class="v-avatar"><slot /></div>' },
  'v-toolbar': { template: '<div class="v-toolbar"><slot /></div>' },
  'v-toolbar-title': { template: '<div class="v-toolbar-title"><slot /></div>' },
  'v-table': { template: '<table class="v-table"><slot /></table>' },
  'v-autocomplete': {
    template: '<input class="v-autocomplete" />',
    props: ['modelValue', 'items'],
  },
  'v-skeleton-loader': { template: '<div class="v-skeleton-loader" />' },
  'v-app': { template: '<div class="v-app"><slot /></div>' },
  'v-main': { template: '<main class="v-main"><slot /></main>' },
  'v-fab': { template: '<button class="v-fab"><slot /></button>' },
  'v-bottom-sheet': {
    template: '<div class="v-bottom-sheet"><slot /></div>',
    props: ['modelValue'],
  },
}

function smokeMount(component: unknown) {
  setActivePinia(createPinia())
  return shallowMount(component as never, {
    global: {
      stubs: globalStubs,
      mocks: { $t: (k: string) => k },
    },
  })
}

describe('Misc views — smoke mount', () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((fn) => {
      if (typeof fn === 'function') (fn as { mockClear?: () => void }).mockClear?.()
    })
  })

  // Bucket 5 — large misc views
  it('LoginView.vue mounts without errors', () => {
    expect(smokeMount(LoginView).exists()).toBe(true)
  })

  it('MyShiftDashboard.vue mounts without errors', () => {
    expect(smokeMount(MyShiftDashboard).exists()).toBe(true)
  })

  it('AlertsView.vue mounts without errors', () => {
    expect(smokeMount(AlertsView).exists()).toBe(true)
  })

  it('HelpCenter.vue mounts without errors', () => {
    expect(smokeMount(HelpCenter).exists()).toBe(true)
  })

  it('PlanVsActualView.vue mounts without errors', () => {
    expect(smokeMount(PlanVsActualView).exists()).toBe(true)
  })

  it('WorkOrderManagement.vue mounts without errors', () => {
    expect(smokeMount(WorkOrderManagement).exists()).toBe(true)
  })

  // Bucket 4 — entry-page wrappers (8-stmt thin shells)
  it('AttendanceEntry.vue mounts without errors', () => {
    expect(smokeMount(AttendanceEntry).exists()).toBe(true)
  })

  it('DowntimeEntry.vue mounts without errors', () => {
    expect(smokeMount(DowntimeEntry).exists()).toBe(true)
  })

  it('HoldResumeEntry.vue mounts without errors', () => {
    expect(smokeMount(HoldResumeEntry).exists()).toBe(true)
  })

  it('QualityEntry.vue mounts without errors', () => {
    expect(smokeMount(QualityEntry).exists()).toBe(true)
  })
})
