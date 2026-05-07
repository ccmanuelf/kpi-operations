/**
 * Smoke-mount tests for admin views (Phase B.3 Bucket 2).
 *
 * Lifts the 11 admin views from 0% line coverage. Each test asserts the
 * view imports + mounts under realistic mocks for its dependencies
 * (vue-i18n, vue-router, @/services/api, @/stores/*, plus the cluster of
 * `use*Data` / `use*Forms` / `use*GridData` composables that the
 * domain-specific admin pages delegate to).
 *
 * Behavioral coverage for admin CRUD lives in the corresponding composable
 * test files (`useDefectTypesGridData.spec.ts`, etc.). The intent here is
 * the B.3 acceptance: "no view at 0% lines (≥1% acceptable)".
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
    getUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getRoles: vi.fn(() => Promise.resolve({ data: [] })),
    createUser: vi.fn(() => Promise.resolve({ data: {} })),
    updateUser: vi.fn(() => Promise.resolve({ data: {} })),
    deleteUser: vi.fn(() => Promise.resolve({ data: {} })),
    getDefectTypes: vi.fn(() => Promise.resolve({ data: [] })),
    getSystemSettings: vi.fn(() => Promise.resolve({ data: {} })),
    updateSystemSettings: vi.fn(() => Promise.resolve({ data: {} })),
    getWorkflowConfigs: vi.fn(() => Promise.resolve({ data: [] })),
    getWorkflowDefinition: vi.fn(() => Promise.resolve({ data: {} })),
    getDatabaseConfig: vi.fn(() => Promise.resolve({ data: {} })),
    getClientConfig: vi.fn(() => Promise.resolve({ data: {} })),
    getKPIThresholds: vi.fn(() => Promise.resolve({ data: [] })),
    updateKPIThresholds: vi.fn(() => Promise.resolve({ data: {} })),
    deleteKPIThreshold: vi.fn(() => Promise.resolve({ data: {} })),
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

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({
    show: vi.fn(),
    showError: vi.fn(),
    showSuccess: vi.fn(),
    showInfo: vi.fn(),
    showWarning: vi.fn(),
  }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    user: { user_id: 'admin', role: 'ADMIN', client_id_assigned: null },
    isAdmin: true,
  }),
}))

vi.mock('@/stores/databaseConfigStore', () => ({
  useDatabaseConfigStore: () => ({
    // The view uses storeToRefs(store) — these need to be refs so the
    // resulting refs unwrap to non-undefined values during render.
    currentProvider: ref('sqlite'),
    connectionInfo: ref({}),
    canMigrate: ref(false),
    isMigrating: ref(false),
    migrationStatus: ref(null),
    migrationProgress: ref(0),
    migrationCompleted: ref(false),
    migrationFailed: ref(false),
    providerDisplayName: ref('SQLite'),
    isLoading: ref(false),
    error: ref(null),
    connectionTestResult: ref(null),
    fetchStatus: vi.fn(() => Promise.resolve()),
    fetchProviders: vi.fn(() => Promise.resolve()),
    runMigration: vi.fn(() => Promise.resolve()),
  }),
}))

// Composables used by admin views — each provides the minimum surface
// the view destructures. Real behavior lives in the composables' own
// unit specs.
function makeGridComposableStub() {
  return () => ({
    gridRef: ref(null),
    rowData: ref([]),
    columnDefs: ref([]),
    onGridReady: vi.fn(),
    onCellValueChanged: vi.fn(),
    onRowsPasted: vi.fn(),
    addNewEntry: vi.fn(),
    saveChanges: vi.fn(),
    onConfirmSave: vi.fn(),
    onCancelSave: vi.fn(),
    showConfirmDialog: ref(false),
    pendingData: ref(null),
    pendingRowsCount: ref(0),
    confirmationFieldConfig: ref([]),
    showPasteDialog: ref(false),
    parsedPasteData: ref([]),
    convertedPasteRows: ref([]),
    pasteValidationResult: ref({ valid: true }),
    pasteColumnMapping: ref({}),
    pasteGridColumns: ref([]),
    onPasteConfirm: vi.fn(),
    onPasteCancel: vi.fn(),
    saving: ref(false),
    snackbar: ref({ show: false, message: '', color: 'success' }),
    unsavedChanges: ref(new Set()),
    hasUnsavedChanges: computed(() => false),
    filteredEntries: ref([]),
    applyFilters: vi.fn(),
  })
}

vi.mock('@/composables/useDefectTypesData', () => ({
  default: () => ({
    GLOBAL_CLIENT_ID: 'GLOBAL',
    selectedClient: ref('GLOBAL'),
    defectTypes: ref([]),
    clientOptions: ref([]),
    isGlobalSelected: computed(() => true),
    selectedClientInfo: computed(() => null),
    loadClients: vi.fn(() => Promise.resolve()),
    loadDefectTypes: vi.fn(() => Promise.resolve()),
  }),
}))
vi.mock('@/composables/useDefectTypesForms', () => ({
  default: () => ({
    uploadDialog: ref(false),
    deleteDialog: ref(false),
    deleteTarget: ref(null),
    uploadFile: ref(null),
    replaceExisting: ref(false),
    uploading: ref(false),
    deleting: ref(false),
    snackbar: ref({ show: false, message: '', color: 'success' }),
    showSnackbar: vi.fn(),
    confirmDelete: vi.fn(),
    deleteDefectType: vi.fn(),
    openUploadDialog: vi.fn(),
    closeUploadDialog: vi.fn(),
    uploadCSV: vi.fn(),
    downloadTemplate: vi.fn(),
  }),
}))
vi.mock('@/composables/useDefectTypesGridData', () => ({
  default: () => ({
    columnDefs: ref([]),
    addRow: vi.fn(),
    onCellValueChanged: vi.fn(),
  }),
}))

vi.mock('@/composables/useFloatingPoolData', () => ({
  default: () => ({
    loading: ref(false),
    loadingInsights: ref(false),
    entries: ref([]),
    statusFilter: ref(null),
    clientFilter: ref(null),
    insightsPanel: ref(null),
    insights: ref({ recommendations: [], summary: {}, breakdowns: {} }),
    summary: ref({ total: 0, available: 0, assigned: 0 }),
    utilizationPercent: computed(() => 0),
    statusOptions: ref([]),
    clientOptions: ref([]),
    filteredEntries: ref([]),
    fetchData: vi.fn(() => Promise.resolve()),
    fetchInsights: vi.fn(() => Promise.resolve()),
  }),
}))
vi.mock('@/composables/useFloatingPoolGridData', () => ({
  default: () => ({
    columnDefs: ref([]),
    onCellValueChanged: vi.fn(),
  }),
}))

vi.mock('@/composables/usePartOpportunitiesData', () => ({
  usePartOpportunitiesData: () => ({
    selectedClient: ref(null),
    partOpportunities: ref([]),
    snackbar: ref({ show: false, message: '', color: 'success' }),
    clientOptions: ref([]),
    averageOpportunities: computed(() => 0),
    minOpportunities: computed(() => 0),
    maxOpportunities: computed(() => 0),
    loadClients: vi.fn(() => Promise.resolve()),
    loadPartOpportunities: vi.fn(() => Promise.resolve()),
    showSnackbar: vi.fn(),
  }),
}))
vi.mock('@/composables/usePartOpportunitiesForms', () => ({
  usePartOpportunitiesForms: () => ({
    uploadDialog: ref(false),
    deleteDialog: ref(false),
    deleteTarget: ref(null),
    uploading: ref(false),
    deleting: ref(false),
    uploadFile: ref(null),
    replaceExisting: ref(false),
    confirmDelete: vi.fn(),
    deletePartOpportunity: vi.fn(),
    openUploadDialog: vi.fn(),
    closeUploadDialog: vi.fn(),
    uploadCSV: vi.fn(),
    downloadTemplate: vi.fn(),
  }),
}))
vi.mock('@/composables/usePartOpportunitiesGridData', () => ({
  default: () => ({
    columnDefs: ref([]),
    addRow: vi.fn(),
    onCellValueChanged: vi.fn(),
  }),
}))

vi.mock('@/composables/useClientConfigData', () => ({
  useClientConfigData: () => ({
    loadingClients: ref(false),
    loadingConfig: ref(false),
    clients: ref([]),
    selectedClientId: ref(null),
    clientConfig: ref({}),
    globalDefaults: ref({}),
    snackbar: ref({ show: false, message: '', color: 'success' }),
    selectedClientName: computed(() => ''),
    configSections: ref([]),
    formatLabel: (s: string) => s,
    formatValue: (v: unknown) => String(v),
    showSnackbar: vi.fn(),
    loadClientConfig: vi.fn(() => Promise.resolve()),
    initialize: vi.fn(() => Promise.resolve()),
  }),
}))
vi.mock('@/composables/useClientConfigForms', () => ({
  useClientConfigForms: () => ({
    editDialog: ref(false),
    confirmResetDialog: ref(false),
    formValid: ref(true),
    configForm: ref(null),
    saving: ref(false),
    resetting: ref(false),
    formData: ref({}),
    otdModeOptions: ref([]),
    rules: {},
    editFormFields: ref([]),
    openEditDialog: vi.fn(),
    confirmResetToDefaults: vi.fn(),
    saveConfig: vi.fn(() => Promise.resolve()),
    resetToDefaults: vi.fn(() => Promise.resolve()),
  }),
}))

vi.mock('@/composables/useWorkflowConfigData', () => ({
  default: () => ({
    loadingClients: ref(false),
    loadingConfig: ref(false),
    loadingAnalytics: ref(false),
    clients: ref([]),
    selectedClientId: ref(null),
    workflowConfig: ref({}),
    templates: ref([]),
    statusDistribution: ref([]),
    averageTimes: ref({}),
    allStatuses: ref([]),
    closureTriggerOptions: ref([]),
    selectedClientName: computed(() => ''),
    getStatusColor: () => 'grey',
    formatStatus: (s: string) => s,
    formatClosureTrigger: (s: string) => s,
    getClosureTriggerIcon: () => 'mdi-cog',
    getClosureTriggerHint: () => '',
    loadClients: vi.fn(() => Promise.resolve()),
    loadTemplates: vi.fn(() => Promise.resolve()),
    loadClientConfig: vi.fn(() => Promise.resolve()),
  }),
}))
vi.mock('@/composables/useWorkflowConfigForms', () => ({
  default: () => ({
    editDialog: ref(false),
    confirmTemplateDialog: ref(false),
    selectedTemplate: ref(null),
    formValid: ref(true),
    configForm: ref(null),
    saving: ref(false),
    applyingTemplate: ref(false),
    formData: ref({}),
    snackbar: ref({ show: false, message: '', color: 'success' }),
    showSnackbar: vi.fn(),
    openEditDialog: vi.fn(),
    saveConfig: vi.fn(() => Promise.resolve()),
    confirmApplyTemplate: vi.fn(),
    applyTemplate: vi.fn(() => Promise.resolve()),
  }),
}))

// Child components used by admin views — minimal stubs.
vi.mock('@/components/grids/AGGridBase.vue', () => ({
  default: { template: '<div class="ag-grid-base-stub"><slot /></div>' },
}))
vi.mock('@/components/admin/MigrationWizard.vue', () => ({
  default: { template: '<div class="migration-wizard-stub" />' },
}))
vi.mock('@/components/admin/MigrationProgress.vue', () => ({
  default: { template: '<div class="migration-progress-stub" />' },
}))
vi.mock('@/components/admin/FloatingPoolGuideDialog.vue', () => ({
  default: { template: '<div class="floating-pool-guide-stub" />' },
}))
vi.mock('@/components/workflow/WorkflowDesigner.vue', () => ({
  default: { template: '<div class="workflow-designer-stub" />' },
}))
vi.mock('@/views/admin/components/PartOpportunitiesGuide.vue', () => ({
  default: { template: '<div class="part-opportunities-guide-stub" />' },
}))
vi.mock('@/views/admin/components/WorkflowAnalyticsCards.vue', () => ({
  default: { template: '<div class="workflow-analytics-cards-stub" />' },
}))
vi.mock('@/views/admin/components/WorkflowConfigDialogs.vue', () => ({
  default: { template: '<div class="workflow-config-dialogs-stub" />' },
}))
vi.mock('@/components/dialogs/ReadBackConfirmation.vue', () => ({
  default: { template: '<div class="read-back-confirmation-stub" />' },
}))
vi.mock('@/components/dialogs/PastePreviewDialog.vue', () => ({
  default: { template: '<div class="paste-preview-dialog-stub" />' },
}))
vi.mock('@/components/common/LineSelector.vue', () => ({
  default: { template: '<div class="line-selector-stub" />' },
}))

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
    props: ['color', 'variant', 'loading', 'disabled', 'icon', 'size', 'block'],
  },
  'v-icon': { template: '<span class="v-icon"><slot /></span>', props: ['start', 'size', 'color'] },
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
    ],
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
      'multiple',
      'chips',
    ],
  },
  'v-checkbox': {
    template: '<input type="checkbox" class="v-checkbox" />',
    props: ['modelValue', 'label'],
  },
  'v-switch': {
    template: '<input type="checkbox" class="v-switch" />',
    props: ['modelValue', 'label', 'color'],
  },
  'v-textarea': {
    template: '<textarea class="v-textarea" />',
    props: ['modelValue', 'label', 'rows'],
  },
  'v-data-table': {
    template: '<table class="v-data-table"><slot /></table>',
    props: ['headers', 'items', 'loading', 'itemsPerPage', 'noDataText'],
  },
  'v-data-table-server': {
    template: '<table class="v-data-table-server"><slot /></table>',
    props: ['headers', 'items', 'loading', 'itemsLength'],
  },
  'v-dialog': {
    template: '<div class="v-dialog"><slot /></div>',
    props: ['modelValue', 'maxWidth', 'persistent'],
  },
  'v-form': { template: '<form class="v-form"><slot /></form>', props: ['modelValue'] },
  'v-snackbar': {
    template: '<div class="v-snackbar"><slot /></div>',
    props: ['modelValue', 'color', 'timeout'],
  },
  'v-overlay': {
    template: '<div class="v-overlay"><slot /></div>',
    props: ['modelValue'],
  },
  'v-progress-circular': {
    template: '<span class="v-progress-circular" />',
    props: ['modelValue', 'indeterminate', 'color', 'size'],
  },
  'v-progress-linear': {
    template: '<div class="v-progress-linear" />',
    props: ['modelValue', 'color'],
  },
  'v-tabs': { template: '<div class="v-tabs"><slot /></div>', props: ['modelValue'] },
  'v-tab': { template: '<button class="v-tab"><slot /></button>', props: ['value'] },
  'v-window': { template: '<div class="v-window"><slot /></div>', props: ['modelValue'] },
  'v-window-item': {
    template: '<div class="v-window-item"><slot /></div>',
    props: ['value'],
  },
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-alert': {
    template: '<div class="v-alert"><slot /></div>',
    props: ['type', 'variant', 'density'],
  },
  'v-list': { template: '<ul class="v-list"><slot /></ul>', props: ['density'] },
  'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-tooltip': { template: '<div class="v-tooltip"><slot /></div>', props: ['text', 'location'] },
  'v-expansion-panels': { template: '<div class="v-expansion-panels"><slot /></div>' },
  'v-expansion-panel': { template: '<div class="v-expansion-panel"><slot /></div>' },
  'v-expansion-panel-title': {
    template: '<div class="v-expansion-panel-title"><slot /></div>',
  },
  'v-expansion-panel-text': {
    template: '<div class="v-expansion-panel-text"><slot /></div>',
  },
  'v-table': { template: '<table class="v-table"><slot /></table>', props: ['density'] },
  'v-autocomplete': {
    template: '<input class="v-autocomplete" />',
    props: ['modelValue', 'items', 'itemTitle', 'itemValue', 'label', 'multiple', 'chips'],
  },
  'v-list-subheader': {
    template: '<div class="v-list-subheader"><slot /></div>',
  },
  'v-menu': { template: '<div class="v-menu"><slot /></div>', props: ['modelValue'] },
  'v-chip-group': {
    template: '<div class="v-chip-group"><slot /></div>',
    props: ['modelValue', 'multiple'],
  },
  'v-alert-title': { template: '<div class="v-alert-title"><slot /></div>' },
  'v-tab-item': { template: '<div class="v-tab-item"><slot /></div>', props: ['value'] },
  'v-toolbar': { template: '<div class="v-toolbar"><slot /></div>' },
  'v-toolbar-title': { template: '<div class="v-toolbar-title"><slot /></div>' },
  'v-img': { template: '<img class="v-img" />', props: ['src', 'alt', 'width', 'height'] },
  'v-avatar': { template: '<div class="v-avatar"><slot /></div>', props: ['size', 'color'] },
  'v-badge': { template: '<div class="v-badge"><slot /></div>', props: ['content', 'color'] },
}

// Static imports — vitest resolves the @/ alias at compile time.
import AdminClients from '@/views/admin/AdminClients.vue'
import AdminUsers from '@/views/admin/AdminUsers.vue'
import AdminSettings from '@/views/admin/AdminSettings.vue'
import AdminDefectTypes from '@/views/admin/AdminDefectTypes.vue'
import FloatingPoolManagement from '@/views/admin/FloatingPoolManagement.vue'
import PartOpportunities from '@/views/admin/PartOpportunities.vue'
import AssumptionVarianceReport from '@/views/admin/AssumptionVarianceReport.vue'
import ClientConfigView from '@/views/admin/ClientConfigView.vue'
import WorkflowConfigView from '@/views/admin/WorkflowConfigView.vue'
import WorkflowDesignerView from '@/views/admin/WorkflowDesignerView.vue'
import DatabaseConfigView from '@/views/admin/DatabaseConfigView.vue'

function smokeMount(component: unknown) {
  setActivePinia(createPinia())
  return shallowMount(component as never, {
    global: {
      stubs: globalStubs,
      mocks: { $t: (k: string) => k },
    },
  })
}

describe('Admin views — smoke mount', () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((fn) => {
      if (typeof fn === 'function') (fn as { mockClear?: () => void }).mockClear?.()
    })
  })

  it('AdminClients.vue mounts without errors', () => {
    expect(smokeMount(AdminClients).exists()).toBe(true)
  })

  it('AdminUsers.vue mounts without errors', () => {
    expect(smokeMount(AdminUsers).exists()).toBe(true)
  })

  it('AdminSettings.vue mounts without errors', () => {
    expect(smokeMount(AdminSettings).exists()).toBe(true)
  })

  it('AdminDefectTypes.vue mounts without errors', () => {
    expect(smokeMount(AdminDefectTypes).exists()).toBe(true)
  })

  it('FloatingPoolManagement.vue mounts without errors', () => {
    expect(smokeMount(FloatingPoolManagement).exists()).toBe(true)
  })

  it('PartOpportunities.vue mounts without errors', () => {
    expect(smokeMount(PartOpportunities).exists()).toBe(true)
  })

  it('AssumptionVarianceReport.vue mounts without errors', () => {
    expect(smokeMount(AssumptionVarianceReport).exists()).toBe(true)
  })

  it('ClientConfigView.vue mounts without errors', () => {
    expect(smokeMount(ClientConfigView).exists()).toBe(true)
  })

  it('WorkflowConfigView.vue mounts without errors', () => {
    expect(smokeMount(WorkflowConfigView).exists()).toBe(true)
  })

  it('WorkflowDesignerView.vue mounts without errors', () => {
    expect(smokeMount(WorkflowDesignerView).exists()).toBe(true)
  })

  it('DatabaseConfigView.vue mounts without errors', () => {
    expect(smokeMount(DatabaseConfigView).exists()).toBe(true)
  })
})
