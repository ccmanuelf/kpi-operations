/**
 * Composable for ScenariosPanel inline-grid editing — column defs and
 * new-row save handler for what-if capacity scenarios.
 *
 * Domain semantics: scenarios are point-in-time records (DRAFT →
 * EVALUATED → APPLIED/REJECTED). The backend exposes create / run /
 * compare / delete but no update — once a scenario is committed,
 * name/type/parameters are immutable. Inline-edit therefore applies
 * **only to new rows**: an operator clicks Add, fills name + type +
 * parameters in the row, then clicks the green Save button to POST.
 * Existing rows expose Run (DRAFT only) / Delete actions.
 *
 * Selection: AG Grid's row-checkbox selection state is owned by the
 * parent (selectedScenarioIds). The parent enables a top-bar "Compare"
 * button when 2+ EVALUATED scenarios are selected.
 *
 * Backend alignment: store.createScenario(name, type, parameters)
 * forwards to capacityApi.createScenario, which now sends
 * `scenario_name` (matching backend ScenarioCreate) — fixed in this
 * commit.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

export interface ScenarioRow {
  id?: number
  _id?: number | string
  client_id?: string | number
  scenario_name?: string
  scenario_type?: string
  parameters?: Record<string, unknown>
  parameters_json?: Record<string, unknown>
  status?: string
  results?: {
    total_output?: number
    avg_utilization?: number
    on_time_rate?: number
  }
  results_json?: Record<string, unknown>
  _isNew?: boolean
  _isSaving?: boolean
  [key: string]: unknown
}

interface ColumnDef {
  headerName?: string
  headerTooltip?: string
  field?: string
  editable?: boolean | ((params: { data: ScenarioRow }) => boolean)
  cellEditor?: string
  cellEditorPopup?: boolean
  cellEditorParams?: { values?: string[]; min?: number; max?: number; precision?: number }
  cellRenderer?: (params: {
    data: ScenarioRow
    rowIndex: number
    value?: unknown
  }) => HTMLElement
  valueGetter?: (params: { data: ScenarioRow }) => unknown
  valueFormatter?: (params: { value?: unknown; data?: ScenarioRow }) => string
  valueSetter?: (params: { data: ScenarioRow; newValue: unknown }) => boolean
  width?: number
  minWidth?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
  checkboxSelection?: boolean | ((params: { data: ScenarioRow }) => boolean)
  headerCheckboxSelection?: boolean
}

// Backend scenario_type catalogue — see backend/routes/capacity/_models.py:478.
export const SCENARIO_TYPE_OPTIONS: string[] = [
  'OVERTIME',
  'SETUP_REDUCTION',
  'SUBCONTRACT',
  'NEW_LINE',
  'THREE_SHIFT',
  'LEAD_TIME_DELAY',
  'ABSENTEEISM_SPIKE',
  'MULTI_CONSTRAINT',
]

const TYPE_COLORS: Record<string, string> = {
  OVERTIME: '#f57c00',
  SETUP_REDUCTION: '#00897b',
  SUBCONTRACT: '#3949ab',
  NEW_LINE: '#43a047',
  THREE_SHIFT: '#8e24aa',
  LEAD_TIME_DELAY: '#c62828',
  ABSENTEEISM_SPIKE: '#fbc02d',
  MULTI_CONSTRAINT: '#1976d2',
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: '#757575',
  EVALUATED: '#2e7d32',
  APPLIED: '#1976d2',
  REJECTED: '#c62828',
}

// Type-specific default parameters mirroring the legacy dialog hints.
export const DEFAULT_PARAMETERS: Record<string, Record<string, unknown>> = {
  OVERTIME: { overtime_percent: 20 },
  SETUP_REDUCTION: { reduction_percent: 30 },
  SUBCONTRACT: { subcontract_percent: 40, department: 'CUTTING' },
  NEW_LINE: { new_line_code: 'SEWING_NEW', operators: 12 },
  THREE_SHIFT: { shift3_hours: 8.0, shift3_efficiency: 0.8 },
  LEAD_TIME_DELAY: { delay_days: 7 },
  ABSENTEEISM_SPIKE: { absenteeism_percent: 15, duration_days: 5 },
  MULTI_CONSTRAINT: {
    overtime_percent: 10,
    setup_reduction_percent: 15,
    absenteeism_percent: 8,
  },
}

interface SnackbarLike {
  showSuccess: (m: string) => void
  showError: (m: string) => void
}

interface UseScenariosGridDataOptions {
  scenarios: Ref<ScenarioRow[]>
  notify: SnackbarLike
  onSaveNewRow: (row: ScenarioRow) => Promise<void>
  onRunRow: (row: ScenarioRow) => Promise<void>
  onConfirmDelete: (row: ScenarioRow) => void
}

interface UseScenariosGridDataReturn {
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeNewRow: (row: ScenarioRow) => void
}

const requiredFieldsPresent = (row: ScenarioRow): boolean =>
  Boolean(row.scenario_name && row.scenario_type)

const formatPercent = (value: unknown): string => {
  if (value === null || value === undefined) return '--'
  const n = Number(value)
  return Number.isFinite(n) ? `${n.toFixed(1)}%` : '--'
}

const formatNumber = (value: unknown): string => {
  if (value === null || value === undefined) return '--'
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString() : '--'
}

const getResults = (row: ScenarioRow) => row.results || row.results_json || {}

const getParameters = (row: ScenarioRow): Record<string, unknown> =>
  (row.parameters || row.parameters_json || {}) as Record<string, unknown>

export default function useScenariosGridData(
  options: UseScenariosGridDataOptions,
): UseScenariosGridDataReturn {
  const { t } = useI18n()
  const { scenarios, notify, onSaveNewRow, onRunRow, onConfirmDelete } = options

  const addRow = (): void => {
    const newRow: ScenarioRow = {
      _isNew: true,
      _id: `new-${Date.now()}`,
      scenario_name: '',
      scenario_type: 'OVERTIME',
      parameters: { ...DEFAULT_PARAMETERS.OVERTIME },
      status: 'DRAFT',
    }
    scenarios.value = [newRow, ...scenarios.value]
  }

  const removeNewRow = (row: ScenarioRow): void => {
    scenarios.value = scenarios.value.filter((r) => r !== row)
  }

  const saveRow = async (row: ScenarioRow): Promise<void> => {
    if (!requiredFieldsPresent(row)) {
      notify.showError(
        t('capacityPlanning.scenarios.errors.fillRequired') ||
          'Fill scenario name and type first',
      )
      return
    }
    row._isSaving = true
    try {
      await onSaveNewRow(row)
      // Success path: store.createScenario pushes the persisted scenario
      // into whatIfScenarios.data, so we drop the local draft.
      scenarios.value = scenarios.value.filter((r) => r !== row)
    } finally {
      row._isSaving = false
    }
  }

  const runRow = async (row: ScenarioRow): Promise<void> => {
    if (row._isNew) {
      notify.showError(
        t('capacityPlanning.scenarios.errors.saveFirst') ||
          'Save the scenario before evaluating',
      )
      return
    }
    row._isSaving = true
    try {
      await onRunRow(row)
    } finally {
      row._isSaving = false
    }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: '',
      field: '_select',
      width: 50,
      pinned: 'left',
      checkboxSelection: (params) => !params.data._isNew,
      headerCheckboxSelection: false,
      sortable: false,
      filter: false,
      editable: false,
    },
    {
      headerName: t('capacityPlanning.scenarios.scenarioName'),
      headerTooltip: t('capacityPlanning.scenarios.scenarioName'),
      field: 'scenario_name',
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 220,
    },
    {
      headerName: t('capacityPlanning.scenarios.scenarioType'),
      headerTooltip: t('capacityPlanning.scenarios.scenarioType'),
      field: 'scenario_type',
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: SCENARIO_TYPE_OPTIONS },
      cellRenderer: (params) =>
        renderTypeChip(String(params.data.scenario_type || '')),
      // Switching type on a draft row also resets the parameters to
      // that type's defaults — same effect as picking a different type
      // in the legacy dialog.
      valueSetter: (params) => {
        if (!params.data._isNew) return false
        const next = String(params.newValue || '')
        if (!SCENARIO_TYPE_OPTIONS.includes(next)) return false
        params.data.scenario_type = next
        params.data.parameters = { ...(DEFAULT_PARAMETERS[next] || {}) }
        return true
      },
      width: 170,
    },
    {
      headerName: t('capacityPlanning.scenarios.parametersHeader'),
      headerTooltip: t('capacityPlanning.scenarios.parametersHeader'),
      field: 'parameters',
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      cellEditorParams: { rows: 6, cols: 50 },
      valueGetter: (params) => JSON.stringify(getParameters(params.data)),
      valueFormatter: (params) => {
        const params_obj = (params.data && getParameters(params.data)) || {}
        const entries = Object.entries(params_obj)
        if (!entries.length) return '--'
        return entries.map(([k, v]) => `${k}=${v}`).join(', ')
      },
      // Operators paste/edit raw JSON in the popup; we parse on commit.
      valueSetter: (params) => {
        if (!params.data._isNew) return false
        const raw = String(params.newValue || '').trim()
        if (!raw) {
          params.data.parameters = {}
          return true
        }
        try {
          const parsed = JSON.parse(raw)
          if (typeof parsed !== 'object' || Array.isArray(parsed)) return false
          params.data.parameters = parsed as Record<string, unknown>
          return true
        } catch {
          return false
        }
      },
      width: 280,
    },
    {
      headerName: t('capacityPlanning.scenarios.statusLabel') || 'Status',
      field: 'status',
      editable: false,
      cellRenderer: (params) =>
        renderStatusChip(String(params.data.status || 'DRAFT')),
      width: 110,
    },
    {
      headerName: t('capacityPlanning.scenarios.totalOutput'),
      headerTooltip: t('capacityPlanning.scenarios.totalOutput'),
      field: '_total_output',
      editable: false,
      sortable: true,
      filter: false,
      valueGetter: (params) => getResults(params.data).total_output,
      valueFormatter: (params) => formatNumber(params.value),
      width: 130,
    },
    {
      headerName: t('capacityPlanning.scenarios.utilization'),
      headerTooltip: t('capacityPlanning.scenarios.utilization'),
      field: '_avg_utilization',
      editable: false,
      sortable: true,
      filter: false,
      valueGetter: (params) => getResults(params.data).avg_utilization,
      valueFormatter: (params) => formatPercent(params.value),
      width: 120,
    },
    {
      headerName: t('capacityPlanning.scenarios.onTime'),
      headerTooltip: t('capacityPlanning.scenarios.onTime'),
      field: '_on_time_rate',
      editable: false,
      sortable: true,
      filter: false,
      valueGetter: (params) => getResults(params.data).on_time_rate,
      valueFormatter: (params) => formatPercent(params.value),
      width: 110,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) =>
        renderActions(params, {
          saveRow,
          removeNewRow,
          runRow,
          onConfirmDelete,
        }),
      width: 150,
      pinned: 'right',
    },
  ])

  return {
    columnDefs,
    addRow,
    removeNewRow,
  }
}

const renderTypeChip = (type: string): HTMLElement => {
  const span = document.createElement('span')
  if (!type) {
    span.textContent = '--'
    span.style.color = '#9e9e9e'
    return span
  }
  const color = TYPE_COLORS[type] || '#757575'
  span.textContent = type
  span.style.cssText = `
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    background: ${color};
  `
  return span
}

const renderStatusChip = (status: string): HTMLElement => {
  const span = document.createElement('span')
  if (!status) {
    span.textContent = '--'
    span.style.color = '#9e9e9e'
    return span
  }
  const color = STATUS_COLORS[status] || STATUS_COLORS.DRAFT
  span.textContent = status
  span.style.cssText = `
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    background: ${color};
  `
  return span
}

const renderActions = (
  params: { data: ScenarioRow; rowIndex: number },
  handlers: {
    saveRow: (row: ScenarioRow) => Promise<void>
    removeNewRow: (row: ScenarioRow) => void
    runRow: (row: ScenarioRow) => Promise<void>
    onConfirmDelete: (row: ScenarioRow) => void
  },
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  if (params.data._isNew) {
    div.innerHTML = `
      <button class="ag-grid-save-btn" title="Save scenario" style="
        background: #2e7d32;
        color: white;
        border: none;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">✓</button>
      <button class="ag-grid-cancel-btn" title="Discard" style="
        background: transparent;
        color: #c62828;
        border: 1px solid #c62828;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">✕</button>
    `
    div
      .querySelector('.ag-grid-save-btn')
      ?.addEventListener('click', () => handlers.saveRow(params.data))
    div
      .querySelector('.ag-grid-cancel-btn')
      ?.addEventListener('click', () => handlers.removeNewRow(params.data))
  } else {
    const isDraft = params.data.status === 'DRAFT'
    const runDisabled = !isDraft
    div.innerHTML = `
      <button class="ag-grid-run-btn" title="${isDraft ? 'Evaluate scenario' : 'Already evaluated'}" ${runDisabled ? 'disabled' : ''} style="
        background: ${runDisabled ? '#bdbdbd' : '#1976d2'};
        color: white;
        border: none;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: ${runDisabled ? 'not-allowed' : 'pointer'};
        font-size: 12px;
      ">▶</button>
      <button class="ag-grid-delete-btn" title="Delete" style="
        background: #c62828;
        color: white;
        border: none;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">✕</button>
    `
    if (!runDisabled) {
      div
        .querySelector('.ag-grid-run-btn')
        ?.addEventListener('click', () => handlers.runRow(params.data))
    }
    div
      .querySelector('.ag-grid-delete-btn')
      ?.addEventListener('click', () => handlers.onConfirmDelete(params.data))
  }
  return div
}
